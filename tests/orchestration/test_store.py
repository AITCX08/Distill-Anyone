import pytest

from src.distillation.state import RevisionConflict
from src.orchestration.store import OrchestrationStore


def test_create_tasks_are_independent_and_revisioned(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")

    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")
    first, second = store.create_tasks(job.job_id, ["p01", "p02"])
    paused = store.transition_task(first.task_id, first.revision, status="pause_requested")

    assert job.status == "queued"
    assert first.status == "pending"
    assert paused.status == "pause_requested"
    assert paused.revision == first.revision + 1
    assert store.get_task(second.task_id).status == "pending"
    assert store.get_task(second.task_id).revision == second.revision


def test_task_transition_rejects_stale_revision(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")
    (task,) = store.create_tasks(job.job_id, ["p01"])
    store.transition_task(task.task_id, task.revision, status="running")

    with pytest.raises(RevisionConflict):
        store.transition_task(task.task_id, task.revision, status="pause_requested")


def test_events_are_ordered_per_task_and_redacted_before_storage(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")
    (task,) = store.create_tasks(job.job_id, ["p01"])

    first = store.append_event(task.task_id, kind="log", payload={"line": "SESSDATA=secret"})
    second = store.append_event(task.task_id, kind="stage", payload={"stage": "downloading"})

    assert (first.sequence, second.sequence) == (1, 2)
    assert "secret" not in store.list_events(task.task_id)[0].payload["line"]


def test_job_persists_a_private_output_directory(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    delivery = tmp_path / "delivery"

    job = store.create_job(
        platform="bilibili",
        target="https://example.invalid/creator",
        output_directory=str(delivery),
    )

    assert store.get_job(job.job_id).output_directory == str(delivery)
