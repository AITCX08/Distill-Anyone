"""Idempotent import of old Bilibili series state into ordinary worker tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from src.orchestration.models import TaskRecord, TaskSpec
from src.orchestration.store import OrchestrationStore


@dataclass(frozen=True)
class BilibiliImportResult:
    job_id: str
    created_tasks: int
    completed_tasks: int
    pending_tasks: int


class BilibiliSeriesImporter:
    def __init__(self, store: OrchestrationStore) -> None:
        self.store = store

    def import_series(
        self,
        bvid: str,
        *,
        legacy_state: Mapping[str, Any],
        output_directory: str = "",
    ) -> BilibiliImportResult:
        if str(legacy_state.get("bvid") or bvid) != bvid:
            raise ValueError("legacy state does not match requested Bilibili series")
        source_url = str(
            legacy_state.get("source_url") or f"https://www.bilibili.com/video/{bvid}"
        )
        parts = legacy_state.get("parts")
        if not isinstance(parts, Mapping) or not parts:
            raise ValueError("legacy Bilibili series has no parts")
        existing_parts = {int(number): value for number, value in parts.items() if str(number).isdigit()}
        if not existing_parts:
            raise ValueError("legacy Bilibili series has no numbered parts")
        declared_count = _declared_part_count(str(legacy_state.get("title") or ""))
        part_count = max(max(existing_parts), declared_count or 0)
        numbered = [(number, existing_parts.get(number, {})) for number in range(1, part_count + 1)]
        source_ids = [self._source_id(bvid, number) for number, _ in numbered]
        existing_job = next(
            (job for job in self.store.list_jobs() if job.platform == "bilibili" and job.target == source_url),
            None,
        )
        if existing_job is not None:
            existing = self.store.list_tasks()
            existing_sources = {task.source_id for task in existing if task.job_id == existing_job.job_id}
            if existing_sources != set(source_ids):
                raise ValueError("existing Bilibili job does not match legacy series parts")
            tasks = tuple(task for task in existing if task.job_id == existing_job.job_id)
            return self._result(existing_job.job_id, tasks, created_tasks=0)

        job = self.store.create_job(
            platform="bilibili",
            target=source_url,
            output_directory=output_directory,
        )
        tasks = self.store.create_tasks(
            job.job_id,
            [
                TaskSpec(
                    source_id=self._source_id(bvid, number),
                    display_title=_part_title(value, number),
                    part_number=number,
                )
                for number, value in numbered
            ],
        )
        completed_by_source = {
            self._source_id(bvid, number)
            for number, value in numbered
            if isinstance(value, Mapping) and str(value.get("stage") or "").lower() == "completed"
        }
        migrated: list[TaskRecord] = []
        for task in tasks:
            if task.source_id in completed_by_source:
                task = self.store.transition_task(
                    task.task_id,
                    task.revision,
                    status="completed",
                    stage="completed",
                )
            migrated.append(task)
        return self._result(job.job_id, tuple(migrated), created_tasks=len(migrated))

    @staticmethod
    def _source_id(bvid: str, part: int) -> str:
        return f"bilibili_{bvid}_p{part:02d}"

    @staticmethod
    def _result(job_id: str, tasks: tuple[TaskRecord, ...], *, created_tasks: int) -> BilibiliImportResult:
        completed = sum(task.status == "completed" for task in tasks)
        return BilibiliImportResult(
            job_id=job_id,
            created_tasks=created_tasks,
            completed_tasks=completed,
            pending_tasks=sum(task.status == "pending" for task in tasks),
        )


def _declared_part_count(title: str) -> int | None:
    """Recover a missing trailing part only when the saved series title declares it."""

    match = re.search(r"(\d+)\s*(?:集|episodes?)", title, flags=re.IGNORECASE)
    return int(match.group(1)) if match is not None else None


def _part_title(value: Any, part_number: int) -> str:
    title = str(value.get("title") or "").strip() if isinstance(value, Mapping) else ""
    return title or f"第 {part_number} 集"
