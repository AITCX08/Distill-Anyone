from dataclasses import dataclass

import pytest

from src.platforms.errors import (
    AmbiguousPlatformError,
    DuplicatePlatformError,
    PlatformNotDetectedError,
    TargetMismatchError,
    UnknownPlatformError,
)
from src.platforms.manager import PlatformManager
from src.platforms.models import ItemType, PlatformDescriptor
from src.platforms.registry import PlatformRegistry


@dataclass
class FakeAdapter:
    name: str
    should_match: bool

    @property
    def descriptor(self) -> PlatformDescriptor:
        return PlatformDescriptor(
            name=self.name,
            url_patterns=(rf"https://{self.name}\\.example/",),
            item_types=frozenset({ItemType.VIDEO}),
        )

    def matches(self, target: str) -> bool:
        return self.should_match


def test_duplicate_platform_registration_is_rejected():
    registry = PlatformRegistry()
    registry.register(FakeAdapter("douyin", True))

    with pytest.raises(DuplicatePlatformError):
        registry.register(FakeAdapter("douyin", True))


def test_get_unknown_platform_is_actionable():
    registry = PlatformRegistry()

    with pytest.raises(UnknownPlatformError, match="missing"):
        registry.get("missing")


def test_auto_detect_requires_one_match():
    registry = PlatformRegistry([FakeAdapter("douyin", True)])

    assert registry.detect("https://v.douyin.com/example/").descriptor.name == "douyin"


def test_auto_detect_rejects_zero_matches():
    registry = PlatformRegistry([FakeAdapter("douyin", False)])

    with pytest.raises(PlatformNotDetectedError):
        registry.detect("https://unknown.example/")


def test_auto_detect_rejects_multiple_matches():
    registry = PlatformRegistry(
        [FakeAdapter("bilibili", True), FakeAdapter("douyin", True)]
    )

    with pytest.raises(AmbiguousPlatformError):
        registry.detect("https://ambiguous.example/")


def test_descriptors_are_stably_sorted():
    registry = PlatformRegistry(
        [FakeAdapter("douyin", False), FakeAdapter("bilibili", False)]
    )

    assert [item.name for item in registry.list_descriptors()] == ["bilibili", "douyin"]


def test_manager_explicit_platform_validates_target():
    manager = PlatformManager(PlatformRegistry([FakeAdapter("douyin", False)]))

    with pytest.raises(TargetMismatchError):
        manager.select("https://not-douyin.example/", platform="douyin")
