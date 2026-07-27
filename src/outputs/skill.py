"""Generate one resumable Skill artifact from a creator corpus."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

from src.outputs.base import ArtifactKind, CorpusOutputContext, ItemOutputContext, OutputReceipt
from src.outputs.episodes import creator_output_directory
from src.outputs.files import atomic_write_text


def _canonical_knowledge(value: Any) -> str:
    if is_dataclass(value):
        value = asdict(value)
    elif isinstance(value, Mapping):
        value = dict(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def corpus_fingerprint(items: Iterable[ItemOutputContext]) -> str:
    """Hash sorted source-id and knowledge-content hash pairs."""

    pairs: list[tuple[str, str]] = []
    for item_context in items:
        knowledge = item_context.artifacts[ArtifactKind.KNOWLEDGE]
        knowledge_hash = hashlib.sha256(_canonical_knowledge(knowledge).encode("utf-8")).hexdigest()
        pairs.append((item_context.item.source_id, knowledge_hash))
    canonical = "\n".join(f"{source_id}:{digest}" for source_id, digest in sorted(pairs))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_skill_markdown(path: Path) -> bool:
    try:
        content = path.read_text("utf-8")
    except (OSError, UnicodeError):
        return False
    return content.startswith("---\n") and "\n---\n" in content[4:] and "\n# " in content


def _with_distillation_metadata(content: str, metadata: Mapping[str, Any]) -> str:
    if not content.startswith("---\n"):
        return content
    lines = [
        "distillation_schema: 1",
        f"corpus_fingerprint: {metadata['corpus_fingerprint']}",
        f"partial: {str(metadata['partial']).lower()}",
        f"coverage: {metadata['coverage']:.6f}",
        f"total_items: {metadata['total_items']}",
        f"completed_items: {metadata['completed_items']}",
        f"failed_items: {metadata['failed_items']}",
        f"unsupported_items: {metadata['unsupported_items']}",
    ]
    return "---\n" + "\n".join(lines) + "\n" + content[4:]


class SkillTarget:
    """Corpus-level output target backed by the existing profile synthesizer."""

    name = "skill"

    def __init__(
        self,
        output_root: Path,
        *,
        merge_fn: Callable[..., Any],
        generator: Any,
    ) -> None:
        self._output_root = output_root
        self.merge_fn = merge_fn
        self.generator = generator

    def skill_path(self, creator) -> Path:
        return creator_output_directory(self._output_root, creator) / "SKILL.md"

    def required_artifacts(self) -> frozenset[ArtifactKind]:
        return frozenset({ArtifactKind.KNOWLEDGE})

    def consume_item(self, context: ItemOutputContext) -> None:
        del context
        return None

    def finalize(self, context: CorpusOutputContext) -> OutputReceipt:
        path = self.skill_path(context.creator)
        fingerprint = corpus_fingerprint(context.items)
        total = context.total_items
        completed = context.completed_items
        coverage = completed / total if total else 1.0
        partial = (
            completed < total
            or context.failed_items > 0
            or context.unsupported_items > 0
        )
        metadata = {
            "corpus_fingerprint": fingerprint,
            "partial": partial,
            "coverage": coverage,
            "total_items": total,
            "completed_items": completed,
            "failed_items": context.failed_items,
            "unsupported_items": context.unsupported_items,
        }

        if context.previous_fingerprints.get(self.name) == fingerprint and path.exists():
            return OutputReceipt(
                target=self.name,
                subject_id="corpus",
                path=path,
                fingerprint=fingerprint,
                skipped=True,
                metadata=metadata,
            )

        knowledge = [item.artifacts[ArtifactKind.KNOWLEDGE] for item in context.items]
        creator_id = context.creator.creator_id
        creator_uid = int(creator_id) if creator_id.isdigit() else 0
        profile = self.merge_fn(
            knowledge,
            up_name=context.creator.display_name,
            up_uid=creator_uid,
        )
        content = self.generator.generate(profile)
        content = _with_distillation_metadata(content, metadata)
        atomic_write_text(path, content, validator=_validate_skill_markdown)
        return OutputReceipt(
            target=self.name,
            subject_id="corpus",
            path=path,
            fingerprint=fingerprint,
            metadata=metadata,
        )
