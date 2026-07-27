from datetime import datetime, timezone

from src.application.event_log import SanitizedEventLog
from src.application.events import ApplicationEvent


def test_event_log_persists_only_redacted_records_and_rotates(tmp_path):
    log = SanitizedEventLog(tmp_path / "events.jsonl", max_bytes=100, backups=2)
    event = ApplicationEvent(
        event_id=1,
        event_type="trace.appended",
        timestamp=datetime.now(timezone.utc),
        payload={"line": "SESSDATA=not-for-disk"},
    )

    log.append(event)
    log.append(event)

    persisted = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.glob("events.jsonl*"))
    assert "not-for-disk" not in persisted
    assert "[REDACTED]" in persisted
    assert (tmp_path / "events.jsonl.1").exists()
