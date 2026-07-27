import asyncio
from types import SimpleNamespace

from src.application.events import EventHub
from src.dashboard.sse import event_stream
from src.distillation.progress import ProgressCounts, ProgressSnapshot


def test_event_stream_replays_last_event_id_and_uses_named_events():
    hub = EventHub()
    hub.publish("job.updated", {"job_id": "job-1", "revision": 2})
    service = SimpleNamespace(events=hub, list_jobs=lambda: ())

    async def next_message():
        stream = event_stream(service, last_event_id=0, job_id="job-1", heartbeat_seconds=0.01)
        return await anext(stream)

    message = asyncio.run(next_message())

    assert "event: job.updated" in message
    assert "id: 1" in message


def test_sse_serializes_real_progress_snapshot_payloads():
    hub = EventHub()
    snapshot = ProgressSnapshot(
        job_id="job-1", revision=2, overall_progress=0.5, coverage=0.25,
        active_items=(), counts=ProgressCounts(total=4, active=1),
        eta_total_seconds=60, eta_active_slowest_seconds=30, provisional_eta=False,
    )
    event = hub.publish("progress.snapshot", {"job_id": "job-1", "snapshot": snapshot})
    service = SimpleNamespace(events=hub, list_jobs=lambda: ())

    async def next_message():
        return await anext(event_stream(service, last_event_id=0, job_id="job-1", heartbeat_seconds=0.01))

    message = asyncio.run(next_message())
    assert '"overall_progress": 0.5' in message


def test_initial_sse_snapshot_includes_latest_progress_for_reconnecting_browser():
    hub = EventHub()
    progress = ProgressSnapshot(
        job_id="job-1", revision=2, overall_progress=0.5, coverage=0.25,
        active_items=(), counts=ProgressCounts(total=4, active=1),
        eta_total_seconds=60, eta_active_slowest_seconds=30, provisional_eta=False,
    )
    hub.publish("progress.snapshot", {"job_id": "job-1", "snapshot": progress})
    service = SimpleNamespace(events=hub, list_jobs=lambda: ())

    async def next_message():
        return await anext(event_stream(service, last_event_id=None, job_id="job-1"))

    message = asyncio.run(next_message())

    assert "event: snapshot" in message
    assert '"overall_progress": 0.5' in message
