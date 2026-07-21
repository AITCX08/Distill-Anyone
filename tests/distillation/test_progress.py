from datetime import datetime, timezone

from src.distillation.progress import (
    ProgressCounts,
    ProgressSnapshot,
    ProgressTracker,
    TransferProgress,
)


def test_same_source_id_keeps_same_active_row():
    tracker = ProgressTracker(job_id="job-1", max_active=3)
    first = tracker.update(
        "douyin_1", title="One", stage="downloading", stage_progress=0.2
    ).row_id
    second = tracker.update(
        "douyin_1", title="One", stage="transcribing", stage_progress=0.1
    ).row_id

    assert first == second
    assert len(tracker.snapshot().active_items) == 1


def test_unsupported_item_prevents_full_completion():
    snapshot = ProgressSnapshot(
        job_id="job-1",
        revision=3,
        overall_progress=0.901,
        coverage=0.9,
        active_items=(),
        counts=ProgressCounts(total=10, completed=9, unsupported=1),
        eta_total_seconds=None,
        eta_active_slowest_seconds=None,
        provisional_eta=False,
    )

    assert snapshot.coverage == 0.9
    assert snapshot.is_complete is False


def test_unknown_download_total_does_not_invent_percentage():
    tracker = ProgressTracker(job_id="job-1")
    progress = TransferProgress(
        source_id="douyin_1",
        completed_bytes=1024,
        total_bytes=None,
        bytes_per_second=512,
        timestamp=datetime.now(timezone.utc),
    )

    item = tracker.update_transfer(progress, title="One")

    assert item.stage_progress is None
    assert item.completed_bytes == 1024
    assert item.total_bytes is None
    assert item.download_eta_seconds is None


def test_transfer_and_terminal_counts_feed_immutable_snapshot():
    tracker = ProgressTracker(job_id="job-1")
    tracker.register("douyin_1", title="One")
    tracker.register("douyin_2", title="Two")
    tracker.update_transfer(
        TransferProgress(
            "douyin_1",
            completed_bytes=50,
            total_bytes=100,
            bytes_per_second=25,
            timestamp=datetime.now(timezone.utc),
        ),
        title="One",
    )
    tracker.update("douyin_2", title="Two", stage="unsupported", terminal=True)

    snapshot = tracker.snapshot(revision=4, enumeration_complete=False)

    assert snapshot.counts.total == 2
    assert snapshot.counts.unsupported == 1
    assert snapshot.active_items[0].download_eta_seconds == 2
    assert snapshot.provisional_eta is True

