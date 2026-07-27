"""Shared event redaction for browser streams and durable local logs."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

_SENSITIVE_KEYS = {"cookie", "cookies", "authorization", "api_key", "token", "secret", "profile", "path"}
_INLINE_SECRETS = (
    (re.compile(r"(?i)(SESSDATA=)[^\s;,&]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(Authorization:\s*Bearer\s+)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]+"), "[REDACTED]"),
    (re.compile(r"[A-Za-z]:\\(?:[^\\\s]+\\)*[^\\\s]*"), "<local-path>"),
    (re.compile(r"/(?:Users|home)/[^\s/]+(?:/[^\s]*)?"), "<local-path>"),
)


def redact_value(value: Any, *, key: str = "") -> Any:
    """Return a recursively safe value without mutating an event payload."""

    if key.lower() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if is_dataclass(value) and not isinstance(value, type):
        return redact_value(asdict(value), key=key)
    if isinstance(value, Mapping):
        return {str(name): redact_value(item, key=str(name)) for name, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        result = value
        for pattern, replacement in _INLINE_SECRETS:
            result = pattern.sub(replacement, result)
        return result
    return value
