"""Typed records exposed by the durable orchestration store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    platform: str
    target: str
    status: str
    revision: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    job_id: str
    source_id: str
    status: str
    stage: str
    revision: int
    attempt: int
    checkpoint_revision: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TaskEventRecord:
    event_id: int
    task_id: str
    sequence: int
    kind: str
    payload: Mapping[str, Any]
    created_at: str


@dataclass(frozen=True)
class WorkerLeaseRecord:
    task_id: str
    pid: int
    start_marker: str
    launched_at: str
    heartbeat_at: str
