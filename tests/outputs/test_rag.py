import json
from datetime import datetime, timezone

from src.model.knowledge_extractor import VideoKnowledge
from src.outputs.base import ArtifactKind, ItemOutputContext
from src.outputs.rag import RagTarget
from src.platforms.models import ItemType, SourceCreator, SourceItem


def test_rag_target_writes_platform_neutral_source_id(tmp_path):
    creator = SourceCreator(
        platform="douyin",
        creator_id="creator-1",
        display_name="Creator",
        canonical_url="https://www.douyin.com/user/creator-1",
    )
    item = SourceItem(
        platform="douyin",
        item_id="123",
        creator_id=creator.creator_id,
        item_type=ItemType.VIDEO,
        title="A Douyin video",
        description="",
        canonical_url="https://www.douyin.com/video/123",
    )
    context = ItemOutputContext(
        item=item,
        creator=creator,
        output_root=tmp_path,
        artifacts={
            ArtifactKind.CLEANED: {
                "title": item.title,
                "full_text": "Reusable knowledge.",
                "topics": [],
            },
            ArtifactKind.KNOWLEDGE: VideoKnowledge(
                source_id=item.source_id,
                title=item.title,
                summary="Summary",
            ),
        },
        processed_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        processing_status="completed",
    )

    receipt = RagTarget(tmp_path).consume_item(context)

    assert receipt.subject_id == "douyin_123"
    assert receipt.path.name == "douyin_123.json"
    document = json.loads(receipt.path.read_text("utf-8"))
    assert document["source_id"] == "douyin_123"
    assert document["source_type"] == "video"
    assert document["source_url"] == item.canonical_url
    assert document["chunks"][0]["chunk_id"].startswith("douyin_123_chunk_")


def test_rag_target_declares_cleaned_and_knowledge_dependencies(tmp_path):
    assert RagTarget(tmp_path).required_artifacts() == frozenset(
        {ArtifactKind.CLEANED, ArtifactKind.KNOWLEDGE}
    )

