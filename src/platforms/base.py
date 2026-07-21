"""Protocol implemented by each source platform adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterator, Protocol

from src.platforms.models import (
    AuthStatus,
    DownloadedAssets,
    EnumerationCheckpoint,
    EnumerationPage,
    PlatformDescriptor,
    ResolvedTarget,
    SourceCreator,
    SourceItem,
)


class PlatformAdapter(Protocol):
    """Boundary between platform acquisition and shared distillation."""

    descriptor: PlatformDescriptor

    def matches(self, target: str) -> bool:
        """Return whether this adapter understands the target."""

    def auth_status(self) -> AuthStatus:
        """Return authentication state without exposing credentials."""

    def authenticate(self, *, headful: bool) -> None:
        """Run the platform-specific authentication flow."""

    def resolve(self, target: str) -> ResolvedTarget:
        """Resolve a user target to a canonical creator target."""

    def get_creator(self, target: ResolvedTarget) -> SourceCreator:
        """Fetch normalized creator metadata."""

    def iter_items(
        self,
        creator: SourceCreator,
        *,
        checkpoint: EnumerationCheckpoint | None,
    ) -> Iterator[EnumerationPage]:
        """Yield normalized pages and resumable checkpoints."""

    def refresh_item(self, item: SourceItem) -> SourceItem:
        """Refresh dynamic asset URLs immediately before download."""

    def download_assets(
        self,
        item: SourceItem,
        destination: Path,
        *,
        progress: Callable[[int, int | None], None],
    ) -> DownloadedAssets:
        """Download the assets required by the content processor."""
