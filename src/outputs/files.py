"""Small atomic file primitives shared by output targets."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

from src.outputs.errors import OutputValidationError


def atomic_write_text(
    path: Path,
    content: str,
    *,
    validator: Callable[[Path], bool],
) -> Path:
    """Validate a flushed temporary file before atomically replacing its target."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if not validator(temporary):
            raise OutputValidationError(path)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path
