"""Versioned state models and deterministic interruption recovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from src.distillation.artifacts import ArtifactRecord, verify_artifact


CURRENT_SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateCorruptionError(RuntimeError):
    def __init__(self, path: Path, message: str = "State file is corrupt"):
        super().__init__(f"{message}: {path}")
        self.path = path


class UnsupportedStateVersionError(RuntimeError):
    def __init__(self, version: int):
        super().__init__(
            f"State schema {version} is newer than supported schema {CURRENT_SCHEMA_VERSION}"
        )
        self.version = version


class RevisionConflict(RuntimeError):
    def __init__(self, expected: int, actual: int | None):
        super().__init__(f"State revision conflict: expected {expected}, actual {actual}")
        self.expected = expected
        self.actual = actual


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    ENUMERATED = "enumerated"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    CLEANING = "cleaning"
    SUMMARIZING = "summarizing"
    WRITING = "writing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_WAIT = "retry_wait"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ItemState:
    source_id: str
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    stage_progress: float = 0.0
    overall_progress: float = 0.0
    attempts: Mapping[str, int] = field(default_factory=dict)
    last_error: str | None = None
    artifacts: Mapping[str, ArtifactRecord] = field(default_factory=dict)
    outputs: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    transcript_verified: bool = False
    temporary_media_cleaned: bool = False
    started_at: str | None = None
    updated_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ItemState":
        artifacts = {
            name: ArtifactRecord.from_dict(record)
            for name, record in dict(value.get("artifacts", {})).items()
        }
        return cls(
            source_id=str(value["source_id"]),
            processing_status=ProcessingStatus(value.get("processing_status", "pending")),
            stage_progress=float(value.get("stage_progress", 0.0)),
            overall_progress=float(value.get("overall_progress", 0.0)),
            attempts={str(k): int(v) for k, v in dict(value.get("attempts", {})).items()},
            last_error=value.get("last_error"),
            artifacts=artifacts,
            outputs=dict(value.get("outputs", {})),
            transcript_verified=bool(value.get("transcript_verified", False)),
            temporary_media_cleaned=bool(value.get("temporary_media_cleaned", False)),
            started_at=value.get("started_at"),
            updated_at=str(value.get("updated_at") or utc_now_iso()),
            completed_at=value.get("completed_at"),
        )


@dataclass(frozen=True)
class JobState:
    job_id: str
    schema_version: int = CURRENT_SCHEMA_VERSION
    revision: int = 0
    status: str = "created"
    request: Mapping[str, Any] = field(default_factory=dict)
    creator: Mapping[str, Any] = field(default_factory=dict)
    enumeration_checkpoint: Mapping[str, Any] = field(default_factory=dict)
    items: Mapping[str, ItemState] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    metrics: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "JobState":
        items = {
            source_id: ItemState.from_dict(item)
            for source_id, item in dict(value.get("items", {})).items()
        }
        return cls(
            job_id=str(value["job_id"]),
            schema_version=int(value.get("schema_version", CURRENT_SCHEMA_VERSION)),
            revision=int(value.get("revision", 0)),
            status=str(value.get("status", "created")),
            request=dict(value.get("request", {})),
            creator=dict(value.get("creator", {})),
            enumeration_checkpoint=dict(value.get("enumeration_checkpoint", {})),
            items=items,
            outputs=dict(value.get("outputs", {})),
            metrics=dict(value.get("metrics", {})),
            created_at=str(value.get("created_at") or utc_now_iso()),
            updated_at=str(value.get("updated_at") or utc_now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for item in value["items"].values():
            status = item["processing_status"]
            item["processing_status"] = status.value if isinstance(status, Enum) else status
        return value


def migrate_state(value: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate known older dictionaries without mutating the input."""

    migrated = dict(value)
    version = int(migrated.get("schema_version", 0))
    if version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedStateVersionError(version)
    if version == 0:
        migrated.setdefault("revision", 0)
        migrated.setdefault("items", {})
        migrated.setdefault("outputs", {})
        migrated.setdefault("metrics", {})
        migrated["schema_version"] = 1
        version = 1
    if version != CURRENT_SCHEMA_VERSION:
        raise UnsupportedStateVersionError(version)
    return migrated


def _valid(state: ItemState, name: str) -> bool:
    record = state.artifacts.get(name)
    return record is not None and verify_artifact(record)


def recover_item(state: ItemState) -> ItemState:
    """Return the earliest safe stage implied by verified durable artifacts."""

    if state.processing_status is ProcessingStatus.UNSUPPORTED:
        return state

    transcript_valid = state.transcript_verified and _valid(state, "transcript")
    if transcript_valid:
        if not _valid(state, "cleaned"):
            status = ProcessingStatus.CLEANING
        elif not _valid(state, "knowledge"):
            status = ProcessingStatus.SUMMARIZING
        elif state.processing_status is ProcessingStatus.COMPLETED:
            status = ProcessingStatus.COMPLETED
        else:
            status = ProcessingStatus.WRITING
        return replace(state, processing_status=status, updated_at=utc_now_iso())

    late_stages = {
        ProcessingStatus.TRANSCRIBING,
        ProcessingStatus.CLEANING,
        ProcessingStatus.SUMMARIZING,
        ProcessingStatus.WRITING,
        ProcessingStatus.COMPLETED,
        ProcessingStatus.FAILED,
        ProcessingStatus.RETRY_WAIT,
    }
    if state.processing_status in late_stages:
        return replace(
            state,
            processing_status=ProcessingStatus.TRANSCRIBING,
            transcript_verified=False,
            updated_at=utc_now_iso(),
            completed_at=None,
        )
    return state
