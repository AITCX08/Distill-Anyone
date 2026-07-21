import pytest

from src.distillation.artifacts import ArtifactRecord, sha256_file
from src.distillation.state import (
    ItemState,
    JobState,
    ProcessingStatus,
    RevisionConflict,
    StateCorruptionError,
    UnsupportedStateVersionError,
    recover_item,
)
from src.distillation.store import JobStateStore


def artifact(tmp_path, name: str, content: bytes = b"valid") -> ArtifactRecord:
    path = tmp_path / name
    path.write_bytes(content)
    return ArtifactRecord(
        path=str(path),
        sha256=sha256_file(path),
        size_bytes=len(content),
        valid=True,
    )


def test_corrupt_state_is_not_treated_as_new_job(tmp_path):
    path = tmp_path / "job_state.json"
    path.write_text("{broken", "utf-8")

    with pytest.raises(StateCorruptionError):
        JobStateStore(path).load()


def test_future_schema_is_rejected_without_rewriting(tmp_path):
    path = tmp_path / "job_state.json"
    original = '{"schema_version": 999, "job_id": "future"}'
    path.write_text(original, "utf-8")

    with pytest.raises(UnsupportedStateVersionError):
        JobStateStore(path).load()

    assert path.read_text("utf-8") == original


def test_known_legacy_schema_is_migrated_and_persisted_atomically(tmp_path):
    path = tmp_path / "job_state.json"
    path.write_text('{"job_id": "legacy", "items": {}}', "utf-8")

    state = JobStateStore(path).load()

    assert state.schema_version == 1
    assert '"schema_version": 1' in path.read_text("utf-8")


def test_every_save_increments_revision_and_detects_conflict(tmp_path):
    store = JobStateStore(tmp_path / "job_state.json")
    first = store.save(JobState(job_id="job-1"))
    second = store.save(first, expected_revision=first.revision)

    assert first.revision == 1
    assert second.revision == 2
    assert store.load().revision == 2

    with pytest.raises(RevisionConflict):
        store.save(second, expected_revision=1)


def test_state_round_trip_preserves_item_and_artifact(tmp_path):
    transcript = artifact(tmp_path, "transcript.txt")
    item = ItemState(
        source_id="douyin_1",
        processing_status=ProcessingStatus.CLEANING,
        artifacts={"transcript": transcript},
        attempts={"download": 1, "asr": 2},
    )
    state = JobState(
        job_id="job-1",
        request={"emit": ["episodes", "skill"]},
        creator={"platform": "douyin", "creator_id": "creator-1"},
        items={item.source_id: item},
    )

    loaded = JobStateStore(tmp_path / "job_state.json").save(state)
    loaded = JobStateStore(tmp_path / "job_state.json").load()

    assert loaded.items["douyin_1"].processing_status is ProcessingStatus.CLEANING
    assert loaded.items["douyin_1"].attempts["asr"] == 2
    assert loaded.items["douyin_1"].artifacts["transcript"] == transcript


def test_completed_item_with_invalid_transcript_recovers_to_transcribing(tmp_path):
    transcript = artifact(tmp_path, "transcript.txt")
    (tmp_path / "transcript.txt").write_bytes(b"corrupt after recording")
    state = ItemState(
        source_id="douyin_1",
        processing_status=ProcessingStatus.COMPLETED,
        artifacts={
            "transcript": transcript,
            "cleaned": artifact(tmp_path, "cleaned.json"),
            "knowledge": artifact(tmp_path, "knowledge.json"),
        },
        transcript_verified=True,
    )

    recovered = recover_item(state)

    assert recovered.processing_status is ProcessingStatus.TRANSCRIBING
    assert recovered.transcript_verified is False


def test_interrupted_item_resumes_from_last_valid_artifact(tmp_path):
    state = ItemState(
        source_id="douyin_1",
        processing_status=ProcessingStatus.WRITING,
        artifacts={
            "transcript": artifact(tmp_path, "transcript.txt"),
            "cleaned": artifact(tmp_path, "cleaned.json"),
        },
        transcript_verified=True,
    )

    recovered = recover_item(state)

    assert recovered.processing_status is ProcessingStatus.SUMMARIZING


def test_unsupported_item_remains_terminal(tmp_path):
    state = ItemState(
        source_id="douyin_note",
        processing_status=ProcessingStatus.UNSUPPORTED,
        last_error="unsupported_note: OCR is not enabled",
    )

    assert recover_item(state) == state
