"""Render one stable Markdown file per processed source item."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.outputs.base import ArtifactKind, CorpusOutputContext, ItemOutputContext, OutputReceipt
from src.outputs.files import atomic_write_text
from src.platforms.models import SourceCreator


_INVALID_PATH_CHARS = re.compile(r"[<>:\"/\\|?*\x00-\x1f]+")
_REQUIRED_MARKERS = (
    "作品 ID:",
    "## 原始描述",
    "## 转写正文",
    "## 清洗正文",
    "## 摘要与知识点",
)


def _safe_component(value: str, *, fallback: str, max_length: int = 72) -> str:
    cleaned = _INVALID_PATH_CHARS.sub("-", value).strip(" .-")
    cleaned = re.sub(r"\s+", "-", cleaned)
    return (cleaned or fallback)[:max_length].rstrip(" .-")


def creator_output_directory(root: Path, creator: SourceCreator) -> Path:
    name = _safe_component(creator.display_name, fallback="creator")
    platform = _safe_component(creator.platform, fallback="platform")
    creator_id = _safe_component(creator.creator_id, fallback="unknown")
    return root / f"{name}-{platform}-{creator_id}"


def _artifact_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("full_text", "text", "cleaned_text"):
            if value.get(key):
                return str(value[key])
    for attribute in ("full_text", "text", "cleaned_text"):
        candidate = getattr(value, attribute, None)
        if candidate:
            return str(candidate)
    return str(value)


def _knowledge_parts(value: Any) -> tuple[str, Sequence[str]]:
    if isinstance(value, Mapping):
        summary = str(value.get("summary") or value.get("core_idea") or "")
        points = value.get("key_points") or value.get("core_views") or ()
    else:
        summary = str(getattr(value, "summary", "") or getattr(value, "core_idea", ""))
        points = getattr(value, "key_points", ()) or getattr(value, "core_views", ())
    if isinstance(points, str):
        points = (points,)
    return summary, tuple(str(point) for point in points)


def render_episode(context: ItemOutputContext) -> str:
    item = context.item
    transcript = _artifact_text(context.artifacts[ArtifactKind.TRANSCRIPT])
    cleaned = _artifact_text(context.artifacts[ArtifactKind.CLEANED])
    summary, points = _knowledge_parts(context.artifacts[ArtifactKind.KNOWLEDGE])
    published_at = item.published_at.isoformat() if item.published_at else "unknown"
    duration = f"{item.duration_seconds:g} 秒" if item.duration_seconds is not None else "unknown"
    tags = ", ".join(item.tags) if item.tags else "none"
    point_text = "\n".join(f"- {point}" for point in points) or "- none"

    return (
        "---\n"
        "schema_version: 1\n"
        f"平台: {item.platform}\n"
        f"博主: {context.creator.display_name}\n"
        f"博主 ID: {context.creator.creator_id}\n"
        f"作品 ID: {item.item_id}\n"
        f"原始链接: {item.canonical_url}\n"
        f"发布时间: {published_at}\n"
        f"作品类型: {item.item_type.value}\n"
        f"时长: {duration}\n"
        f"标签: {tags}\n"
        f"处理时间: {context.processed_at.isoformat()}\n"
        f"处理状态: {context.processing_status}\n"
        "---\n\n"
        f"# {item.title}\n\n"
        f"## 原始描述\n\n{item.description or 'none'}\n\n"
        f"## 转写正文\n\n{transcript}\n\n"
        f"## 清洗正文\n\n{cleaned}\n\n"
        f"## 摘要与知识点\n\n{summary or 'none'}\n\n{point_text}\n"
    )


def validate_episode_markdown(path: Path) -> bool:
    try:
        text = path.read_text("utf-8")
    except (OSError, UnicodeError):
        return False
    return text.startswith("---\n") and all(marker in text for marker in _REQUIRED_MARKERS)


class EpisodeMarkdownTarget:
    name = "episodes"

    def __init__(self, output_root: Path):
        self._output_root = output_root

    def required_artifacts(self) -> frozenset[ArtifactKind]:
        return frozenset(
            {ArtifactKind.TRANSCRIPT, ArtifactKind.CLEANED, ArtifactKind.KNOWLEDGE}
        )

    def consume_item(self, context: ItemOutputContext) -> OutputReceipt:
        output_dir = creator_output_directory(self._output_root, context.creator) / "episodes"
        path = output_dir / f"{_safe_component(context.item.item_id, fallback='item')}.md"
        content = render_episode(context)
        atomic_write_text(path, content, validator=validate_episode_markdown)
        fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return OutputReceipt(
            target=self.name,
            subject_id=context.item.source_id,
            path=path,
            fingerprint=fingerprint,
        )

    def finalize(self, context: CorpusOutputContext) -> None:
        del context
        return None
