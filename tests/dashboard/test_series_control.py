from unittest.mock import Mock

from src.dashboard.series_control import SeriesController
from src.series.runtime import SeriesRuntimeStore


def test_pause_records_a_cooperative_request(tmp_path):
    state = tmp_path / "series" / "BV1test" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}", encoding="utf-8")
    runtime = SeriesRuntimeStore(tmp_path / "series" / "BV1test")
    runtime.update(status="running")

    paused = SeriesController(tmp_path, launcher=Mock()).pause("BV1test")

    assert paused["status"] == "pause_requested"


def test_resume_launches_one_checkpointed_worker(tmp_path):
    state = tmp_path / "series" / "BV1test" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}", encoding="utf-8")
    runtime = SeriesRuntimeStore(tmp_path / "series" / "BV1test")
    runtime.update(status="paused")
    launcher = Mock()

    resumed = SeriesController(tmp_path, launcher=launcher).resume("BV1test")

    assert resumed["status"] == "running"
    launcher.assert_called_once_with("BV1test")
