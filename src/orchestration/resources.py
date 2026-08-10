"""In-memory stage resource slots shared by one local TaskManager."""

from __future__ import annotations

from dataclasses import dataclass, field


_RESOURCE_BY_STAGE = {
    "downloading": "download",
    "downloaded": "download",
    "extracting_audio": "asr",
    "transcribing": "asr",
    "cleaning": "llm",
    "summarizing": "llm",
    "writing": "llm",
}


@dataclass
class ResourceSlots:
    """Small, deterministic allocation table for worker stage boundaries."""

    download: int = 2
    asr: int = 1
    llm: int = 1
    _holders: dict[str, set[str]] = field(default_factory=dict, init=False)

    def clear(self) -> None:
        """Rebuild grants from durable worker requests on each manager tick."""

        self._holders.clear()

    def acquire(self, task_id: str, stage: str) -> bool:
        resource = _RESOURCE_BY_STAGE.get(stage)
        if resource is None:
            return True
        holders = self._holders.setdefault(resource, set())
        if task_id in holders:
            return True
        if len(holders) >= getattr(self, resource):
            return False
        holders.add(task_id)
        return True

    def release(self, task_id: str, stage: str) -> None:
        resource = _RESOURCE_BY_STAGE.get(stage)
        if resource is not None:
            self._holders.setdefault(resource, set()).discard(task_id)
