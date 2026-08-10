from pathlib import Path

from fastapi.testclient import TestClient

from src.application.commands import PreviewResult
from src.application.queries import JobRepository
from src.application.service import DistillationService
from src.dashboard.app import create_dashboard_app


def _client(tmp_path: Path) -> TestClient:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<main>Dashboard shell</main>", encoding="utf-8")
    preview = PreviewResult(
        fingerprint="preview-1",
        platform="bilibili",
        creator_id="creator-1",
        creator_name="Creator",
        total_items=1,
        processable_items=1,
    )
    service = DistillationService(
        repository=JobRepository(tmp_path / "jobs"),
        previewer=lambda _: preview,
    )
    return TestClient(create_dashboard_app(service, static_dir, session_secret="test-session"))


def _mutation_headers(client: TestClient) -> dict[str, str]:
    client.get("/api/v1/health")
    return {
        "Origin": "http://testserver",
        "X-Distill-CSRF": client.cookies.get("distill_csrf"),
    }


def test_create_job_with_override_uses_resolved_token_but_never_returns_path(tmp_path):
    client = _client(tmp_path)
    destination = tmp_path / "delivery"
    token = client.app.state.output_directories.validate(str(destination)).token

    response = client.post(
        "/api/v1/jobs",
        json={
            "target": "https://example.invalid/creator",
            "preview_fingerprint": "preview-1",
            "destination_mode": "override",
            "destination_token": token,
        },
        headers=_mutation_headers(client),
    )

    assert response.status_code == 200
    assert "output_directory" not in response.json()
    assert str(destination) not in response.text
    state = client.app.state.service.queries.get(response.json()["job_id"])
    assert state.request["output_directory"] == str(destination)


def test_create_job_copies_the_current_default_directory(tmp_path):
    client = _client(tmp_path)
    default = tmp_path / "default-delivery"
    client.app.state.output_directories.set_default(str(default))

    response = client.post(
        "/api/v1/jobs",
        json={"target": "https://example.invalid/creator", "preview_fingerprint": "preview-1"},
        headers=_mutation_headers(client),
    )

    assert response.status_code == 200
    state = client.app.state.service.queries.get(response.json()["job_id"])
    assert state.request["output_directory"] == str(default)


def test_create_job_rejects_an_unvalidated_override_directory(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/api/v1/jobs",
        json={
            "target": "https://example.invalid/creator",
            "preview_fingerprint": "preview-1",
            "destination_mode": "override",
        },
        headers=_mutation_headers(client),
    )

    assert response.status_code == 409
    assert "directory" not in response.text.lower()
