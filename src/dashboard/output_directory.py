"""Private local-output directory selection for the loopback Dashboard."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class DirectoryValidationResult:
    """A directory validated for one short-lived local Dashboard session."""

    token: str
    directory: str
    expires_at: str


@dataclass(frozen=True)
class DirectorySelection:
    """The result of a local native directory picker interaction."""

    selected: bool
    directory: str | None = None
    token: str | None = None
    expires_at: str | None = None


@dataclass(frozen=True)
class _TokenRecord:
    directory: Path
    session_id: str
    expires_at: datetime


class OutputDirectoryService:
    """Persist only the default directory; retain validation tokens in memory."""

    def __init__(
        self,
        settings_path: Path,
        *,
        session_id: str,
        default_directory: Path | None = None,
        token_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self._settings_path = settings_path
        self._session_id = session_id
        self._fallback_directory = (default_directory or settings_path.parent / "output").resolve(
            strict=False
        )
        self._token_ttl = token_ttl
        self._tokens: dict[str, _TokenRecord] = {}

    def get_default(self) -> Path:
        """Return the persisted default or the application-owned fallback."""

        try:
            data = json.loads(self._settings_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return self._fallback_directory
        value = data.get("default_directory")
        if not isinstance(value, str) or not value.strip():
            return self._fallback_directory
        return self._normalize(value)

    def set_default(self, directory: str) -> Path:
        """Validate and persist a user-selected local default directory."""

        resolved = self._validate_directory(directory)
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._settings_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps({"default_directory": str(resolved)}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary_path, self._settings_path)
        return resolved

    def validate(self, directory: str) -> DirectoryValidationResult:
        """Validate a directory and issue a five-minute session-bound token."""

        resolved = self._validate_directory(directory)
        expires_at = datetime.now(UTC) + self._token_ttl
        token = secrets.token_urlsafe(32)
        self._tokens[token] = _TokenRecord(
            directory=resolved,
            session_id=self._session_id,
            expires_at=expires_at,
        )
        return DirectoryValidationResult(
            token=token,
            directory=str(resolved),
            expires_at=expires_at.isoformat(),
        )

    def resolve_token(self, token: str, *, session_id: str) -> Path:
        """Resolve only a current token issued for the requesting local session."""

        record = self._tokens.get(token)
        if record is None or record.expires_at <= datetime.now(UTC):
            self._tokens.pop(token, None)
            raise PermissionError("directory validation token is unavailable")
        if not secrets.compare_digest(record.session_id, session_id):
            raise PermissionError("directory validation token belongs to another session")
        return record.directory

    def choose(self, chooser: Callable[[Path], Path | None]) -> DirectorySelection:
        """Run an injected local chooser and turn its result into a validation token."""

        selected = chooser(self.get_default())
        if selected is None:
            return DirectorySelection(selected=False)
        result = self.validate(str(selected))
        return DirectorySelection(
            selected=True,
            directory=result.directory,
            token=result.token,
            expires_at=result.expires_at,
        )

    def _validate_directory(self, directory: str) -> Path:
        resolved = self._normalize(directory)
        if resolved.parent == resolved:
            raise ValueError("filesystem root cannot be used as an output directory")

        resolved.parent.mkdir(parents=True, exist_ok=True)
        probe = Path(tempfile.mkdtemp(prefix=".distill-write-check-", dir=resolved.parent))
        probe.rmdir()
        return resolved

    @staticmethod
    def _normalize(directory: str) -> Path:
        if not directory.strip():
            raise ValueError("output directory is required")
        return Path(directory).expanduser().resolve(strict=False)


def choose_output_directory(initial_directory: Path) -> Path | None:
    """Ask the local desktop for a directory without starting a shell process."""

    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    try:
        selected = filedialog.askdirectory(
            parent=root,
            initialdir=str(initial_directory),
            title="选择默认保存位置",
            mustexist=False,
        )
    finally:
        root.destroy()
    return Path(selected) if selected else None
