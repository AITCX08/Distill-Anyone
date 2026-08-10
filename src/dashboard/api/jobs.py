"""Versioned job query and mutation endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from src.application.commands import CreateJobRequest, JobView, PreviewRequest, PreviewResult
from src.application.service import DistillationService
from src.dashboard.schemas import (
    CreateJobInput,
    ItemResponse,
    JobResponse,
    PreviewInput,
    PreviewResponse,
    RevisionInput,
)
from src.dashboard.security import require_mutation_security
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


@router.get("/{job_id}/items", response_model=tuple[ItemResponse, ...])
def list_items(job_id: str, request: Request):
    service: DistillationService = request.app.state.service
    return tuple(
        ItemResponse(
            source_id=item.source_id,
            processing_status=item.processing_status.value,
            retryable=item.processing_status in {ProcessingStatus.FAILED, ProcessingStatus.RETRY_WAIT},
            stage_progress=item.stage_progress,
            overall_progress=item.overall_progress,
            last_error=item.last_error,
            updated_at=item.updated_at,
        )
        for item in service.queries.items(job_id).values()
    )


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
