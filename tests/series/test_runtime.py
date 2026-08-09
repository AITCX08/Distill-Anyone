from src.series.runtime import SeriesRuntimeStore


def test_update_is_atomic_and_monotonic(tmp_path):
    store = SeriesRuntimeStore(tmp_path)

    assert store.update(status="running", active_part=7, stage="downloading")["revision"] == 1
    updated = store.update(
        transfer={"completed_bytes": 25, "total_bytes": 100, "bytes_per_second": 5.0}
    )

    assert updated["revision"] == 2
    assert store.load()["transfer"]["total_bytes"] == 100


def test_pause_and_bounded_trace(tmp_path):
    store = SeriesRuntimeStore(tmp_path, trace_limit=2)
    store.append_trace("info", "one")
    store.append_trace("info", "two")

    assert [item["message"] for item in store.append_trace("info", "three")["trace"]] == [
        "two",
        "three",
    ]
    store.update(status="pause_requested")

    assert store.pause_requested() is True
