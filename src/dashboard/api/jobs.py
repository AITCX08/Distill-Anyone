"""Versioned job query and mutation endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.application.commands import CreateJobRequest, JobView, PreviewRequest, PreviewResult
from src.application.service import DistillationService
from src.dashboard.schemas import (
    CreateJobInput,
    ItemResponse,
    JobDetailsResponse,
    JobResponse,
    PreviewInput,
    PreviewResponse,
    RevisionInput,
)
from src.dashboard.security import require_local_session, require_mutation_security
from src.distillation.state import ProcessingStatus, RevisionConflict

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _job_response(view: JobView) -> JobResponse:
    return JobResponse(
        job_id=view.job_id,
        status=view.status.value,
        revision=view.revision,
        platform=view.platform,
        creator_id=view.creator_id,
        creator_name=view.creator_name,
        outputs=view.outputs,
        total_items=view.total_items,
        completed_items=view.completed_items,
        failed_items=view.failed_items,
        unsupported_items=view.unsupported_items,
        updated_at=view.updated_at,
    )


def _preview_response(value: PreviewResult) -> PreviewResponse:
    return PreviewResponse(**value.__dict__)


def _delivery_details(job_id: str, request: Request) -> JobDetailsResponse:
    state = request.app.state.service.queries.get(job_id)
    raw_destination = state.request.get("output_directory")
    if not isinstance(raw_destination, str) or not raw_destination.strip():
        raise HTTPException(status_code=409, detail="此任务没有可用的保存位置")
    destination = Path(raw_destination).expanduser().resolve(strict=False)
    if destination == destination.parent or not destination.is_dir():
        raise HTTPException(status_code=409, detail="保存位置不可用")

    titles = (
        str(value.get("title")).strip()
        for value in state.catalog.values()
        if isinstance(value, dict) and isinstance(value.get("title"), str)
    )
    display_title = next((title for title in titles if title), "内容蒸馏任务")
    completed_at = max(
        (item.completed_at for item in state.items.values() if item.completed_at),
        default=None,
    )
    return JobDetailsResponse(
        job_id=state.job_id,
        display_title=display_title,
        creator_name=str(state.creator.get("display_name") or "未知创作者"),
        destination=str(destination),
        artifact_count=sum(len(item.artifacts) for item in state.items.values()),
        completed_at=completed_at,
    )


@router.post("/preview", response_model=PreviewResponse, dependencies=[Depends(require_mutation_security)])
def preview(payload: PreviewInput, request: Request):
    service: DistillationService = request.app.state.service
    return _preview_response(service.preview(PreviewRequest(**payload.model_dump())))


@router.post("", response_model=JobResponse, dependencies=[Depends(require_mutation_security)])
def create(payload: CreateJobInput, request: Request):
    service: DistillationService = request.app.state.service
    data = payload.model_dump()
    destination = _resolve_destination(payload, request)
    data.pop("destination_mode", None)
    data.pop("destination_token", None)
    return _job_response(service.create(CreateJobRequest(**data, output_directory=str(destination))))


def _resolve_destination(payload: CreateJobInput, request: Request) -> Path:
    directories = request.app.state.output_directories
    if payload.destination_mode == "default":
        return directories.get_default()
    if not payload.destination_token:
        raise HTTPException(status_code=409, detail="\u4fdd\u5b58\u4f4d\u7f6e\u5c1a\u672a\u6821\u9a8c")
    try:
        return directories.resolve_token(
            payload.destination_token,
            session_id=request.app.state.local_session.value,
        )
    except PermissionError as error:
        raise HTTPException(status_code=409, detail="\u4fdd\u5b58\u4f4d\u7f6e\u5c1a\u672a\u6821\u9a8c") from error


@router.get("", response_model=tuple[JobResponse, ...])
def list_jobs(request: Request):
    service: DistillationService = request.app.state.service
    return tuple(_job_response(view) for view in service.list_jobs())


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, request: Request):
    service: DistillationService = request.app.state.service
    return _job_response(service.get_job(job_id))


@router.get("/{job_id}/details", response_model=JobDetailsResponse, dependencies=[Depends(require_local_session)])
def job_details(job_id: str, request: Request):
    return _delivery_details(job_id, request)


@router.post("/{job_id}/reveal-output", status_code=204, dependencies=[Depends(require_mutation_security)])
def reveal_output(job_id: str, request: Request) -> Response:
    details = _delivery_details(job_id, request)
    try:
        request.app.state.reveal_directory(Path(details.destination))
    except OSError as error:
        raise HTTPException(status_code=409, detail="打开保存位置失败") from error
    return Response(status_code=204)


@router.get("/{job_id}/items", response_model=tuple[ItemResponse, ...])
def list_items(job_id: str, request: Request):
    service: DistillationService = request.app.state.service
    state = service.queries.get(job_id)
    return tuple(
        ItemResponse(
            source_id=item.source_id,
            display_title=_item_title(state, item.source_id),
            part_number=_item_part_number(state, item.source_id),
            processing_status=item.processing_status.value,
            retryable=item.processing_status in {ProcessingStatus.FAILED, ProcessingStatus.RETRY_WAIT},
            stage_progress=item.stage_progress,
            overall_progress=item.overall_progress,
            last_error=item.last_error,
            updated_at=item.updated_at,
        )
        for item in state.items.values()
    )


def _catalog_metadata(state, source_id: str) -> dict[str, object]:
    value = state.catalog.get(source_id)
    return dict(value) if isinstance(value, dict) else {}


def _item_title(state, source_id: str) -> str:
    value = _catalog_metadata(state, source_id).get("title")
    return value.strip() if isinstance(value, str) and value.strip() else source_id


def _item_part_number(state, source_id: str) -> int | None:
    value = _catalog_metadata(state, source_id).get("part_number")
    return value if isinstance(value, int) and value >= 1 else None


@router.post("/{job_id}/pause", response_model=JobResponse, dependencies=[Depends(require_mutation_security)])
def pause(job_id: str, payload: RevisionInput, request: Request):
    controlled = _controlled_series(job_id, payload.expected_revision, request)
    if controlled is not None:
        request.app.state.series_controller.pause(controlled)
        request.app.state.series_task_monitor.bridge.sync()
        return _job_response(request.app.state.service.get_job(job_id))
    return _job_response(request.app.state.service.pause(job_id, payload.expected_revision))


@router.post("/{job_id}/resume", response_model=JobResponse, dependencies=[Depends(require_mutation_security)])
def resume(job_id: str, payload: RevisionInput, request: Request):
    controlled = _controlled_series(job_id, payload.expected_revision, request)
    if controlled is not None:
        request.app.state.series_controller.resume(controlled)
        request.app.state.series_task_monitor.bridge.sync()
        return _job_response(request.app.state.service.get_job(job_id))
    return _job_response(request.app.state.service.resume(job_id, payload.expected_revision))


def _controlled_series(job_id: str, expected_revision: int, request: Request) -> str | None:
    state = request.app.state.service.queries.get(job_id)
    if state.revision != expected_revision:
        raise RevisionConflict(expected_revision, state.revision)
    if not state.request.get("controlled_series"):
        return None
    if request.app.state.series_controller is None:
        raise RuntimeError("local series control is unavailable")
    return str(state.creator.get("creator_id") or "")


@router.post("/{job_id}/retry-failed", response_model=JobResponse, dependencies=[Depends(require_mutation_security)])
def retry_failed(job_id: str, payload: RevisionInput, request: Request):
    return _job_response(request.app.state.service.retry_failed(job_id, payload.expected_revision))


@router.post("/{job_id}/items/{source_id}/retry", response_model=JobResponse, dependencies=[Depends(require_mutation_security)])
def retry_item(job_id: str, source_id: str, payload: RevisionInput, request: Request):
    return _job_response(request.app.state.service.retry_item(job_id, source_id, payload.expected_revision))
