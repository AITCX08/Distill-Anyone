"""Shared progress value objects (tracker and ETA are added by the progress stage)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TransferProgress:
    source_id: str
    completed_bytes: int
    total_bytes: int | None
    bytes_per_second: float
    timestamp: datetime

