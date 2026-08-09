"""Safety tests for task controls and process recovery."""

import json

from src.orchestration.manager import TaskManager
from src.orchestration.store import OrchestrationStore


def _running_task(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")
    task = store.create_tasks(job.job_id, ["p01"])[0]
    task = store.transition_task(task.task_id, task.revision, status="running")
    store.create_lease(task.task_id, pid=123, start_marker="opaque-marker")
    return store, task


def test_restart_marks_missing_leased_process_interrupted_and_resumable(tmp_path):
    store, task = _running_task(tmp_path)
    manager = TaskManager(
        store=store,
        worker_root=tmp_path / "workers",
        pid_probe=lambda pid, marker: False,
    )

    manager.reconcile()

    assert store.get_task(task.task_id).status == "interrupted"


def test_pause_requests_checkpoint_without_killing_an_unowned_process(tmp_path):
    store, task = _running_task(tmp_path)
    manager = TaskManager(store=store, worker_root=tmp_path / "workers")

    manager.pause(task.task_id)

    control = json.loads((tmp_path / "workers" / task.task_id / "control.json").read_text("utf-8"))
    assert control["action"] == "pause"
    assert store.get_task(task.task_id).status == "pause_requested"


def test_restart_reattaches_live_lease_and_consumes_new_worker_jsonl(tmp_path):
    store, task = _running_task(tmp_path)
    probes = [True, False]
    manager = TaskManager(
        store=store,
        worker_root=tmp_path / "workers",
        pid_probe=lambda pid, marker: probes[0],
    )
    worker_dir = tmp_path / "workers" / task.task_id
    worker_dir.mkdir(parents=True)

    manager.reconcile()
    (worker_dir / "events.jsonl").write_text(
        '{"v":1,"type":"stage","task_id":"' + task.task_id + '","stage":"transcribing"}\n',
        "utf-8",
    )
    manager.tick()

    assert store.get_task(task.task_id).stage == "transcribing"
    probes[0] = False
    manager.tick()
    assert store.get_task(task.task_id).status == "interrupted"
    try:
        store.get_lease(task.task_id)
    except KeyError:
        pass
    else:
        raise AssertionError("lost reattached worker lease was not released")
