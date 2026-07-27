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
from src.outputs.rag import RagTarget
from src.outputs.registry import OutputRegistry
from src.outputs.skill import SkillTarget, corpus_fingerprint

__all__ = [
    "ArtifactKind",
    "CorpusOutputContext",
    "EpisodeMarkdownTarget",
    "ItemOutputContext",
    "OutputManager",
    "OutputReceipt",
    "OutputRegistry",
    "OutputTarget",
    "RagTarget",
    "SkillTarget",
    "corpus_fingerprint",
]
