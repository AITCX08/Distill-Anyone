"""Content-addressed records used to validate resumable artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class ArtifactValidationError(RuntimeError):
    def __init__(self, path: Path):
        super().__init__(f"Artifact validation failed: {path}")
        self.path = path


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ArtifactRecord:
    path: str
    sha256: str
    size_bytes: int
    valid: bool = True
    content_type: str = ""

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ArtifactRecord":
        return cls(
            path=str(value["path"]),
            sha256=str(value["sha256"]),
            size_bytes=int(value.get("size_bytes", 0)),
            valid=bool(value.get("valid", True)),
            content_type=str(value.get("content_type", "")),
        )


def verify_artifact(record: ArtifactRecord) -> bool:
    """Reopen an artifact and verify its declared validity, size, and hash."""

    if not record.valid:
        return False
    path = Path(record.path)
    try:
        if not path.is_file() or path.stat().st_size != record.size_bytes:
            return False
        return sha256_file(path) == record.sha256
    except OSError:
        return False
