from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from src.model.knowledge_extractor import BloggerProfile, VideoKnowledge
from src.outputs.base import ArtifactKind, CorpusOutputContext, ItemOutputContext
from src.outputs.skill import SkillTarget, corpus_fingerprint
from src.platforms.models import ItemType, SourceCreator, SourceItem


def make_item_context(
    tmp_path: Path,
    item_id: str,
    knowledge: VideoKnowledge,
) -> ItemOutputContext:
    creator = SourceCreator(
        platform="douyin",
        creator_id="creator-1",
        display_name="Creator",
        canonical_url="https://www.douyin.com/user/creator-1",
    )
    item = SourceItem(
        platform="douyin",
        item_id=item_id,
        creator_id=creator.creator_id,
        item_type=ItemType.VIDEO,
        title=f"Item {item_id}",
        description="",
        canonical_url=f"https://www.douyin.com/video/{item_id}",
    )
    return ItemOutputContext(
        item=item,
        creator=creator,
        output_root=tmp_path,
        artifacts={ArtifactKind.KNOWLEDGE: knowledge},
        processed_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        processing_status="completed",
    )


def make_corpus_context(
    tmp_path: Path,
    items: tuple[ItemOutputContext, ...],
    *,
    previous_fingerprint: str = "",
    total: int | None = None,
    completed: int | None = None,
    failed: int = 0,
    unsupported: int = 0,
) -> CorpusOutputContext:
    return CorpusOutputContext(
        creator=items[0].creator,
        output_root=tmp_path,
        items=items,
        previous_fingerprints={"skill": previous_fingerprint},
        total_items=len(items) if total is None else total,
        completed_items=len(items) if completed is None else completed,
        failed_items=failed,
        unsupported_items=unsupported,
    )


def test_corpus_fingerprint_is_order_independent_and_content_sensitive(tmp_path):
    first = make_item_context(
        tmp_path,
        "1",
        VideoKnowledge(source_id="douyin_1", title="One", summary="alpha"),
    )
    second = make_item_context(
        tmp_path,
        "2",
        VideoKnowledge(source_id="douyin_2", title="Two", summary="beta"),
    )

    assert corpus_fingerprint((first, second)) == corpus_fingerprint((second, first))

    changed = make_item_context(
        tmp_path,
        "2",
        VideoKnowledge(source_id="douyin_2", title="Two", summary="changed"),
    )
    assert corpus_fingerprint((first, second)) != corpus_fingerprint((first, changed))


def test_skill_skips_when_corpus_fingerprint_matches(tmp_path):
    item = make_item_context(
        tmp_path,
        "1",
        VideoKnowledge(source_id="douyin_1", title="One", summary="alpha"),
    )
    fingerprint = corpus_fingerprint((item,))
    merge_fn = Mock()
    generator = Mock()
    target = SkillTarget(tmp_path, merge_fn=merge_fn, generator=generator)
    target.skill_path(item.creator).parent.mkdir(parents=True)
    target.skill_path(item.creator).write_text("---\nname: existing\n---\n# Existing\n", "utf-8")

    receipt = target.finalize(
        make_corpus_context(tmp_path, (item,), previous_fingerprint=fingerprint)
    )

    assert receipt.skipped is True
    assert receipt.fingerprint == fingerprint
    merge_fn.assert_not_called()
    generator.generate.assert_not_called()


def test_partial_skill_records_coverage_and_writes_atomically(tmp_path):
    item = make_item_context(
        tmp_path,
        "1",
        VideoKnowledge(source_id="douyin_1", title="One", summary="alpha"),
    )
    merge_fn = Mock(return_value=BloggerProfile(name="Creator", uid=0))
    generator = Mock()
    generator.generate.return_value = "---\nname: creator\n---\n# Creator Skill\n"
    target = SkillTarget(tmp_path, merge_fn=merge_fn, generator=generator)

    receipt = target.finalize(
        make_corpus_context(
            tmp_path,
            (item,),
            total=10,
            completed=8,
            unsupported=2,
        )
    )

    assert receipt.path.read_text("utf-8").endswith("# Creator Skill\n")
    assert receipt.metadata["partial"] is True
    assert receipt.metadata["coverage"] == 0.8
    assert receipt.metadata["total_items"] == 10
    assert receipt.metadata["unsupported_items"] == 2
    merge_fn.assert_called_once_with([item.artifacts[ArtifactKind.KNOWLEDGE]], up_name="Creator", up_uid=0)
