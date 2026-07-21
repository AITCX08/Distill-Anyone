"""Contracts shared by episode, Skill, and RAG outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from src.platforms.models import SourceCreator, SourceItem


class ArtifactKind(str, Enum):
    TRANSCRIPT = "transcript"
    CLEANED = "cleaned"
    KNOWLEDGE = "knowledge"


@dataclass(frozen=True)
class ItemOutputContext:
    item: SourceItem
    creator: SourceCreator
    output_root: Path
    artifacts: Mapping[ArtifactKind, Any]
    processed_at: datetime
    processing_status: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifacts", MappingProxyType(dict(self.artifacts)))


@dataclass(frozen=True)
class CorpusOutputContext:
    creator: SourceCreator
    output_root: Path
    items: tuple[ItemOutputContext, ...] = ()
    previous_fingerprints: Mapping[str, str] = field(default_factory=dict)
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    unsupported_items: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(
            self,
            "previous_fingerprints",
            MappingProxyType(dict(self.previous_fingerprints)),
        )


@dataclass(frozen=True)
class OutputReceipt:
    target: str
    subject_id: str
    path: Path
    fingerprint: str
    skipped: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class OutputTarget(Protocol):
    name: str

    def required_artifacts(self) -> frozenset[ArtifactKind]:
        """Return item artifacts required by this target."""

    def consume_item(self, context: ItemOutputContext) -> OutputReceipt:
        """Write or update an item-level output."""

    def finalize(self, context: CorpusOutputContext) -> OutputReceipt | None:
        """Write a corpus-level output after item processing reaches terminal states."""
