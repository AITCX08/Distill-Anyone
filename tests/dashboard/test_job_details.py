from pathlib import Path

from fastapi.testclient import TestClient

from src.application.queries import JobRepository
from src.application.service import DistillationService
from src.dashboard.app import create_dashboard_app
from src.dashboard.sse import _snapshot_message
from src.distillation.artifacts import ArtifactRecord, sha256_file
from src.distillation.state import ItemState, JobState, ProcessingStatus


def _client_with_delivery(tmp_path: Path) -> tuple[TestClient, Path]:
    root = tmp_path / "jobs"
    destination = tmp_path / "delivery"
    destination.mkdir()
    artifact_path = root / "safe.md"
    artifact_path.parent.mkdir()
    artifact_path.write_text("# Safe artifact", encoding="utf-8")
    repository = JobRepository(root)
    store = repository.register("job-1", platform="douyin", creator_id="creator-1")
    record = ArtifactRecord(
        path=str(artifact_path), sha256=sha256_file(artifact_path), size_bytes=artifact_path.stat().st_size
    )
    store.save(JobState(
        job_id="job-1",
        status="completed",
        request={"output_directory": str(destination)},
        creator={"platform": "douyin", "creator_id": "creator-1", "display_name": "创作者甲"},
        catalog={"douyin_1": {"title": "作品标题"}},
        items={"douyin_1": ItemState(
            source_id="douyin_1", processing_status=ProcessingStatus.COMPLETED,
            artifacts={"episode": record}, completed_at="2026-08-10T00:00:00+00:00",
        )},
    ))
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("dashboard", encoding="utf-8")
    return TestClient(create_dashboard_app(DistillationService(repository=repository), static_dir, "test")), destination


def _mutation_headers(client: TestClient) -> dict[str, str]:
    return {"Origin": "http://testserver", "X-Distill-CSRF": client.cookies["distill_csrf"]}


def test_job_details_return_destination_only_from_the_private_details_route(tmp_path):
    client, destination = _client_with_delivery(tmp_path)

    assert client.get("/api/v1/jobs/job-1/details").status_code == 403
    client.get("/api/v1/health")
    details = client.get("/api/v1/jobs/job-1/details")
    jobs = client.get("/api/v1/jobs")
    snapshot = _snapshot_message(client.app.state.service, None)

    assert details.status_code == 200
    assert details.json()["destination"] == str(destination.resolve())
    assert details.json()["display_title"] == "作品标题"
    assert str(destination) not in jobs.text
    assert str(destination) not in snapshot


def test_reveal_output_uses_only_the_job_allowlisted_destination(tmp_path):
    client, destination = _client_with_delivery(tmp_path)
    revealed: list[Path] = []
    client.app.state.reveal_directory = revealed.append
    client.get("/api/v1/health")

    response = client.post("/api/v1/jobs/job-1/reveal-output", headers=_mutation_headers(client))

    assert response.status_code == 204
    assert revealed == [destination.resolve()]
    assert str(destination) not in response.text
