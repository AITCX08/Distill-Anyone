import json

from src.application.events import EventHub
from src.dashboard.series_bridge import SeriesTaskBridge
from src.distillation.store import JobStateStore
from src.orchestration.store import OrchestrationStore


def test_series_bridge_projects_running_eight_part_series_as_read_only_dashboard_job(tmp_path):
    data_dir = tmp_path / "data"
    source_state = data_dir / "series" / "BV18bLkztE7R" / "state.json"
    source_state.parent.mkdir(parents=True)
    source_state.write_text(
        json.dumps(
            {
                "bvid": "BV18bLkztE7R",
                "source_url": "https://www.bilibili.com/video/BV18bLkztE7R",
                "output_directory": str(data_dir / "delivery"),
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
    (source_state.parent / "runtime.json").write_text(
        json.dumps(
            {
                "status": "running",
                "revision": 4,
                "active_part": 1,
                "stage": "downloading",
                "transfer": {"completed_bytes": 50, "total_bytes": 100, "bytes_per_second": 10.0},
                "trace": [{"level": "info", "message": "Downloading part 1."}],
            }
        ),
        encoding="utf-8",
    )
    events = EventHub()

    bridge = SeriesTaskBridge(data_dir=data_dir, events=events)

    assert bridge.sync() == 1

    store = JobStateStore(data_dir / "jobs" / "imported-series" / "BV18bLkztE7R" / "job_state.json")
    state = store.load()
    assert state.status == "running"
    assert state.request["controlled_series"] is True
    assert state.request["output_directory"] == str(data_dir / "delivery")
    assert state.catalog["bilibili_BV18bLkztE7R_p01"] == {
        "title": "四柱命卦 1",
        "part_number": 1,
    }
    assert len(state.items) == 8
    assert state.items["bilibili_BV18bLkztE7R_p01"].processing_status.value == "downloading"
    assert state.items["bilibili_BV18bLkztE7R_p08"].processing_status.value == "enumerated"

    snapshots = [event for event in events.snapshot() if event.event_type == "progress.snapshot"]
    assert len(snapshots) == 1
    snapshot = snapshots[0].payload["snapshot"]
    assert snapshot.counts.total == 8
    assert snapshot.counts.active == 1
    assert snapshot.active_items[0].completed_bytes == 50
    assert snapshot.active_items[0].total_bytes == 100
    assert snapshot.active_items[0].bytes_per_second == 10.0
    assert snapshot.active_items[0].title == "四柱命卦 1"


def test_series_bridge_hides_active_work_when_the_series_is_paused(tmp_path):
    data_dir = tmp_path / "data"
    source_state = data_dir / "series" / "BV18bLkztE7R" / "state.json"
    source_state.parent.mkdir(parents=True)
    source_state.write_text(
        json.dumps(
            {
                "bvid": "BV18bLkztE7R",
                "title": "八集系列",
                "parts": {"7": {"stage": "extracting_knowledge"}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (source_state.parent / "runtime.json").write_text(
        json.dumps({"status": "paused", "active_part": 7, "stage": "extracting_knowledge"}),
        encoding="utf-8",
    )
    events = EventHub()

    assert SeriesTaskBridge(data_dir=data_dir, events=events).sync() == 1

    snapshot = [event for event in events.snapshot() if event.event_type == "progress.snapshot"][0].payload["snapshot"]
    assert snapshot.counts.active == 0
    assert snapshot.active_items == ()


def test_series_bridge_marks_the_stopped_active_part_as_failed(tmp_path):
    data_dir = tmp_path / "data"
    source_state = data_dir / "series" / "BV18bLkztE7R" / "state.json"
    source_state.parent.mkdir(parents=True)
    source_state.write_text(
        json.dumps(
            {
                "bvid": "BV18bLkztE7R",
                "title": "八集系列",
                "parts": {"7": {"title": "知识提取", "stage": "extracting_knowledge"}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (source_state.parent / "runtime.json").write_text(
        json.dumps(
            {
                "status": "paused",
                "active_part": 7,
                "stage": "extracting_knowledge",
                "last_error": "执行器已停止，可继续任务。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert SeriesTaskBridge(data_dir=data_dir, events=EventHub()).sync() == 1

    state = JobStateStore(data_dir / "jobs" / "imported-series" / "BV18bLkztE7R" / "job_state.json").load()
    item = state.items["bilibili_BV18bLkztE7R_p07"]
    assert state.status == "paused"
    assert item.processing_status.value == "failed"
    assert item.last_error == "执行器已停止，可继续任务。"


def test_series_bridge_skips_a_series_already_migrated_to_worker_tasks(tmp_path):
    data_dir = tmp_path / "data"
    source_state = data_dir / "series" / "BV18bLkztE7R" / "state.json"
    source_state.parent.mkdir(parents=True)
    source_state.write_text(
        json.dumps({"bvid": "BV18bLkztE7R", "parts": {"1": {"stage": "pending"}}}),
        encoding="utf-8",
    )
    store = OrchestrationStore(data_dir / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://www.bilibili.com/video/BV18bLkztE7R")
    store.create_tasks(job.job_id, ["bilibili_BV18bLkztE7R_p01"])

    bridge = SeriesTaskBridge(data_dir=data_dir, events=EventHub(), orchestration_store=store)

    assert bridge.sync() == 0
    assert not (data_dir / "jobs" / "imported-series" / "BV18bLkztE7R" / "job_state.json").exists()


def test_series_bridge_keeps_an_existing_legacy_projection_authoritative(tmp_path):
    data_dir = tmp_path / "data"
    source_state = data_dir / "series" / "BV18bLkztE7R" / "state.json"
    source_state.parent.mkdir(parents=True)
    source_state.write_text(
        json.dumps(
            {
                "bvid": "BV18bLkztE7R",
                "title": "八集系列",
                "parts": {"7": {"title": "知识提取", "stage": "extracting_knowledge"}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    bridge = SeriesTaskBridge(data_dir=data_dir, events=EventHub())
    assert bridge.sync() == 1

    store = OrchestrationStore(data_dir / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://www.bilibili.com/video/BV18bLkztE7R")
    store.create_tasks(job.job_id, ["bilibili_BV18bLkztE7R_p07"])
    (source_state.parent / "runtime.json").write_text(
        json.dumps(
            {
                "status": "paused",
                "active_part": 7,
                "stage": "extracting_knowledge",
                "last_error": "执行器已停止，可继续任务。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert SeriesTaskBridge(data_dir=data_dir, events=EventHub(), orchestration_store=store).sync() == 1
    state = JobStateStore(data_dir / "jobs" / "imported-series" / "BV18bLkztE7R" / "job_state.json").load()
    assert state.status == "paused"
    assert state.items["bilibili_BV18bLkztE7R_p07"].last_error == "执行器已停止，可继续任务。"


def test_series_bridge_serializes_repeated_syncs(tmp_path):
    data_dir = tmp_path / "data"
    source_state = data_dir / "series" / "BV18bLkztE7R" / "state.json"
    source_state.parent.mkdir(parents=True)
    source_state.write_text(
        json.dumps({"bvid": "BV18bLkztE7R", "parts": {"1": {"stage": "pending"}}}),
        encoding="utf-8",
    )
    bridge = SeriesTaskBridge(data_dir=data_dir, events=EventHub())

    assert bridge.sync() == 1
    assert bridge.sync() == 0
