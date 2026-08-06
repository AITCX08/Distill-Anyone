"""Project externally running local series work into read-only Dashboard jobs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Event, Thread
from typing import Any

from src.application.events import EventHub
from src.distillation.progress import ItemProgress, ProgressCounts, ProgressSnapshot
from src.distillation.state import ItemState, JobState, ProcessingStatus, utc_now_iso
from src.distillation.store import JobStateStore

_PART_COUNT = re.compile(r"(\d+)\s*集")
_STAGES = {
    "downloading": (ProcessingStatus.DOWNLOADING, 0.0),
    "downloaded": (ProcessingStatus.DOWNLOADED, 0.15),
    "extracting_audio": (ProcessingStatus.EXTRACTING_AUDIO, 0.15),
    "transcribing": (ProcessingStatus.TRANSCRIBING, 0.2),
    "cleaning": (ProcessingStatus.CLEANING, 0.65),
    "extracting_knowledge": (ProcessingStatus.SUMMARIZING, 0.8),
    "summarizing": (ProcessingStatus.SUMMARIZING, 0.8),
    "writing": (ProcessingStatus.WRITING, 0.95),
    "completed": (ProcessingStatus.COMPLETED, 1.0),
    "failed": (ProcessingStatus.FAILED, 0.0),
}
_ACTIVE = {
    ProcessingStatus.DOWNLOADING,
    ProcessingStatus.DOWNLOADED,
    ProcessingStatus.EXTRACTING_AUDIO,
    ProcessingStatus.TRANSCRIBING,
    ProcessingStatus.CLEANING,
    ProcessingStatus.SUMMARIZING,
    ProcessingStatus.WRITING,
}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _expected_parts(raw: dict[str, Any]) -> int:
    title = str(raw.get("title") or "")
    match = _PART_COUNT.search(title)
    if match:
        return max(1, int(match.group(1)))
    parts = raw.get("parts")
    if isinstance(parts, dict):
        numeric = [int(key) for key in parts if str(key).isdigit()]
        if numeric:
            return max(numeric)
    return 1


def _job_status(raw: dict[str, Any], items: dict[str, ItemState]) -> str:
    stage = str(raw.get("stage") or "").lower()
    if stage == "completed":
        return "completed"
    if stage == "failed":
        return "failed"
    completed = sum(item.processing_status is ProcessingStatus.COMPLETED for item in items.values())
    failed = sum(item.processing_status is ProcessingStatus.FAILED for item in items.values())
    if failed and completed:
        return "partial"
    if failed:
        return "failed"
    return "running"


class SeriesTaskBridge:
    """Mirror `data/series/*/state.json` into standard, read-only job states."""

    def __init__(self, *, data_dir: Path, events: EventHub) -> None:
        self.data_dir = data_dir
        self.events = events
        self._seen_fingerprints: dict[Path, str] = {}

    def sync(self) -> int:
        """Synchronize changed external series states and return their count."""

        root = self.data_dir / "series"
        if not root.is_dir():
            return 0
        changed = 0
        for state_path in root.glob("*/state.json"):
            raw = _read_json(state_path)
            if raw is None:
                continue
            fingerprint = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if self._seen_fingerprints.get(state_path) == fingerprint:
                continue
            if self._project(raw):
                changed += 1
                self._seen_fingerprints[state_path] = fingerprint
        return changed

    def _project(self, raw: dict[str, Any]) -> bool:
        bvid = str(raw.get("bvid") or "").strip()
        if not bvid:
            return False
        title = str(raw.get("title") or bvid)
        owner = str(raw.get("owner") or "Bilibili series")
        source_url = str(raw.get("source_url") or f"https://www.bilibili.com/video/{bvid}")
        parts = raw.get("parts") if isinstance(raw.get("parts"), dict) else {}
        count = _expected_parts(raw)
        items: dict[str, ItemState] = {}
        titles: dict[str, str] = {}
        for part in range(1, count + 1):
            value = parts.get(str(part), {})
            value = value if isinstance(value, dict) else {}
            source_id = str(value.get("source_id") or f"bilibili_{bvid}_p{part:02d}")
            stage = str(value.get("stage") or "enumerated").lower()
            status, progress = _STAGES.get(stage, (ProcessingStatus.ENUMERATED, 0.0))
            items[source_id] = ItemState(
                source_id=source_id,
                processing_status=status,
                stage_progress=1.0 if status is ProcessingStatus.COMPLETED else 0.0,
                overall_progress=progress,
                last_error=str(value.get("error")) if value.get("error") else None,
                started_at=raw.get("started_at"),
                completed_at=value.get("completed_at"),
                updated_at=str(raw.get("updated_at") or utc_now_iso()),
            )
            titles[source_id] = str(value.get("title") or f"第 {part:02d} 集（待处理）")

        job_id = f"imported-series-{bvid}"
        store = JobStateStore(self.data_dir / "jobs" / "imported-series" / bvid / "job_state.json")
        existing = store.load() if store.path.exists() else None
        state = JobState(
            job_id=job_id,
            status=_job_status(raw, items),
            request={
                "target": source_url,
                "platform": "bilibili",
                "outputs": ("skill",),
                "read_only": True,
                "external_state": str((self.data_dir / "series" / bvid / "state.json")),
            },
            creator={
                "platform": "imported-series",
                "creator_id": bvid,
                "display_name": title,
                "owner_name": owner,
                "canonical_url": source_url,
            },
            items=items,
            metrics={"external": True, "part_count": count},
            created_at=str(raw.get("started_at") or utc_now_iso()),
        )
        saved = store.save(state, expected_revision=existing.revision if existing else None)
        self.events.publish(
            "job.updated",
            {
                "job_id": saved.job_id,
                "status": saved.status,
                "revision": saved.revision,
                "read_only": True,
            },
        )
        self.events.publish(
            "progress.snapshot",
            {"job_id": saved.job_id, "snapshot": self._snapshot(saved, titles)},
        )
        return True

    @staticmethod
    def _snapshot(state: JobState, titles: dict[str, str]) -> ProgressSnapshot:
        values = tuple(state.items.values())
        active = [
            ItemProgress(
                source_id=item.source_id,
                title=titles.get(item.source_id, item.source_id),
                row_id=index,
                stage=item.processing_status.value,
                stage_progress=item.stage_progress,
                overall_progress=item.overall_progress,
                status_text=item.last_error or "",
            )
            for index, item in enumerate(values, start=1)
            if item.processing_status in _ACTIVE
        ]
        total = len(values)
        completed = sum(item.processing_status is ProcessingStatus.COMPLETED for item in values)
        failed = sum(item.processing_status is ProcessingStatus.FAILED for item in values)
        queued = sum(item.processing_status in {ProcessingStatus.PENDING, ProcessingStatus.ENUMERATED} for item in values)
        return ProgressSnapshot(
            job_id=state.job_id,
            revision=state.revision,
            overall_progress=(sum(item.overall_progress for item in values) / total if total else 0.0),
            coverage=(completed / total if total else 0.0),
            active_items=tuple(active),
            counts=ProgressCounts(
                total=total,
                enumerated=total,
                queued=queued,
                active=len(active),
                completed=completed,
                failed=failed,
            ),
            eta_total_seconds=None,
            eta_active_slowest_seconds=None,
            provisional_eta=True,
        )


class SeriesTaskMonitor:
    """Poll an external series runner without coupling it to the Dashboard process."""

    def __init__(self, bridge: SeriesTaskBridge, *, interval_seconds: float = 1.0) -> None:
        self.bridge = bridge
        self.interval_seconds = interval_seconds
        self._stop = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        self.bridge.sync()
        self._thread = Thread(target=self._run, daemon=True, name="distill-series-dashboard-monitor")
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.bridge.sync()

    def stop(self) -> None:
        self._stop.set()
