"""Selection facade used by application services and pipelines."""

from src.platforms.base import PlatformAdapter
from src.platforms.errors import TargetMismatchError
from src.platforms.models import PlatformDescriptor
from src.platforms.registry import PlatformRegistry


class PlatformManager:
    """Select adapters while keeping platform logic out of callers."""

    def __init__(self, registry: PlatformRegistry):
        self._registry = registry

    def select(self, target: str, *, platform: str = "auto") -> PlatformAdapter:
        if platform == "auto":
            return self._registry.detect(target)

        adapter = self._registry.get(platform)
        if not adapter.matches(target):
            raise TargetMismatchError(platform, target)
        return adapter

    def list_descriptors(self) -> tuple[PlatformDescriptor, ...]:
        return self._registry.list_descriptors()
