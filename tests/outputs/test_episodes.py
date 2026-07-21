import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from src.outputs.base import ArtifactKind, ItemOutputContext
from src.outputs.episodes import EpisodeMarkdownTarget, creator_output_directory
from src.outputs.files import atomic_write_text
from src.platforms.models import ItemType, SourceCreator, SourceItem


def make_context(tmp_path: Path, *, title: str = "A/B:*?") -> ItemOutputContext:
    creator = SourceCreator(
        platform="douyin",
        creator_id="creator-1",
        display_name="测试/博主:*?",
        canonical_url="https://www.douyin.com/user/creator-1",
    )
    item = SourceItem(
        platform="douyin",
        item_id="123",
        creator_id=creator.creator_id,
        item_type=ItemType.VIDEO,
        title=title,
        description="原始描述",
        canonical_url="https://www.douyin.com/video/123",
        published_at=datetime(2026, 7, 21, 8, 0, tzinfo=timezone.utc),
        duration_seconds=90,
        tags=("产品", "知识"),
    )
    return ItemOutputContext(
        item=item,
        creator=creator,
        output_root=tmp_path,
        artifacts={
            ArtifactKind.TRANSCRIPT: "原始转写正文",
            ArtifactKind.CLEANED: "清洗后的正文",
            ArtifactKind.KNOWLEDGE: {
                "summary": "一句话摘要",
                "key_points": ["知识点一", "知识点二"],
            },
        },
        processed_at=datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc),
        processing_status="completed",
    )


def test_creator_output_directory_is_cross_platform_and_path_safe(tmp_path):
    context = make_context(tmp_path)

    path = creator_output_directory(tmp_path, context.creator)

    assert path.parent == tmp_path
    assert path.name == "测试-博主-douyin-creator-1"


def test_episode_uses_stable_item_id_filename_and_required_fields(tmp_path):
    context = make_context(tmp_path)

    receipt = EpisodeMarkdownTarget(tmp_path).consume_item(context)

    assert receipt.path.name == "123.md"
    assert receipt.path.parent.name == "episodes"
    text = receipt.path.read_text("utf-8")
    for expected in (
        "# A/B:*?",
        "平台: douyin",
        "博主: 测试/博主:*?",
        "作品 ID: 123",
        "原始链接: https://www.douyin.com/video/123",
        "作品类型: video",
        "时长: 90 秒",
        "原始描述",
        "产品, 知识",
        "原始转写正文",
        "清洗后的正文",
        "一句话摘要",
        "知识点一",
        "处理状态: completed",
    ):
        assert expected in text


def test_episode_target_declares_only_shared_artifact_dependencies(tmp_path):
    assert EpisodeMarkdownTarget(tmp_path).required_artifacts() == frozenset(
        {ArtifactKind.TRANSCRIPT, ArtifactKind.CLEANED, ArtifactKind.KNOWLEDGE}
    )


def test_atomic_write_replaces_only_after_validation(tmp_path, monkeypatch):
    target = tmp_path / "episode.md"
    replace = Mock(wraps=os.replace)
    monkeypatch.setattr(os, "replace", replace)

    atomic_write_text(target, "complete", validator=lambda path: path.read_text("utf-8") == "complete")

    assert target.read_text("utf-8") == "complete"
    replace.assert_called_once()
    assert not list(tmp_path.glob("*.tmp"))
