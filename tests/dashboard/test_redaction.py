from datetime import datetime, timezone

from src.application.events import ApplicationEvent
from src.dashboard.sse import redact_event, serialize_sse


def test_sse_redacts_credentials_and_machine_paths_before_serialization():
    event = ApplicationEvent(
        event_id=4,
        event_type="trace.appended",
        timestamp=datetime.now(timezone.utc),
        payload={
            "line": "Cookie: SESSDATA=secret Authorization: Bearer abcdefghijklmnop C:\\Users\\Administrator\\profile",
            "api_key": "sk-secret-123456789",
        },
    )

    serialized = serialize_sse(redact_event(event))

    assert "secret" not in serialized
    assert "Administrator" not in serialized
    assert "sk-secret" not in serialized
    assert "event: trace.appended" in serialized
    assert "id: 4" in serialized


def test_sse_normalizes_engine_item_updates_to_the_public_event_name():
    event = ApplicationEvent(
        event_id=5,
        event_type="job.item.updated",
        timestamp=datetime.now(timezone.utc),
        payload={"job_id": "job-1"},
    )

    assert "event: item.updated" in serialize_sse(event)
