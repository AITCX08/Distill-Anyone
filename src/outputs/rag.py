"""Write one platform-neutral RAG chunk document per source item."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.outputs.base import ArtifactKind, CorpusOutputContext, ItemOutputContext, OutputReceipt
from src.outputs.episodes import _safe_component, creator_output_directory
from src.outputs.files import atomic_write_text
from src.rag.chunker import build_chunks


def _cleaned_document(context: ItemOutputContext) -> dict[str, Any]:
    value = context.artifacts[ArtifactKind.CLEANED]
    if isinstance(value, Mapping):
        document = dict(value)
    else:
        document = {
            "title": context.item.title,
            "full_text": str(value),
            "topics": [],
        }
    metadata = dict(document.get("metadata") or {})
    metadata.setdefault("platform", context.item.platform)
    metadata.setdefault("item_type", context.item.item_type.value)
    metadata.setdefault("source_url", context.item.canonical_url)
    document["metadata"] = metadata
    document["source_id"] = context.item.source_id
    document.setdefault("title", context.item.title)
    return document


def _validate_rag_document(path: Path, source_id: str) -> bool:
    try:
        document = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return document.get("source_id") == source_id and isinstance(document.get("chunks"), list)


class RagTarget:
    name = "rag"

    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root

    def required_artifacts(self) -> frozenset[ArtifactKind]:
        return frozenset({ArtifactKind.CLEANED, ArtifactKind.KNOWLEDGE})

    def consume_item(self, context: ItemOutputContext) -> OutputReceipt:
        source_id = context.item.source_id
        document = build_chunks(
            _cleaned_document(context),
            context.artifacts[ArtifactKind.KNOWLEDGE],
        )
        document["source_url"] = context.item.canonical_url
        content = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        path = (
            creator_output_directory(self._output_root, context.creator)
            / "rag"
            / f"{_safe_component(source_id, fallback='source')}.json"
        )
        atomic_write_text(
            path,
            content,
            validator=lambda candidate: _validate_rag_document(candidate, source_id),
        )
        return OutputReceipt(
            target=self.name,
            subject_id=source_id,
            path=path,
            fingerprint=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    def finalize(self, context: CorpusOutputContext) -> None:
        del context
        return None

