"""Bounded, redacted, atomically-written application event logs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

from src.application.events import ApplicationEvent
from src.application.redaction import redact_value


class SanitizedEventLog:
    def __init__(self, path: Path, *, max_bytes: int = 5 * 1024 * 1024, backups: int = 3) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups
        self._lock = RLock()

    def append(self, event: ApplicationEvent) -> None:
        value = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "payload": redact_value(event.payload),
        }
        encoded = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            current = self.path.read_bytes() if self.path.exists() else b""
            if current and len(current) + len(encoded) > self.max_bytes:
                self._rotate()
                current = b""
            self._atomic_write(current + encoded)

    def _rotate(self) -> None:
        for index in range(self.backups, 0, -1):
            source = self.path.with_name(f"{self.path.name}.{index}")
            target = self.path.with_name(f"{self.path.name}.{index + 1}")
            if source.exists():
                if index == self.backups:
                    source.unlink()
                else:
                    os.replace(source, target)
        if self.path.exists():
            os.replace(self.path, self.path.with_name(f"{self.path.name}.1"))

    def _atomic_write(self, content: bytes) -> None:
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, self.path)
