"""SQLite-backed authority for orchestration jobs, tasks, and safe event history."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from src.application.redaction import redact_value
from src.distillation.state import RevisionConflict, utc_now_iso
from src.orchestration.models import JobRecord, TaskEventRecord, TaskRecord, WorkerLeaseRecord


class OrchestrationStore:
    """Durable, revision-checked store used by the future task manager."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    target TEXT NOT NULL,
                    status TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES jobs(job_id),
                    source_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    attempt INTEGER NOT NULL,
                    checkpoint_revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(job_id, source_id)
                );
                CREATE TABLE IF NOT EXISTS task_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    sequence INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(task_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS worker_leases (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(task_id),
                    pid INTEGER NOT NULL,
                    start_marker TEXT NOT NULL,
                    launched_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_commands (
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    command_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, command_id)
                );
                CREATE TABLE IF NOT EXISTS task_manager_ownership (
                    singleton TEXT PRIMARY KEY CHECK(singleton = 'dashboard'),
                    owner_id TEXT NOT NULL,
                    pid INTEGER NOT NULL,
                    start_marker TEXT NOT NULL,
                    claimed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS worker_event_cursors (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(task_id),
                    line_count INTEGER NOT NULL CHECK(line_count >= 0),
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_job_id ON tasks(job_id);
                CREATE INDEX IF NOT EXISTS idx_task_events_task_sequence
                    ON task_events(task_id, sequence);
                """
            )

    def create_job(self, *, platform: str, target: str) -> JobRecord:
        if not platform.strip() or not target.strip():
            raise ValueError("platform and target are required")
        now = utc_now_iso()
        job = JobRecord(
            job_id=f"job_{uuid.uuid4().hex}",
            platform=platform,
            target=target,
            status="queued",
            revision=0,
            created_at=now,
            updated_at=now,
        )
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO jobs
                   (job_id, platform, target, status, revision, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.job_id,
                    job.platform,
                    job.target,
                    job.status,
                    job.revision,
                    job.created_at,
                    job.updated_at,
                ),
            )
        return job

    def create_tasks(self, job_id: str, source_ids: Sequence[str]) -> tuple[TaskRecord, ...]:
        if not source_ids or any(not source_id.strip() for source_id in source_ids):
            raise ValueError("at least one non-empty source_id is required")
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source_ids must be unique within a job")
        now = utc_now_iso()
        tasks = tuple(
            TaskRecord(
                task_id=f"task_{uuid.uuid4().hex}",
                job_id=job_id,
                source_id=source_id,
                status="pending",
                stage="queued",
                revision=0,
                attempt=0,
                checkpoint_revision=0,
                created_at=now,
                updated_at=now,
            )
            for source_id in source_ids
        )
        with self._connection() as connection:
            if connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone() is None:
                raise KeyError(f"unknown job: {job_id}")
            connection.executemany(
                """INSERT INTO tasks
                   (task_id, job_id, source_id, status, stage, revision, attempt,
                    checkpoint_revision, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        task.task_id,
                        task.job_id,
                        task.source_id,
                        task.status,
                        task.stage,
                        task.revision,
                        task.attempt,
                        task.checkpoint_revision,
                        task.created_at,
                        task.updated_at,
                    )
                    for task in tasks
                ],
            )
        return tasks

    def list_jobs(self) -> tuple[JobRecord, ...]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM jobs ORDER BY created_at, job_id").fetchall()
        return tuple(self._job_from_row(row) for row in rows)

    def get_job(self, job_id: str) -> JobRecord:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown job: {job_id}")
        return self._job_from_row(row)

    def get_task(self, task_id: str) -> TaskRecord:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown task: {task_id}")
        return self._task_from_row(row)

    def list_tasks(self, *, status: str | None = None) -> tuple[TaskRecord, ...]:
        with self._connection() as connection:
            if status is None:
                rows = connection.execute("SELECT * FROM tasks ORDER BY job_id, source_id").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY job_id, source_id", (status,)
                ).fetchall()
        return tuple(self._task_from_row(row) for row in rows)

    def create_lease(self, task_id: str, *, pid: int, start_marker: str) -> WorkerLeaseRecord:
        if pid <= 0 or not start_marker:
            raise ValueError("lease pid and start marker are required")
        now = utc_now_iso()
        lease = WorkerLeaseRecord(task_id, pid, start_marker, now, now)
        with self._connection() as connection:
            if connection.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)).fetchone() is None:
                raise KeyError(f"unknown task: {task_id}")
            connection.execute(
                """INSERT INTO worker_leases
                   (task_id, pid, start_marker, launched_at, heartbeat_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (lease.task_id, lease.pid, lease.start_marker, lease.launched_at, lease.heartbeat_at),
            )
        return lease

    def get_lease(self, task_id: str) -> WorkerLeaseRecord:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM worker_leases WHERE task_id = ?", (task_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown worker lease: {task_id}")
        return self._lease_from_row(row)

    def list_leases(self) -> tuple[WorkerLeaseRecord, ...]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM worker_leases ORDER BY launched_at").fetchall()
        return tuple(self._lease_from_row(row) for row in rows)

    def remove_lease(self, task_id: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM worker_leases WHERE task_id = ?", (task_id,))

    def transition_task(
        self,
        task_id: str,
        expected_revision: int,
        *,
        status: str,
        stage: str | None = None,
        increment_attempt: bool = False,
    ) -> TaskRecord:
        if not status.strip():
            raise ValueError("status is required")
        now = utc_now_iso()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown task: {task_id}")
            task = self._task_from_row(row)
            if task.revision != expected_revision:
                raise RevisionConflict(expected_revision, task.revision)
            next_stage = stage if stage is not None else task.stage
            next_revision = task.revision + 1
            next_attempt = task.attempt + (1 if increment_attempt else 0)
            connection.execute(
                """UPDATE tasks SET status = ?, stage = ?, revision = ?, attempt = ?, updated_at = ?
                   WHERE task_id = ?""",
                (status, next_stage, next_revision, next_attempt, now, task_id),
            )
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._task_from_row(row)

    def append_event(self, task_id: str, *, kind: str, payload: Mapping[str, Any]) -> TaskEventRecord:
        if not kind.strip():
            raise ValueError("kind is required")
        safe_payload = redact_value(dict(payload))
        now = utc_now_iso()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)).fetchone() is None:
                raise KeyError(f"unknown task: {task_id}")
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM task_events WHERE task_id = ?",
                (task_id,),
            ).fetchone()[0]
            cursor = connection.execute(
                """INSERT INTO task_events (task_id, sequence, kind, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (task_id, sequence, kind, json.dumps(safe_payload, ensure_ascii=False), now),
            )
        return TaskEventRecord(cursor.lastrowid, task_id, sequence, kind, safe_payload, now)

    def list_events(self, task_id: str) -> tuple[TaskEventRecord, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM task_events WHERE task_id = ? ORDER BY sequence",
                (task_id,),
            ).fetchall()
        return tuple(self._event_from_row(row) for row in rows)

    def command_action(self, task_id: str, command_id: str) -> str | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT action FROM task_commands WHERE task_id = ? AND command_id = ?",
                (task_id, command_id),
            ).fetchone()
        return str(row["action"]) if row is not None else None

    def record_command(self, task_id: str, command_id: str, action: str) -> None:
        if not command_id or not action:
            raise ValueError("command id and action are required")
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO task_commands (task_id, command_id, action, created_at)
                   VALUES (?, ?, ?, ?)""",
                (task_id, command_id, action, utc_now_iso()),
            )

    def task_manager_owner(self) -> tuple[str, int, str] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT owner_id, pid, start_marker FROM task_manager_ownership "
                "WHERE singleton = 'dashboard'"
            ).fetchone()
        if row is None:
            return None
        return str(row["owner_id"]), int(row["pid"]), str(row["start_marker"])

    def claim_task_manager(
        self,
        *,
        owner_id: str,
        pid: int,
        start_marker: str,
        replacing_owner_id: str | None = None,
    ) -> bool:
        """Atomically claim the one Dashboard process slot for this data root."""

        if not owner_id or pid <= 0 or not start_marker:
            raise ValueError("task manager ownership fields are required")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT owner_id FROM task_manager_ownership WHERE singleton = 'dashboard'"
            ).fetchone()
            if row is None:
                connection.execute(
                    """INSERT INTO task_manager_ownership
                       (singleton, owner_id, pid, start_marker, claimed_at)
                       VALUES ('dashboard', ?, ?, ?, ?)""",
                    (owner_id, pid, start_marker, utc_now_iso()),
                )
                return True
            if str(row["owner_id"]) == owner_id:
                return True
            if replacing_owner_id is None or str(row["owner_id"]) != replacing_owner_id:
                return False
            cursor = connection.execute(
                """UPDATE task_manager_ownership
                   SET owner_id = ?, pid = ?, start_marker = ?, claimed_at = ?
                   WHERE singleton = 'dashboard' AND owner_id = ?""",
                (owner_id, pid, start_marker, utc_now_iso(), replacing_owner_id),
            )
            return cursor.rowcount == 1

    def release_task_manager(self, owner_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM task_manager_ownership WHERE singleton = 'dashboard' AND owner_id = ?",
                (owner_id,),
            )

    def worker_event_cursor(self, task_id: str) -> int | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT line_count FROM worker_event_cursors WHERE task_id = ?", (task_id,)
            ).fetchone()
        return int(row["line_count"]) if row is not None else None

    def set_worker_event_cursor(self, task_id: str, line_count: int) -> None:
        if line_count < 0:
            raise ValueError("worker event line count cannot be negative")
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO worker_event_cursors (task_id, line_count, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET
                       line_count = excluded.line_count,
                       updated_at = excluded.updated_at""",
                (task_id, line_count, utc_now_iso()),
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"],
            job_id=row["job_id"],
            source_id=row["source_id"],
            status=row["status"],
            stage=row["stage"],
            revision=row["revision"],
            attempt=row["attempt"],
            checkpoint_revision=row["checkpoint_revision"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            platform=row["platform"],
            target=row["target"],
            status=row["status"],
            revision=row["revision"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> TaskEventRecord:
        return TaskEventRecord(
            event_id=row["event_id"],
            task_id=row["task_id"],
            sequence=row["sequence"],
            kind=row["kind"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _lease_from_row(row: sqlite3.Row) -> WorkerLeaseRecord:
        return WorkerLeaseRecord(
            task_id=row["task_id"],
            pid=row["pid"],
            start_marker=row["start_marker"],
            launched_at=row["launched_at"],
            heartbeat_at=row["heartbeat_at"],
        )
