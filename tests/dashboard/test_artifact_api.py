from pathlib import Path

from fastapi.testclient import TestClient

from src.application.queries import JobRepository
from src.application.service import DistillationService
from src.dashboard.app import create_dashboard_app
from src.distillation.artifacts import ArtifactRecord, sha256_file
from src.distillation.state import ItemState, JobState


def test_artifacts_are_resolved_by_allowlisted_ids_and_reject_path_traversal(tmp_path):
    root = tmp_path / "jobs"
    artifact_path = root / "safe.md"
    artifact_path.parent.mkdir()
    artifact_path.write_text("# Safe artifact", encoding="utf-8")
    repository = JobRepository(root)
    store = repository.register("job-1", platform="douyin", creator_id="creator-1")
    record = ArtifactRecord(
        path=str(artifact_path), sha256=sha256_file(artifact_path), size_bytes=artifact_path.stat().st_size
    )
    store.save(JobState(job_id="job-1", items={"douyin_1": ItemState(source_id="douyin_1", artifacts={"episode": record})}))
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("dashboard", encoding="utf-8")
    client = TestClient(create_dashboard_app(DistillationService(repository=repository), static_dir, "test"))

    listed = client.get("/api/v1/jobs/job-1/artifacts")
    artifact_id = listed.json()[0]["artifact_id"]
    read = client.get(f"/api/v1/jobs/job-1/artifacts/{artifact_id}")
    traversal = client.get("/api/v1/jobs/job-1/artifacts/%2E%2E")

    assert read.json()["content"] == "# Safe artifact"
    assert "safe.md" in listed.text
    assert str(root) not in listed.text
    assert traversal.status_code == 403
