import json

from src.application.events import EventHub
from src.dashboard.series_bridge import SeriesTaskBridge
from src.distillation.store import JobStateStore


def test_series_bridge_projects_running_eight_part_series_as_read_only_dashboard_job(tmp_path):
    data_dir = tmp_path / "data"
    source_state = data_dir / "series" / "BV18bLkztE7R" / "state.json"
    source_state.parent.mkdir(parents=True)
    source_state.write_text(
        json.dumps(
            {
                "bvid": "BV18bLkztE7R",
                "source_url": "https://www.bilibili.com/video/BV18bLkztE7R",
                "title": "倪海厦《天纪·四柱命卦》(8集全)",
                "owner": "程心学",
                "parts": {
                    "1": {
                        "title": "四柱命卦 1",
                        "source_id": "bilibili_BV18bLkztE7R_p01",
                        "duration_seconds": 2155,
                        "stage": "transcribing",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    events = EventHub()

    bridge = SeriesTaskBridge(data_dir=data_dir, events=events)

    assert bridge.sync() == 1

    store = JobStateStore(data_dir / "jobs" / "imported-series" / "BV18bLkztE7R" / "job_state.json")
    state = store.load()
    assert state.status == "running"
    assert state.request["read_only"] is True
    assert len(state.items) == 8
    assert state.items["bilibili_BV18bLkztE7R_p01"].processing_status.value == "transcribing"
    assert state.items["bilibili_BV18bLkztE7R_p08"].processing_status.value == "enumerated"

    snapshots = [event for event in events.snapshot() if event.event_type == "progress.snapshot"]
    assert len(snapshots) == 1
    snapshot = snapshots[0].payload["snapshot"]
    assert snapshot.counts.total == 8
    assert snapshot.counts.active == 1
    assert snapshot.active_items[0].title == "四柱命卦 1"
