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


def test_import_bilibili_series_creates_independent_tasks_from_local_legacy_state(tmp_path):
    client = make_client(tmp_path)
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    manager = TaskManager(store=store, worker_root=tmp_path / "workers")
    client.app.state.task_manager = manager
    state_dir = tmp_path / "series" / "BV18bLkztE7R"
    state_dir.mkdir(parents=True)
    state_dir.joinpath("state.json").write_text(
        '{"bvid":"BV18bLkztE7R","parts":{"1":{"stage":"completed"},"2":{"stage":"pending"}}}',
        "utf-8",
    )
    client.get("/api/v1/health")
    csrf = client.cookies.get("distill_csrf")

    response = client.post(
        "/api/v1/tasks/import/bilibili",
        json={"bvid": "BV18bLkztE7R"},
        headers={"Origin": "http://testserver", "X-Distill-CSRF": csrf},
    )

    assert response.status_code == 200
    assert response.json()["created_tasks"] == 2
    assert response.json()["completed_tasks"] == 1


def test_retry_interrupted_task_requeues_the_same_task_id(tmp_path):
    client = make_client(tmp_path)
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    manager = TaskManager(store=store, worker_root=tmp_path / "workers")
    client.app.state.task_manager = manager
    job = store.create_job(platform="bilibili", target="https://example.invalid")
    task = store.create_tasks(job.job_id, ["p01"])[0]
    task = store.transition_task(task.task_id, task.revision, status="interrupted", stage="transcribing")
    client.get("/api/v1/health")

    response = client.post(
        f"/api/v1/tasks/{task.task_id}/retry",
        json={"expected_revision": task.revision, "command_id": "retry_task_1"},
        headers={"Origin": "http://testserver", "X-Distill-CSRF": client.cookies.get("distill_csrf")},
    )

    assert response.status_code == 200
    assert response.json()["task_id"] == task.task_id
    assert response.json()["status"] == "pending"

    duplicate = client.post(
        f"/api/v1/tasks/{task.task_id}/retry",
        json={"expected_revision": task.revision, "command_id": "retry_task_1"},
        headers={"Origin": "http://testserver", "X-Distill-CSRF": client.cookies.get("distill_csrf")},
    )

    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "pending"
