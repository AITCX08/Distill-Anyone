"""Safe local controls for registered checkpointed series runners."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.series.runtime import SeriesRuntimeStore


class SeriesController:
    def __init__(self, data_dir: Path, *, launcher: Callable[[str], None]) -> None:
        self.data_dir = Path(data_dir)
        self.launcher = launcher

    def _store(self, bvid: str) -> SeriesRuntimeStore:
        state_path = self.data_dir / "series" / bvid / "state.json"
        if not state_path.is_file():
            raise LookupError("series was not registered locally")
        return SeriesRuntimeStore(state_path.parent)

    def pause(self, bvid: str) -> dict[str, Any]:
        runtime = self._store(bvid)
        current = runtime.load()
        if current.get("status") in {"paused", "pause_requested"}:
            return current
        return runtime.update(status="pause_requested")

    def resume(self, bvid: str) -> dict[str, Any]:
        runtime = self._store(bvid)
        current = runtime.load()
        if current.get("status") == "running":
            return current
        updated = runtime.update(status="running", transfer={})
        self.launcher(bvid)
        return updated
