"""Immutable progress snapshots shared by Rich Live, SSE, and Dashboard."""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Sequence


_TERMINAL = {"completed", "failed", "unsupported"}
_ACTIVE = {
    "downloading",
    "downloaded",
    "extracting_audio",
    "transcribing",
    "cleaning",
    "summarizing",
    "writing",
}
_WEIGHTS = {
    "downloading": (0.00, 0.15),
    "extracting_audio": (0.15, 0.05),
    "transcribing": (0.20, 0.45),
    "cleaning": (0.65, 0.15),
    "summarizing": (0.80, 0.15),
    "writing": (0.95, 0.05),
}


@dataclass(frozen=True)
class TransferProgress:
    source_id: str
    completed_bytes: int
    total_bytes: int | None
    bytes_per_second: float
    timestamp: datetime


@dataclass(frozen=True)
class ItemProgress:
    source_id: str
    title: str
    row_id: int
    stage: str
    stage_progress: float | None
    overall_progress: float
    status_text: str = ""
    completed_bytes: int = 0
    total_bytes: int | None = None
    bytes_per_second: float = 0.0
    download_eta_seconds: float | None = None
    audio_completed_seconds: float = 0.0
    audio_total_seconds: float | None = None
    asr_rtf: float | None = None


@dataclass(frozen=True)
class ProgressCounts:
    total: int = 0
    enumerated: int = 0
    queued: int = 0
    active: int = 0
    completed: int = 0
    failed: int = 0
    retry: int = 0
    unsupported: int = 0


@dataclass(frozen=True)
class ProgressSnapshot:
    job_id: str
    revision: int
    overall_progress: float
    coverage: float
    active_items: Sequence[ItemProgress]
    counts: ProgressCounts
    eta_total_seconds: float | None
    eta_active_slowest_seconds: float | None
    provisional_eta: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "active_items", tuple(self.active_items))

    @property
    def is_complete(self) -> bool:
        return self.counts.total > 0 and self.counts.completed == self.counts.total


def _weighted_progress(stage: str, progress: float | None, previous: float) -> float:
    if stage == "completed":
        return 1.0
    if stage == "unsupported":
        return max(previous, 0.01)
    if stage in {"failed", "retry_wait"}:
        return previous
    if stage == "downloaded":
        return max(previous, 0.15)
    base_weight = _WEIGHTS.get(stage)
    if base_weight is None:
        return previous
    base, weight = base_weight
    if progress is None:
        return max(previous, base)
    return max(previous, min(1.0, base + weight * max(0.0, min(1.0, progress))))


