"""High-level Douyin adapter composed from browser session primitives."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Iterator
from urllib.parse import urlparse

from src.platforms.douyin.resolver import DouyinResolver, extract_sec_uid, extract_target_url
from src.platforms.models import (
    AuthStatus,
    DownloadedAssets,
    EnumerationCheckpoint,
    EnumerationPage,
    ItemType,
    PlatformDescriptor,
    ResolvedTarget,
    SourceCreator,
    SourceItem,
)


_DIRECT_RE = re.compile(r"^douyin:[A-Za-z0-9_.-]+$", re.IGNORECASE)


class DouyinAdapter:
    descriptor = PlatformDescriptor(
        name="douyin",
        url_patterns=(r"https?://(?:v\.)?douyin\.com/",),
        item_types=frozenset({ItemType.VIDEO, ItemType.GALLERY}),
        requires_browser=True,
        requires_auth=True,
        commands=("status", "login", "creator"),
    )

    def __init__(
        self,
        session,
        *,
        resolver_factory: Callable = DouyinResolver,
        enumerator=None,
        downloader=None,
    ) -> None:
        self.session = session
        self._resolver_factory = resolver_factory
        self._enumerator = enumerator
        self._downloader = downloader

    def matches(self, target: str) -> bool:
        if _DIRECT_RE.fullmatch(target.strip()):
            return True
        url = extract_target_url(target)
        if not url:
            return False
        hostname = (urlparse(url).hostname or "").lower()
        return hostname == "douyin.com" or hostname.endswith(".douyin.com")

    def auth_status(self) -> AuthStatus:
        return self.session.auth_status()

    def authenticate(self, *, headful: bool) -> None:
        self.session.authenticate(headful=headful)

    def resolve(self, target: str) -> ResolvedTarget:
        direct = _DIRECT_RE.fullmatch(target.strip())
        url = extract_target_url(target)
        if direct or (url and extract_sec_uid(url)):
            return self._resolver_factory(None).resolve_share_url(target)
        with self.session.open_page(headless=True, task="resolve") as page:
            return self._resolver_factory(page).resolve_share_url(target)

    def get_creator(self, target: ResolvedTarget) -> SourceCreator:
        return SourceCreator(
            platform="douyin",
            creator_id=target.creator_id,
            display_name=f"Douyin {target.creator_id[:12]}",
            canonical_url=target.canonical_url,
        )

    def iter_items(
        self,
        creator: SourceCreator,
        *,
        checkpoint: EnumerationCheckpoint | None,
    ) -> Iterator[EnumerationPage]:
        if self._enumerator is None:
            raise RuntimeError("Douyin item enumerator is not configured")
        yield from self._enumerator.iter_items(creator, checkpoint=checkpoint)

    def refresh_item(self, item: SourceItem) -> SourceItem:
        if self._downloader is None:
            return item
        return self._downloader.refresh_item(item)

    def download_assets(
        self,
        item: SourceItem,
        destination: Path,
        *,
        progress,
    ) -> DownloadedAssets:
        if self._downloader is None:
            raise RuntimeError("Douyin downloader is not configured")
        return self._downloader.download_assets(item, destination, progress=progress)
