"""Atomic, credential-free telemetry state for a locally controlled series."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SeriesRuntimeStore:
    def __init__(self, root: Path, *, trace_limit: int = 100) -> None:
        self.path = Path(root) / "runtime.json"
        self.trace_limit = trace_limit

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._default()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return self._default()
        return value if isinstance(value, dict) else self._default()

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "status": "idle",
            "revision": 0,
            "active_part": None,
            "stage": None,
            "transfer": {},
            "trace": [],
            "updated_at": None,
        }

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    def update(self, **changes: Any) -> dict[str, Any]:
        value = self.load()
        value.update(changes)
        value["revision"] = int(value.get("revision", 0)) + 1
        value["updated_at"] = _utc_now()
        self._write(value)
        return value

    def append_trace(self, level: str, message: str) -> dict[str, Any]:
        value = self.load()
        trace = list(value.get("trace") or [])
        trace.append({"at": _utc_now(), "level": str(level), "message": str(message)})
        return self.update(trace=trace[-self.trace_limit :])

    def pause_requested(self) -> bool:
        return self.load().get("status") == "pause_requested"
