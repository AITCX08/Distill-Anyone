"""Platform-neutral source adapter contracts."""

from src.platforms.base import PlatformAdapter
from src.platforms.manager import PlatformManager
from src.platforms.models import (
    AuthStatus,
    DownloadedAssets,
    EnumerationCheckpoint,
    EnumerationPage,
    ItemType,
    PlatformDescriptor,
    ResolvedTarget,
    SourceAsset,
    SourceCreator,
    SourceItem,
)
from src.platforms.registry import PlatformRegistry

__all__ = [
    "AuthStatus",
    "DownloadedAssets",
    "EnumerationCheckpoint",
    "EnumerationPage",
    "ItemType",
    "PlatformAdapter",
    "PlatformDescriptor",
    "PlatformManager",
    "PlatformRegistry",
    "ResolvedTarget",
    "SourceAsset",
    "SourceCreator",
    "SourceItem",
]
