"""Streaming, atomic downloads for short-lived Douyin media URLs."""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.distillation.progress import TransferProgress
from src.platforms.errors import PlatformDownloadError
from src.platforms.models import DownloadedAssets, SourceItem


class _UrlResponse:
    def __init__(self, response: Any):
        self._response = response
        status = getattr(response, "status", None)
        self.status = int(status if status is not None else response.getcode())
        self.headers = response.headers

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._response.close()

    def iter_bytes(self, chunk_size: int):
        while chunk := self._response.read(chunk_size):
            yield chunk


class UrllibHttpClient:
    def get(self, url: str, *, headers: dict[str, str]):
        request = urllib.request.Request(url, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=60)
        except urllib.error.HTTPError as exc:
            response = exc
        return _UrlResponse(response)


def _header(headers: Any, name: str) -> str | None:
    if hasattr(headers, "get"):
        value = headers.get(name) or headers.get(name.lower())
        return str(value) if value is not None else None
    return None


class DouyinDownloader:
    def __init__(
        self,
        http_client: Any | None = None,
        *,
        refresh_item: Callable[[SourceItem], SourceItem] | None = None,
        chunk_size: int = 64 * 1024,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.http_client = http_client or UrllibHttpClient()
        self._refresh_item = refresh_item
        self.chunk_size = chunk_size
        self.clock = clock

    @staticmethod
    def _video_url(item: SourceItem) -> tuple[str, int | None]:
        for asset in item.assets:
            if asset.kind == "video":
                return asset.url, asset.expected_bytes
        raise PlatformDownloadError(f"Douyin item {item.item_id} has no video asset")

    def refresh_item(self, item: SourceItem) -> SourceItem:
        return self._refresh_item(item) if self._refresh_item is not None else item

    def download(
        self,
        item: SourceItem,
        destination: Path,
        progress: Callable[[TransferProgress], None],
    ) -> DownloadedAssets:
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / f"{item.item_id}.mp4"
        temporary = destination / f".{item.item_id}.{uuid.uuid4().hex}.part"
        current = item
        refreshed = False
        try:
            while True:
                url, declared_total = self._video_url(current)
                with self.http_client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": current.canonical_url,
                    },
                ) as response:
                    if response.status in {401, 403, 404} and not refreshed:
                        if self._refresh_item is None:
                            raise PlatformDownloadError(
                                f"Douyin media URL expired for {item.item_id}"
                            )
                        current = self._refresh_item(current)
                        refreshed = True
                        continue
                    if response.status < 200 or response.status >= 300:
                        raise PlatformDownloadError(
                            f"Douyin download failed for {item.item_id}: HTTP {response.status}"
                        )

                    content_length = _header(response.headers, "Content-Length")
                    total = int(content_length) if content_length and content_length.isdigit() else declared_total
                    completed = 0
                    started = self.clock()
                    with temporary.open("wb") as stream:
                        for chunk in response.iter_bytes(self.chunk_size):
                            if not chunk:
                                continue
                            stream.write(chunk)
                            completed += len(chunk)
                            elapsed = max(self.clock() - started, 1e-9)
                            progress(
                                TransferProgress(
                                    source_id=item.source_id,
                                    completed_bytes=completed,
                                    total_bytes=total,
                                    bytes_per_second=completed / elapsed,
                                    timestamp=datetime.now(timezone.utc),
                                )
                            )
                        stream.flush()
                        os.fsync(stream.fileno())
                    if completed <= 0:
                        raise PlatformDownloadError(
                            f"Douyin download returned an empty body for {item.item_id}"
                        )
                    if total is not None and completed != total:
                        raise PlatformDownloadError(
                            f"Douyin download size mismatch for {item.item_id}: {completed}/{total}"
                        )
                    os.replace(temporary, path)
                    return DownloadedAssets(video_path=path)
        finally:
            temporary.unlink(missing_ok=True)

    def download_assets(
        self,
        item: SourceItem,
        destination: Path,
        *,
        progress: Callable[[TransferProgress], None],
    ) -> DownloadedAssets:
        return self.download(item, destination, progress)
