"""Local Dashboard API tests for revisioned worker task controls."""

from src.orchestration.manager import TaskManager
from src.orchestration.store import OrchestrationStore
from tests.dashboard.test_app import make_client


def _seed_running_task(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid/creator")
    task = store.create_tasks(job.job_id, ["p01"])[0]
    task = store.transition_task(task.task_id, task.revision, status="running")
    store.create_lease(task.task_id, pid=123, start_marker="test-marker")
    return store, task


def test_pause_task_requires_current_revision(tmp_path):
    store, task = _seed_running_task(tmp_path)
    client = make_client(tmp_path)
    client.app.state.task_manager = TaskManager(store=store, worker_root=tmp_path / "workers")
    client.get("/api/v1/health")
    csrf = client.cookies.get("distill_csrf")

    response = client.post(
        f"/api/v1/tasks/{task.task_id}/pause",
        json={"expected_revision": task.revision, "command_id": "cmd_123e4567-e89b-12d3-a456-426614174000"},
        headers={"Origin": "http://testserver", "X-Distill-CSRF": csrf},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pause_requested"
