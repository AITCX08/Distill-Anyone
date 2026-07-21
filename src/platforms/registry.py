"""Explicit registry for built-in platform adapters."""

from __future__ import annotations

from collections.abc import Iterable

from src.platforms.base import PlatformAdapter
from src.platforms.errors import (
    AmbiguousPlatformError,
    DuplicatePlatformError,
    PlatformNotDetectedError,
    UnknownPlatformError,
)
from src.platforms.models import PlatformDescriptor


class PlatformRegistry:
    """Register and discover platform adapters without dynamic plugins."""

    def __init__(self, adapters: Iterable[PlatformAdapter] = ()):
        self._adapters: dict[str, PlatformAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: PlatformAdapter) -> None:
        name = adapter.descriptor.name
        if name in self._adapters:
            raise DuplicatePlatformError(name)
        self._adapters[name] = adapter

    def get(self, name: str) -> PlatformAdapter:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise UnknownPlatformError(name) from exc

    def detect(self, target: str) -> PlatformAdapter:
        matches = [adapter for adapter in self._adapters.values() if adapter.matches(target)]
        if not matches:
            raise PlatformNotDetectedError(target)
        if len(matches) > 1:
            raise AmbiguousPlatformError(
                target,
                [adapter.descriptor.name for adapter in matches],
            )
        return matches[0]

    def list_descriptors(self) -> tuple[PlatformDescriptor, ...]:
        return tuple(
            adapter.descriptor
            for adapter in sorted(
                self._adapters.values(),
                key=lambda item: item.descriptor.name,
            )
        )