class ProgressTracker:
    def __init__(self, job_id: str, max_active: int = 3):
        self.job_id = job_id
        self.max_active = max_active
        self._items: dict[str, ItemProgress] = {}
        self._next_row_id = 1
        self._lock = threading.RLock()
        self._eta_total_seconds: float | None = None
        self._eta_active_seconds: float | None = None
        self._eta_provisional = False

    def register(self, source_id: str, *, title: str = "") -> ItemProgress:
        with self._lock:
            current = self._items.get(source_id)
            if current is not None:
                return current
            item = ItemProgress(
                source_id=source_id,
                title=title,
                row_id=self._next_row_id,
                stage="queued",
                stage_progress=None,
                overall_progress=0.0,
            )
            self._next_row_id += 1
            self._items[source_id] = item
            return item

    def update(
        self,
        source_id: str,
        *,
        title: str = "",
        stage: str,
        stage_progress: float | None = None,
        status_text: str = "",
        terminal: bool | None = None,
        **metrics,
    ) -> ItemProgress:
        del terminal  # Terminal membership is derived from the canonical stage.
        with self._lock:
            current = self.register(source_id, title=title)
            updated = replace(
                current,
                title=title or current.title,
                stage=stage,
                stage_progress=stage_progress,
                overall_progress=_weighted_progress(
                    stage,
                    stage_progress,
                    current.overall_progress,
                ),
                status_text=status_text,
                **metrics,
            )
            self._items[source_id] = updated
            return updated

    def update_transfer(self, progress: TransferProgress, *, title: str = "") -> ItemProgress:
        stage_progress = None
        eta = None
        if progress.total_bytes is not None and progress.total_bytes > 0:
            stage_progress = min(1.0, progress.completed_bytes / progress.total_bytes)
            if progress.bytes_per_second > 0:
                eta = max(
                    0.0,
                    (progress.total_bytes - progress.completed_bytes)
                    / progress.bytes_per_second,
                )
        return self.update(
            progress.source_id,
            title=title,
            stage="downloading",
            stage_progress=stage_progress,
            completed_bytes=progress.completed_bytes,
            total_bytes=progress.total_bytes,
            bytes_per_second=progress.bytes_per_second,
            download_eta_seconds=eta,
        )

    def update_asr(
        self,
        source_id: str,
        *,
        title: str = "",
        completed_seconds: float,
        total_seconds: float | None,
        elapsed_seconds: float,
    ) -> ItemProgress:
        stage_progress = (
            min(1.0, completed_seconds / total_seconds)
            if total_seconds and total_seconds > 0
            else None
        )
        rtf = elapsed_seconds / completed_seconds if completed_seconds > 0 else None
        return self.update(
            source_id,
            title=title,
            stage="transcribing",
            stage_progress=stage_progress,
            audio_completed_seconds=completed_seconds,
            audio_total_seconds=total_seconds,
            asr_rtf=rtf,
        )

    def set_eta(
        self,
        *,
        total_seconds: float | None,
        active_slowest_seconds: float | None,
        provisional: bool,
    ) -> None:
        with self._lock:
            self._eta_total_seconds = total_seconds
            self._eta_active_seconds = active_slowest_seconds
            self._eta_provisional = provisional

    def snapshot(
        self,
        *,
        revision: int = 0,
        enumeration_complete: bool = True,
    ) -> ProgressSnapshot:
        with self._lock:
            items = tuple(self._items.values())
            active = tuple(
                sorted(
                    (item for item in items if item.stage in _ACTIVE),
                    key=lambda item: item.row_id,
                )[: self.max_active]
            )
            completed = sum(item.stage == "completed" for item in items)
            failed = sum(item.stage == "failed" for item in items)
            retry = sum(item.stage == "retry_wait" for item in items)
            unsupported = sum(item.stage == "unsupported" for item in items)
            queued = sum(item.stage in {"queued", "pending", "enumerated"} for item in items)
            total = len(items)
            counts = ProgressCounts(
                total=total,
                enumerated=total,
                queued=queued,
                active=len(active),
                completed=completed,
                failed=failed,
                retry=retry,
                unsupported=unsupported,
            )
            overall = sum(item.overall_progress for item in items) / total if total else 0.0
            coverage = completed / total if total else 0.0
            return ProgressSnapshot(
                job_id=self.job_id,
                revision=revision,
                overall_progress=overall,
                coverage=coverage,
                active_items=active,
                counts=counts,
                eta_total_seconds=self._eta_total_seconds,
                eta_active_slowest_seconds=self._eta_active_seconds,
                provisional_eta=self._eta_provisional or not enumeration_complete,
            )


class RichProgressView:
    @staticmethod
    def _duration(seconds: float | None) -> str:
        if seconds is None:
            return "--:--"
        rounded = max(0, int(round(seconds)))
        hours, remainder = divmod(rounded, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def render(self, snapshot: ProgressSnapshot):
        from rich.table import Table

        table = Table(title=f"Distillation {snapshot.job_id}")
        provisional = " · estimating" if snapshot.provisional_eta else ""
        table.caption = (
            f"Total ETA {self._duration(snapshot.eta_total_seconds)} · "
            f"Active ETA {self._duration(snapshot.eta_active_slowest_seconds)} · "
            f"Coverage {snapshot.coverage * 100:.1f}%{provisional}"
        )
        table.add_column("Row", justify="right")
        table.add_column("Item")
        table.add_column("Stage")
        table.add_column("Progress", justify="right")
        table.add_column("Transfer", justify="right")
        for item in snapshot.active_items:
            percentage = (
                f"{item.stage_progress * 100:.1f}%"
                if item.stage_progress is not None
                else "estimating"
            )
            transfer = (
                f"{item.completed_bytes}/{item.total_bytes} B"
                if item.total_bytes is not None
                else f"{item.completed_bytes} B"
            )
            table.add_row(str(item.row_id), item.title or item.source_id, item.stage, percentage, transfer)
        return table
