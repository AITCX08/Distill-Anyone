"""Local-only, revision-checked commands for isolated pipeline tasks."""

from fastapi import APIRouter, Depends, HTTPException, Request

from src.dashboard.schemas import TaskCommandInput, TaskResponse
from src.dashboard.security import require_mutation_security
from src.distillation.state import RevisionConflict
from src.orchestration.models import TaskRecord

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


def _response(task: TaskRecord) -> TaskResponse:
    return TaskResponse(
        task_id=task.task_id,
        job_id=task.job_id,
        source_id=task.source_id,
        status=task.status,
        stage=task.stage,
        revision=task.revision,
        attempt=task.attempt,
        checkpoint_revision=task.checkpoint_revision,
        updated_at=task.updated_at,
    )


def _manager(request: Request):
    manager = getattr(request.app.state, "task_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="local task manager is unavailable")
    return manager


def _check_revision(manager, task_id: str, expected_revision: int) -> TaskRecord:
    task = manager.store.get_task(task_id)
    if task.revision != expected_revision:
        raise RevisionConflict(expected_revision, task.revision)
    return task


@router.get("", response_model=tuple[TaskResponse, ...])
def list_tasks(request: Request):
    return tuple(_response(task) for task in _manager(request).store.list_tasks())


@router.post("/{task_id}/pause", response_model=TaskResponse, dependencies=[Depends(require_mutation_security)])
def pause(task_id: str, payload: TaskCommandInput, request: Request):
    manager = _manager(request)
    _check_revision(manager, task_id, payload.expected_revision)
    manager.pause(task_id)
    return _response(manager.store.get_task(task_id))


@router.post("/{task_id}/resume", response_model=TaskResponse, dependencies=[Depends(require_mutation_security)])
def resume(task_id: str, payload: TaskCommandInput, request: Request):
    manager = _manager(request)
    _check_revision(manager, task_id, payload.expected_revision)
    manager.resume(task_id)
    return _response(manager.store.get_task(task_id))


@router.post("/{task_id}/cancel", response_model=TaskResponse, dependencies=[Depends(require_mutation_security)])
def cancel(task_id: str, payload: TaskCommandInput, request: Request):
    manager = _manager(request)
    _check_revision(manager, task_id, payload.expected_revision)
    manager.cancel(task_id)
    return _response(manager.store.get_task(task_id))
