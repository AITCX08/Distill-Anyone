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


def _snapshot_message(service, job_id: str | None) -> str:
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
    for event in reversed(service.events.snapshot(job_id=job_id)):
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
    message = {"schema_version": 1, "jobs": jobs, "progress_snapshots": progress_snapshots}
    return f"event: snapshot\ndata: {json.dumps(message, ensure_ascii=False)}\n\n"


async def event_stream(
    service,
    last_event_id: int | None,
    job_id: str | None,
    *,
    heartbeat_seconds: float = 15,
) -> AsyncIterator[str]:
    """Replay safe events, then wait with a heartbeat and bounded subscription."""

    events = service.events.snapshot(job_id=job_id)
    oldest_id = events[0].event_id if events else None
    if last_event_id is None or (oldest_id is not None and last_event_id < oldest_id - 1):
        yield _snapshot_message(service, job_id)
        last_event_id = events[-1].event_id if events else 0

    subscription = service.events.subscribe(after_id=last_event_id, job_id=job_id, queue_size=100)
    try:
        while True:
            if subscription.needs_snapshot:
                subscription.needs_snapshot = False
                yield _snapshot_message(service, job_id)
                continue
            try:
                event = await to_thread(subscription.get, heartbeat_seconds)
            except Empty:
                yield ": heartbeat\n\n"
                continue
            yield serialize_sse(event)
    finally:
        subscription.close()
