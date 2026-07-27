"""Validated execution request for the staged distillation engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.platforms.models import SourceCreator, SourceItem


@dataclass(frozen=True)
class DistillationRequest:
    job_id: str
    creator: SourceCreator
    items: tuple[SourceItem, ...]
    output_root: Path
    download_workers: int = 3
    asr_workers: int = 1
    llm_workers: int = 3
    max_active_items: int = 3
    retry_limit: int = 2
    cleanup_media: bool = True
    resume: bool = True
    retry_failed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        if self.download_workers <= 0 or self.llm_workers <= 0:
            raise ValueError("Worker counts must be positive")
        if self.asr_workers != 1:
            raise ValueError("FunASR is serialized; asr_workers must be 1")
        if self.max_active_items <= 0:
            raise ValueError("max_active_items must be positive")
        if self.retry_limit < 0:
            raise ValueError("retry_limit cannot be negative")
