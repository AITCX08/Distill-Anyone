"""Typed records exposed by the durable orchestration store."""

from __future__ import annotations

from dataclasses import dataclass
import re
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
    output_directory: str = ""


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
    display_title: str = ""
    part_number: int | None = None


@dataclass(frozen=True)
class TaskSpec:
    source_id: str
    display_title: str = ""
    part_number: int | None = None


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


_BILIBILI_PART = re.compile(r"^bilibili_[A-Za-z0-9]+_p(?P<part>\d+)$")


def task_metadata(source_id: str, *, display_title: str = "", part_number: int | None = None) -> tuple[str, int | None]:
    """Return safe readable metadata without exposing source internals as a heading."""

    derived_part = part_number
    if derived_part is None:
        match = _BILIBILI_PART.match(source_id)
        if match is not None:
            derived_part = int(match.group("part"))
    title = display_title.strip()
    if title:
        return title, derived_part
    if derived_part is not None:
        return f"第 {derived_part} 集", derived_part
    return source_id, None


def display_title_for(task: TaskRecord) -> str:
    return task_metadata(
        task.source_id,
        display_title=task.display_title,
        part_number=task.part_number,
    )[0]
