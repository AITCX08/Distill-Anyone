"""Local-only, revision-checked commands for isolated pipeline tasks."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from src.dashboard.schemas import (
    BilibiliImportInput,
    BilibiliImportResponse,
    TaskCommandInput,
    TaskResponse,
)
from src.dashboard.security import require_mutation_security
from src.distillation.state import RevisionConflict
from src.orchestration.models import TaskRecord
from src.orchestration.bilibili_import import BilibiliSeriesImporter

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


def _command_or_duplicate(manager, task_id: str, payload: TaskCommandInput, action: str, command) -> TaskRecord:
    existing = manager.store.command_action(task_id, payload.command_id)
    if existing is not None:
        if existing != action:
            raise HTTPException(status_code=409, detail="command id already belongs to another action")
        return manager.store.get_task(task_id)
    _check_revision(manager, task_id, payload.expected_revision)
    command(task_id)
    manager.store.record_command(task_id, payload.command_id, action)
    return manager.store.get_task(task_id)


@router.post("/import/bilibili", response_model=BilibiliImportResponse, dependencies=[Depends(require_mutation_security)])
def import_bilibili(payload: BilibiliImportInput, request: Request):
    manager = _manager(request)
    state_path = manager.worker_root.parent / "series" / payload.bvid / "state.json"
    try:
        legacy_state = json.loads(state_path.read_text("utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise HTTPException(status_code=404, detail="local Bilibili series state was not found") from None
    if not isinstance(legacy_state, dict):
        raise HTTPException(status_code=400, detail="local Bilibili series state is invalid")
    result = BilibiliSeriesImporter(manager.store).import_series(
        payload.bvid,
        legacy_state=legacy_state,
        output_directory=str(request.app.state.output_directories.get_default()),
    )
    return BilibiliImportResponse(**result.__dict__)


@router.get("", response_model=tuple[TaskResponse, ...])
def list_tasks(request: Request):
    return tuple(_response(task) for task in _manager(request).store.list_tasks())


@router.post("/{task_id}/pause", response_model=TaskResponse, dependencies=[Depends(require_mutation_security)])
def pause(task_id: str, payload: TaskCommandInput, request: Request):
    manager = _manager(request)
    return _response(_command_or_duplicate(manager, task_id, payload, "pause", manager.pause))


@router.post("/{task_id}/resume", response_model=TaskResponse, dependencies=[Depends(require_mutation_security)])
def resume(task_id: str, payload: TaskCommandInput, request: Request):
    manager = _manager(request)
    return _response(_command_or_duplicate(manager, task_id, payload, "resume", manager.resume))


@router.post("/{task_id}/cancel", response_model=TaskResponse, dependencies=[Depends(require_mutation_security)])
def cancel(task_id: str, payload: TaskCommandInput, request: Request):
    manager = _manager(request)
    return _response(_command_or_duplicate(manager, task_id, payload, "cancel", manager.cancel))


@router.post("/{task_id}/retry", response_model=TaskResponse, dependencies=[Depends(require_mutation_security)])
def retry(task_id: str, payload: TaskCommandInput, request: Request):
    manager = _manager(request)
    return _response(_command_or_duplicate(manager, task_id, payload, "retry", manager.retry))
