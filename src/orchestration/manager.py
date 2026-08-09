"""The sole owner of hidden worker subprocesses for Dashboard tasks."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from src.orchestration.models import TaskRecord
from src.orchestration.protocol import ProtocolError, parse_worker_event
from src.orchestration.store import OrchestrationStore


ProcessFactory = Callable[[TaskRecord, Path], Any]


class TaskManager:
    """Queue work, create one hidden child process per task, and own its lease."""

    def __init__(
        self,
        *,
        store: OrchestrationStore,
        worker_root: Path,
        process_factory: ProcessFactory | None = None,
        max_pipeline_workers: int = 2,
    ) -> None:
        self.store = store
        self.worker_root = Path(worker_root)
        self.process_factory = process_factory or self._launch_worker
        self.max_pipeline_workers = max_pipeline_workers
        self._processes: dict[str, Any] = {}
        self._event_lines_read: dict[str, int] = {}

    def enqueue(self, job_id: str, source_id: str) -> TaskRecord:
        return self.store.create_tasks(job_id, [source_id])[0]

    def tick(self) -> None:
        capacity = max(0, self.max_pipeline_workers - len(self._processes))
        for task in self.store.list_tasks(status="pending")[:capacity]:
            self.start(task.task_id)

    def start(self, task_id: str) -> TaskRecord:
        if task_id in self._processes:
            return self.store.get_task(task_id)
        task = self.store.get_task(task_id)
        if task.status != "pending":
            raise ValueError("only pending tasks can be started")
        payload_path = self._write_payload(task)
        process = self.process_factory(task, payload_path)
        pid = int(process.pid)
        self.store.create_lease(task.task_id, pid=pid, start_marker=uuid.uuid4().hex)
        running = self.store.transition_task(
            task.task_id,
            task.revision,
            status="running",
            stage="pending",
        )
        self._processes[task.task_id] = process
        self._read_worker_events(task.task_id)
        return running

    def pause(self, task_id: str) -> None:
        raise NotImplementedError("cooperative task controls are added in Task 6")

    def resume(self, task_id: str) -> None:
        raise NotImplementedError("cooperative task controls are added in Task 6")

    def cancel(self, task_id: str) -> None:
        raise NotImplementedError("cooperative task controls are added in Task 6")

    def _write_payload(self, task: TaskRecord) -> Path:
        work_dir = self.worker_root / task.task_id
        work_dir.mkdir(parents=True, exist_ok=True)
        payload_path = work_dir / "payload.json"
        payload_path.write_text(
            json.dumps(
                {"task_id": task.task_id, "work_dir": str(work_dir), "source": {"id": task.source_id}},
                ensure_ascii=False,
            ),
            "utf-8",
        )
        return payload_path

    def _read_worker_events(self, task_id: str) -> None:
        events_path = self.worker_root / task_id / "events.jsonl"
        if not events_path.exists():
            return
        lines = events_path.read_text("utf-8").splitlines()
        start = self._event_lines_read.get(task_id, 0)
        for line in lines[start:]:
            try:
                event = parse_worker_event(line, task_id)
            except ProtocolError:
                continue
            self.store.append_event(task_id, kind=event.kind, payload=event.payload)
        self._event_lines_read[task_id] = len(lines)

    @staticmethod
    def _launch_worker(task: TaskRecord, payload_path: Path) -> subprocess.Popen[str]:
        del task
        return subprocess.Popen(
            [sys.executable, "-m", "src.orchestration.worker", str(payload_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
