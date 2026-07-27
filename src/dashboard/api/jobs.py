"""Versioned job query and mutation endpoints."""

from fastapi import APIRouter, Depends, Request

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
    return _job_response(service.create(CreateJobRequest(**data)))


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
            stage_progress=item.stage_progress,
            overall_progress=item.overall_progress,
            last_error=item.last_error,
            updated_at=item.updated_at,
        )
        for item in service.queries.items(job_id).values()
    )


@router.post("/{job_id}/pause", response_model=JobResponse, dependencies=[Depends(require_mutation_security)])
def pause(job_id: str, payload: RevisionInput, request: Request):
    return _job_response(request.app.state.service.pause(job_id, payload.expected_revision))


@router.post("/{job_id}/resume", response_model=JobResponse, dependencies=[Depends(require_mutation_security)])
def resume(job_id: str, payload: RevisionInput, request: Request):
    return _job_response(request.app.state.service.resume(job_id, payload.expected_revision))


@router.post("/{job_id}/retry-failed", response_model=JobResponse, dependencies=[Depends(require_mutation_security)])
def retry_failed(job_id: str, payload: RevisionInput, request: Request):
    return _job_response(request.app.state.service.retry_failed(job_id, payload.expected_revision))


@router.post("/{job_id}/items/{source_id}/retry", response_model=JobResponse, dependencies=[Depends(require_mutation_security)])
def retry_item(job_id: str, source_id: str, payload: RevisionInput, request: Request):
    return _job_response(request.app.state.service.retry_item(job_id, source_id, payload.expected_revision))
