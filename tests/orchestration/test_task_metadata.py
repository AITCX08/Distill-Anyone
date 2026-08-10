"""Readable, non-sensitive task metadata contracts."""

from src.orchestration.bilibili_import import BilibiliSeriesImporter
from src.orchestration.store import OrchestrationStore


def test_imported_bilibili_task_prefers_part_title_and_has_human_fallback(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    result = BilibiliSeriesImporter(store).import_series(
        "BV18bLkztE7R",
        legacy_state={
            "bvid": "BV18bLkztE7R",
            "title": "课程（2 集）",
            "parts": {
                "1": {"stage": "completed", "title": "开场与概念"},
                "2": {"stage": "pending"},
            },
        },
    )

    tasks = [task for task in store.list_tasks() if task.job_id == result.job_id]

    assert tasks[0].display_title == "开场与概念"
    assert tasks[0].part_number == 1
    assert tasks[1].display_title == "第 2 集"
    assert tasks[1].part_number == 2


def test_existing_source_id_gets_a_safe_bilibili_part_title_fallback(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")

    task = store.create_tasks(job.job_id, ["bilibili_BV18bLkztE7R_p07"])[0]

    assert task.display_title == "第 7 集"
    assert task.part_number == 7
