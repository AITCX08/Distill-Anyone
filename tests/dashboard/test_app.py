from pathlib import Path

from fastapi.testclient import TestClient

from src.application.queries import JobRepository
from src.application.service import DistillationService
from src.dashboard.app import create_dashboard_app


def make_client(tmp_path: Path) -> TestClient:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<main>Dashboard shell</main>", encoding="utf-8")
    service = DistillationService(repository=JobRepository(tmp_path / "jobs"))
    return TestClient(
        create_dashboard_app(
            service=service,
            static_dir=static_dir,
            session_secret="test-session-secret",
        )
    )


def test_health_exposes_only_safe_dashboard_compatibility(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "api_version": "v1",
        "static_compatible": True,
    }
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "test-session-secret" not in response.text


def test_spa_fallback_never_captures_api_routes(tmp_path):
    client = make_client(tmp_path)

    page = client.get("/jobs/local")
    missing_api = client.get("/api/v1/unknown")

    assert page.status_code == 200
    assert page.text == "<main>Dashboard shell</main>"
    assert missing_api.status_code == 404
