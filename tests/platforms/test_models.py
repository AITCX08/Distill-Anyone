from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from src.platforms.models import ItemType, SourceAsset, SourceItem


def make_item(*, platform: str = "douyin", item_id: str = "123") -> SourceItem:
    return SourceItem(
        platform=platform,
        item_id=item_id,
        creator_id="creator-1",
        item_type=ItemType.VIDEO,
        title="Test item",
        description="Description",
        canonical_url="https://example.test/item/123",
        published_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        duration_seconds=90.0,
        statistics={"likes": 10},
        cover_url="https://example.test/cover.jpg",
        tags=("knowledge",),
        assets=(SourceAsset(kind="video", url="https://example.test/video.mp4"),),
        raw_metadata={"platform_field": "value"},
    )


def test_source_id_is_platform_qualified():
    item = make_item(platform="douyin", item_id="123")

    assert item.source_id == "douyin_123"


def test_source_item_is_immutable():
    item = make_item()

    with pytest.raises(FrozenInstanceError):
        item.title = "Changed"


@pytest.mark.parametrize("platform,item_id", [("", "1"), ("douyin", ""), ("bad/name", "1")])
def test_source_item_rejects_invalid_stable_identifiers(platform, item_id):
    with pytest.raises(ValueError):
        make_item(platform=platform, item_id=item_id)
