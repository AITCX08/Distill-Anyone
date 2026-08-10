"""Migration tests for converting legacy Bilibili series into worker tasks."""

from src.orchestration.bilibili_import import BilibiliSeriesImporter
from src.orchestration.store import OrchestrationStore


def test_import_creates_one_task_per_series_part_and_preserves_completed_parts(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    importer = BilibiliSeriesImporter(store)
    legacy_state = {
        "bvid": "BV18bLkztE7R",
        "title": "八集系列",
        "source_url": "https://www.bilibili.com/video/BV18bLkztE7R",
        "parts": {
            str(part): {"stage": "completed" if part <= 6 else "pending", "title": f"第 {part} 集"}
            for part in range(1, 9)
        },
    }

    result = importer.import_series("BV18bLkztE7R", legacy_state=legacy_state)

    assert result.created_tasks == 8
    assert result.completed_tasks == 6
    assert result.pending_tasks == 2
    assert [task.status for task in store.list_tasks()] == ["completed"] * 6 + ["pending"] * 2


def test_import_uses_declared_series_count_to_restore_a_missing_final_part(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    legacy_state = {
        "bvid": "BV18bLkztE7R",
        "title": "8集系列",
        "parts": {
            str(part): {"stage": "completed" if part <= 6 else "extracting_knowledge"}
            for part in range(1, 8)
        },
    }

    result = BilibiliSeriesImporter(store).import_series("BV18bLkztE7R", legacy_state=legacy_state)

    assert result.created_tasks == 8
    assert result.completed_tasks == 6
    assert result.pending_tasks == 2
    assert [task.source_id for task in store.list_tasks()][-2:] == [
        "bilibili_BV18bLkztE7R_p07",
        "bilibili_BV18bLkztE7R_p08",
    ]
