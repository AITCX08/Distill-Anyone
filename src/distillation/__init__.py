"""Recoverable distillation state and artifact primitives."""

from src.distillation.artifacts import ArtifactRecord, sha256_file, verify_artifact
from src.distillation.state import ItemState, JobState, ProcessingStatus, recover_item
from src.distillation.store import JobStateStore, atomic_write_bytes, atomic_write_json
from src.distillation.engine import DistillationEngine, JobResult
from src.distillation.request import DistillationRequest
from src.distillation.eta import EtaEstimate, EtaEstimator
from src.distillation.progress import (
    ItemProgress,
    ProgressSnapshot,
    ProgressTracker,
    TransferProgress,
)

__all__ = [
    "ArtifactRecord",
    "DistillationEngine",
    "DistillationRequest",
    "EtaEstimate",
    "EtaEstimator",
    "ItemState",
    "ItemProgress",
    "JobState",
    "JobResult",
    "JobStateStore",
    "ProcessingStatus",
    "ProgressSnapshot",
    "ProgressTracker",
    "TransferProgress",
    "atomic_write_bytes",
    "atomic_write_json",
    "recover_item",
    "sha256_file",
    "verify_artifact",
]
