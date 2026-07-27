from fastapi.testclient import TestClient

from src.application.commands import CreateJobRequest, PreviewResult
from src.application.queries import JobRepository
from src.application.service import DistillationService
from src.dashboard.app import create_dashboard_app


def make_job_client(tmp_path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("dashboard", encoding="utf-8")
    preview = PreviewResult(
        fingerprint="preview-1",
        platform="bilibili",
        creator_id="creator-1",
        creator_name="Creator",
        total_items=1,
        processable_items=1,
    )
    service = DistillationService(
        repository=JobRepository(tmp_path / "jobs"), previewer=lambda request: preview
    )
    return TestClient(create_dashboard_app(service, static_dir, "test")), service


def mutation_headers(client):
    client.get("/api/v1/health")
    return {"Origin": "http://testserver", "X-Distill-CSRF": client.cookies["distill_csrf"]}


def test_preview_never_creates_a_job_and_invalid_input_is_schema_rejected(tmp_path):
    client, service = make_job_client(tmp_path)

    preview = client.post(
        "/api/v1/jobs/preview",
        json={"target": "https://space.bilibili.com/1", "outputs": ["episodes", "skill"]},
        headers=mutation_headers(client),
    )
    malformed = client.post("/api/v1/jobs/preview", json={}, headers=mutation_headers(client))

    assert preview.status_code == 200
    assert preview.json()["fingerprint"] == "preview-1"
    assert service.list_jobs() == ()
    assert malformed.status_code == 422


def test_stale_revision_maps_to_a_safe_conflict_code(tmp_path):
    client, service = make_job_client(tmp_path)
    created = service.create(
        CreateJobRequest(
            target="https://space.bilibili.com/1", preview_fingerprint="preview-1", job_id="job-1"
        )
    )

    response = client.post(
        "/api/v1/jobs/job-1/pause",
        json={"expected_revision": created.revision + 1},
        headers=mutation_headers(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "revision_conflict"


def test_domain_errors_use_stable_codes_without_raw_exception_text(tmp_path):
    client, _ = make_job_client(tmp_path)

    response = client.get("/api/v1/jobs/no-such-job")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "job_not_found", "retryable": False}}
