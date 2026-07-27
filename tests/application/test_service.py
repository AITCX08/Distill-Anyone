import pytest
from threading import Event

from src.application.commands import (
    CreateJobRequest,
    JobStatus,
    PreviewResult,
)
from src.application.errors import PreviewChangedError
from src.application.events import EventHub
from src.application.queries import JobRepository
from src.application.service import DistillationService
from src.distillation.state import ItemState, JobState, ProcessingStatus, RevisionConflict


def make_service(tmp_path, *, revision: int = 0, status: str = "running"):
    repository = JobRepository(tmp_path)
    store = repository.register("job-1", platform="douyin", creator_id="creator-1")
    state = JobState(
        job_id="job-1",
        status=status,
        items={
            "douyin_ok": ItemState(
                source_id="douyin_ok",
                processing_status=ProcessingStatus.COMPLETED,
            ),
            "douyin_failed": ItemState(
                source_id="douyin_failed",
                processing_status=ProcessingStatus.FAILED,
                last_error="network",
            ),
        },
    )
    saved = store.save(state)
    while saved.revision < revision:
        saved = store.save(saved, expected_revision=saved.revision)
    hub = EventHub()
    return DistillationService(repository=repository, events=hub), store, hub


def test_pause_rejects_stale_revision(tmp_path):
    service, _, _ = make_service(tmp_path, revision=3)

    with pytest.raises(RevisionConflict):
        service.pause("job-1", expected_revision=2)


def test_pause_is_revisioned_and_publishes_same_view(tmp_path):
    service, store, hub = make_service(tmp_path)
    current = service.get_job("job-1")

    paused = service.pause("job-1", expected_revision=current.revision)

    assert paused.status is JobStatus.PAUSE_REQUESTED
    assert paused.revision == current.revision + 1
    assert store.load().status == "pause_requested"
    event = hub.snapshot()[-1]
    assert event.event_type == "job.updated"
    assert event.payload["revision"] == paused.revision
    assert event.payload["status"] == "pause_requested"


def test_retry_failed_resets_only_failed_items(tmp_path):
    service, store, _ = make_service(tmp_path, status="partial")
    current = service.get_job("job-1")

    retried = service.retry_failed("job-1", expected_revision=current.revision)

    state = store.load()
    assert retried.status is JobStatus.RUNNING
    assert state.items["douyin_ok"].processing_status is ProcessingStatus.COMPLETED
    assert state.items["douyin_failed"].processing_status is ProcessingStatus.TRANSCRIBING
    assert state.items["douyin_failed"].last_error is None


def test_resume_is_idempotent_without_revision_churn(tmp_path):
    service, _, _ = make_service(tmp_path, status="running")
    current = service.get_job("job-1")

    resumed = service.resume("job-1", expected_revision=current.revision)

    assert resumed == current


def test_create_requires_current_preview_fingerprint(tmp_path):
    repository = JobRepository(tmp_path)
    preview = PreviewResult(
        fingerprint="current",
        platform="douyin",
        creator_id="creator-1",
        creator_name="Creator",
        total_items=10,
        processable_items=10,
    )
    service = DistillationService(
        repository=repository,
        previewer=lambda request: preview,
    )

    with pytest.raises(PreviewChangedError):
        service.create(
            CreateJobRequest(
                target="https://www.douyin.com/user/creator-1",
                preview_fingerprint="stale",
            )
        )


def test_create_persists_the_previewed_creator(tmp_path):
    repository = JobRepository(tmp_path)
    preview = PreviewResult(
        fingerprint="current",
        platform="douyin",
        creator_id="creator-1",
        creator_name="Creator",
        total_items=10,
        processable_items=8,
        unsupported_items=2,
    )
    service = DistillationService(repository=repository, previewer=lambda request: preview)

    created = service.create(
        CreateJobRequest(
            target="https://www.douyin.com/user/creator-1",
            preview_fingerprint="current",
            outputs=("episodes", "skill"),
            job_id="job-created",
        )
    )

    assert created.status is JobStatus.QUEUED
    assert created.creator_id == "creator-1"
    assert created.outputs == ("episodes", "skill")
    assert service.get_job("job-created") == created


def test_create_starts_the_configured_source_runner_from_a_verified_preview(tmp_path):
    preview = PreviewResult(
        fingerprint="current",
        platform="douyin",
        creator_id="creator-1",
        creator_name="Creator",
        total_items=1,
        processable_items=1,
    )
    completed = Event()
    source_requests = []

    class DashboardRunner:
        def preview(self, request):
            return preview

        def job_id_for_preview(self, value):
            assert value is preview
            return "dashboard-job"

        def run(self, request):
            source_requests.append(request)
            completed.set()

    service = DistillationService(
        repository=JobRepository(tmp_path),
        source_runner=DashboardRunner(),
    )

    created = service.create(
        CreateJobRequest(
            target="https://fixture.invalid/creator",
            platform="douyin",
            outputs=("episodes", "skill"),
            rag_chunks=True,
            preview_fingerprint="current",
        )
    )

    assert created.job_id == "dashboard-job"
    assert completed.wait(timeout=1)
    assert source_requests[0].target == "https://fixture.invalid/creator"
    assert source_requests[0].platform == "douyin"
    assert source_requests[0].emit == ("episodes", "skill")
    assert source_requests[0].rag_chunks is True


def test_pause_notifies_an_active_source_runner(tmp_path):
    repository = JobRepository(tmp_path)
    store = repository.register("job-1", platform="douyin", creator_id="creator-1")
    saved = store.save(JobState(job_id="job-1", status="running"))
    paused = []
    runner = type("Runner", (), {"request_pause": lambda self, job_id: paused.append(job_id)})()
    service = DistillationService(repository=repository, source_runner=runner)

    result = service.pause("job-1", saved.revision)

    assert result.status is JobStatus.PAUSE_REQUESTED
    assert paused == ["job-1"]


def test_resume_restarts_source_runner_from_persisted_request(tmp_path):
    repository = JobRepository(tmp_path)
    store = repository.register("job-1", platform="douyin", creator_id="creator-1")
    saved = store.save(
        JobState(
            job_id="job-1",
            status="paused",
            request={
                "target": "https://fixture.invalid/creator",
                "platform": "douyin",
                "outputs": ("episodes", "skill"),
                "rag_chunks": True,
            },
            creator={"canonical_url": "https://fixture.invalid/creator"},
        )
    )
    completed = Event()
    source_requests = []

    class Runner:
        def run(self, request):
            source_requests.append(request)
            completed.set()

    service = DistillationService(repository=repository, source_runner=Runner())

    resumed = service.resume("job-1", saved.revision)

    assert resumed.status is JobStatus.RUNNING
    assert completed.wait(timeout=1)
    assert source_requests[0].target == "https://fixture.invalid/creator"
    assert source_requests[0].emit == ("episodes", "skill")
    assert source_requests[0].rag_chunks is True
