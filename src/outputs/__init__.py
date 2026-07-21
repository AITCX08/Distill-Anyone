"""Composable distillation output targets."""

from src.outputs.base import (
    ArtifactKind,
    CorpusOutputContext,
    ItemOutputContext,
    OutputReceipt,
    OutputTarget,
)
from src.outputs.episodes import EpisodeMarkdownTarget
from src.outputs.manager import OutputManager
from src.outputs.registry import OutputRegistry

__all__ = [
    "ArtifactKind",
    "CorpusOutputContext",
    "EpisodeMarkdownTarget",
    "ItemOutputContext",
    "OutputManager",
    "OutputReceipt",
    "OutputRegistry",
    "OutputTarget",
]
