"""Adapt the existing Bilibili crawler to platform-neutral contracts."""

from __future__ import annotations

import asyncio
import inspect
import re
import tempfile
from collections.abc import Callable, Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.crawl.audio_download import (
    download_audio_with_progress,
    generate_cookies_file,
    parse_duration_str,
)
from src.crawl.auth import get_credential, run_qrcode_login, save_credential
from src.crawl.video_list import fetch_user_videos
from src.distillation.progress import TransferProgress
from src.platforms.errors import PlatformDownloadError, TargetResolutionError
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


_SPACE_URL_RE = re.compile(
    r"^https?://space\.bilibili\.com/(?P<uid>\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)
_EXPLICIT_UID_RE = re.compile(r"^bilibili:(?P<uid>\d+)$", re.IGNORECASE)


def legacy_source_id(value: str) -> str:
    """Qualify a legacy BVID without double-prefixing new identifiers."""

    return value if value.startswith("bilibili_") else f"bilibili_{value}"


class BilibiliAdapter:
    """Thin wrapper around Distill-Anyone's established Bilibili functions."""

    descriptor = PlatformDescriptor(
        name="bilibili",
        url_patterns=(r"https?://space\.bilibili\.com/\d+",),
        item_types=frozenset({ItemType.VIDEO}),
        requires_auth=True,
        commands=("status", "login", "creator"),
    )

    def __init__(
        self,
        config,
        *,
        credential_provider: Callable = get_credential,
        video_fetcher: Callable = fetch_user_videos,
        download_fn: Callable = download_audio_with_progress,
        cookies_factory: Callable = generate_cookies_file,
        login_fn: Callable = run_qrcode_login,
        credential_saver: Callable = save_credential,
    ):
        self._config = config
        self._credential_provider = credential_provider
        self._video_fetcher = video_fetcher
        self._download_fn = download_fn
        self._cookies_factory = cookies_factory
        self._login_fn = login_fn
        self._credential_saver = credential_saver

    def matches(self, target: str) -> bool:
        return bool(_SPACE_URL_RE.match(target) or _EXPLICIT_UID_RE.match(target))

    def auth_status(self) -> AuthStatus:
        config = self._config.bilibili
        if config.sessdata:
            return AuthStatus("configured", "Bilibili credentials are configured")
        cache = getattr(self._config, "credentials_cache", None)
        if cache is not None and Path(cache).is_file() and Path(cache).stat().st_size > 0:
            return AuthStatus("configured", "Bilibili cached credentials are available")
        return AuthStatus("missing", "Run the Bilibili login command")

    def authenticate(self, *, headful: bool) -> None:
        del headful  # The existing QR login owns its browser presentation.
        result = self._login_fn()
        if isinstance(result, tuple) and len(result) == 2:
            credential, buvid3 = result
            self._credential_saver(
                credential,
                buvid3,
                self._config.credentials_cache,
            )

    def resolve(self, target: str) -> ResolvedTarget:
        match = _SPACE_URL_RE.match(target) or _EXPLICIT_UID_RE.match(target)
        if not match:
            raise TargetResolutionError(
                "Bilibili creator targets must use a space.bilibili.com URL"
            )
        creator_id = match.group("uid")
        return ResolvedTarget(
            platform="bilibili",
            creator_id=creator_id,
            canonical_url=f"https://space.bilibili.com/{creator_id}",
            original_target=target,
        )

    def get_creator(self, target: ResolvedTarget) -> SourceCreator:
        return SourceCreator(
            platform="bilibili",
            creator_id=target.creator_id,
            display_name=f"Bilibili {target.creator_id}",
            canonical_url=target.canonical_url,
        )

    def iter_items(
        self,
        creator: SourceCreator,
        *,
        checkpoint: EnumerationCheckpoint | None,
    ) -> Iterator[EnumerationPage]:
        credential, _ = self._credential_provider(self._config)
        seen_ids = set(checkpoint.seen_ids) if checkpoint else set()
        fetched = self._video_fetcher(
            int(creator.creator_id),
            credential,
            existing_bvids=seen_ids,
            max_candidates=0,
        )
        if inspect.isawaitable(fetched):
            fetched = asyncio.run(fetched)

        items = tuple(self.map_video(raw, creator.creator_id) for raw in fetched)
        next_seen = frozenset(seen_ids | {item.item_id for item in items})
        next_checkpoint = EnumerationCheckpoint(
            cursor=None,
            seen_ids=next_seen,
            complete=True,
            expected_count=len(next_seen),
        )
        yield EnumerationPage(items=items, checkpoint=next_checkpoint, has_more=False)

    def refresh_item(self, item: SourceItem) -> SourceItem:
        return item

    def download_assets(
        self,
        item: SourceItem,
        destination: Path,
        *,
        progress: Callable[[TransferProgress], None],
    ) -> DownloadedAssets:
        credential, buvid3 = self._credential_provider(self._config)
        latest_speed = 0.0

        def report_transfer(
            completed_bytes: int,
            total_bytes: int | None,
            bytes_per_second: float,
        ) -> None:
            nonlocal latest_speed
            latest_speed = max(0.0, bytes_per_second)
            progress(
                TransferProgress(
                    source_id=item.source_id,
                    completed_bytes=completed_bytes,
                    total_bytes=total_bytes,
                    bytes_per_second=latest_speed,
                    timestamp=datetime.now(timezone.utc),
                )
            )

        with tempfile.TemporaryDirectory(prefix="distill_bilibili_") as temp_dir:
            cookie_path = self._cookies_factory(
                credential,
                buvid3,
                Path(temp_dir) / "cookies.txt",
            )
            audio_path = self._download_fn(
                item.item_id,
                destination,
                audio_format="wav",
                cookies_file=cookie_path,
                progress_callback=report_transfer,
            )

        if audio_path is None:
            raise PlatformDownloadError(
                f"Bilibili audio download failed for {item.item_id}"
            )
        audio_path = Path(audio_path)
        size = audio_path.stat().st_size if audio_path.exists() else 0
        progress(
            TransferProgress(
                source_id=item.source_id,
                completed_bytes=size,
                total_bytes=size,
                bytes_per_second=latest_speed,
                timestamp=datetime.now(timezone.utc),
            )
        )
        return DownloadedAssets(audio_path=audio_path)

    def map_video(
        self,
        raw: Mapping[str, Any],
        creator_id: str,
    ) -> SourceItem:
        bvid = str(raw["bvid"])
        timestamp = raw.get("pubdate")
        published_at = None
        if isinstance(timestamp, (int, float)) and timestamp > 0:
            published_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)

        return SourceItem(
            platform="bilibili",
            item_id=bvid,
            creator_id=creator_id,
            item_type=ItemType.VIDEO,
            title=str(raw.get("title") or bvid),
            description=str(raw.get("description") or ""),
            canonical_url=f"https://www.bilibili.com/video/{bvid}",
            published_at=published_at,
            duration_seconds=parse_duration_str(str(raw.get("duration") or "0")),
            statistics={
                "views": int(raw.get("view_count") or 0),
                "comments": int(raw.get("comment_count") or 0),
            },
            raw_metadata=dict(raw),
        )
