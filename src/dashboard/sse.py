"""SSE serialization and redaction for Dashboard event consumers."""

from __future__ import annotations

import json
from asyncio import to_thread
from collections.abc import Mapping
from queue import Empty
from typing import AsyncIterator

from src.application.events import ApplicationEvent
from src.application.redaction import redact_value

_PUBLIC_EVENT_NAMES = {
    "job.item.updated": "item.updated",
    "progress.snapshot": "snapshot",
}


def redact_event(event: ApplicationEvent) -> ApplicationEvent:
    return ApplicationEvent(
        event_id=event.event_id,
        event_type=event.event_type,
        timestamp=event.timestamp,
        payload=redact_value(event.payload),
    )


def serialize_sse(event: ApplicationEvent) -> str:
    safe = redact_event(event)
    payload = {
        "schema_version": 1,
        "timestamp": safe.timestamp.isoformat(),
        "payload": redact_value(safe.payload),
    }
    event_name = _PUBLIC_EVENT_NAMES.get(safe.event_type, safe.event_type)
    return f"id: {safe.event_id}\nevent: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _snapshot_message(service, job_id: str | None, task_manager=None) -> str:
    jobs = []
    for job in service.list_jobs():
        if job_id is None or job.job_id == job_id:
            read_only = False
            queries = getattr(service, "queries", None)
            if queries is not None:
                try:
                    read_only = bool(queries.get(job.job_id).request.get("read_only", False))
                except Exception:
                    read_only = False
            jobs.append(
                {
                    "job_id": job.job_id,
                    "status": job.status.value,
                    "revision": job.revision,
                    "read_only": read_only,
                }
            )
    progress_snapshots = []
    seen_job_ids = set()
    traces: dict[str, list[str]] = {}
    events = service.events.snapshot(job_id=job_id)
    for event in events:
        if event.event_type != "trace.appended":
            continue
        payload = redact_value(event.payload)
        if not isinstance(payload, Mapping):
            continue
        trace_job_id = payload.get("job_id")
        line = payload.get("line")
        if isinstance(trace_job_id, str) and isinstance(line, str):
            traces.setdefault(trace_job_id, []).append(line)
    for event in reversed(events):
        if event.event_type != "progress.snapshot":
            continue
        payload = redact_value(event.payload)
        if not isinstance(payload, Mapping):
            continue
        snapshot = payload.get("snapshot")
        current_job_id = payload.get("job_id")
        if not isinstance(snapshot, Mapping) or not isinstance(current_job_id, str):
            continue
        if current_job_id in seen_job_ids:
            continue
        seen_job_ids.add(current_job_id)
        progress_snapshots.append(snapshot)
    tasks = []
    task_traces: dict[str, list[str]] = {}
    if task_manager is not None:
        for task in task_manager.store.list_tasks():
            if job_id is not None and task.job_id != job_id:
                continue
            task_payload = {
                "task_id": task.task_id,
                "job_id": task.job_id,
                "source_id": task.source_id,
                "display_title": task.display_title,
                "part_number": task.part_number,
                "delivery_state": _delivery_state(task),
                "status": task.status,
                "stage": task.stage,
                "revision": task.revision,
                "attempt": task.attempt,
                "checkpoint_revision": task.checkpoint_revision,
                "updated_at": task.updated_at,
            }
            events = task_manager.store.list_events(task.task_id)
            latest_transfer = next(
                (event.payload for event in reversed(events) if event.kind == "transfer"), None
            )
            latest_terminal = next(
                (event.payload for event in reversed(events) if event.kind == "terminal"), None
            )
            if task.stage == "downloading" and isinstance(latest_transfer, Mapping):
                task_payload["transfer"] = {
                    "completed_bytes": latest_transfer.get("completed_bytes"),
                    "total_bytes": latest_transfer.get("total_bytes"),
                    "bytes_per_second": latest_transfer.get("bytes_per_second"),
                }
            if task.status == "failed" and isinstance(latest_terminal, Mapping):
                reason = latest_terminal.get("reason")
                if isinstance(reason, str):
                    task_payload["error"] = reason
            tasks.append(task_payload)
            lines = [
                str(event.payload.get("line", ""))
                for event in events[-50:]
                if event.kind == "log" and isinstance(event.payload.get("line"), str)
            ]
            if lines:
                task_traces[task.task_id] = lines
    message = {
        "schema_version": 1,
        "jobs": jobs,
        "progress_snapshots": progress_snapshots,
        "traces": traces,
        "tasks": tasks,
        "task_traces": task_traces,
    }
    return f"event: snapshot\ndata: {json.dumps(message, ensure_ascii=False)}\n\n"


def _delivery_state(task) -> str:
    if task.status == "completed":
        return "available"
    if task.status == "failed":
        return "unavailable"
    return "pending"


async def event_stream(
    service,
    last_event_id: int | None,
    job_id: str | None,
    *,
    heartbeat_seconds: float = 15,
    worker_snapshot_seconds: float = 1,
    task_manager=None,
) -> AsyncIterator[str]:
    """Replay safe events, then publish bounded local worker snapshots between heartbeats."""

    events = service.events.snapshot(job_id=job_id)
    oldest_id = events[0].event_id if events else None
    if last_event_id is None or (oldest_id is not None and last_event_id < oldest_id - 1):
        yield _snapshot_message(service, job_id, task_manager)
        last_event_id = events[-1].event_id if events else 0

    subscription = service.events.subscribe(after_id=last_event_id, job_id=job_id, queue_size=100)
    try:
        while True:
            if subscription.needs_snapshot:
                subscription.needs_snapshot = False
                yield _snapshot_message(service, job_id, task_manager)
                continue
            try:
                timeout = min(heartbeat_seconds, worker_snapshot_seconds) if task_manager is not None else heartbeat_seconds
                event = await to_thread(subscription.get, timeout)
            except Empty:
                if task_manager is not None:
                    yield _snapshot_message(service, job_id, task_manager)
                else:
                    yield ": heartbeat\n\n"
                continue
            yield serialize_sse(event)
    finally:
        subscription.close()
