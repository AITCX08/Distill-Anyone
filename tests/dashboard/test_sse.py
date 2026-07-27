import asyncio
from types import SimpleNamespace

from src.application.events import EventHub
from src.dashboard.sse import event_stream


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
