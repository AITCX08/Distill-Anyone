"""Resolve Douyin share text and redirects to a stable creator sec_uid."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlparse

from src.platforms.errors import TargetResolutionError
from src.platforms.models import ResolvedTarget


_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_SEC_UID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_DIRECT_RE = re.compile(r"^douyin:(?P<sec_uid>[A-Za-z0-9_.-]+)$", re.IGNORECASE)


def extract_sec_uid(value: str) -> str | None:
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    hostname = (parsed.hostname or "").lower()
    if hostname != "douyin.com" and not hostname.endswith(".douyin.com"):
        return None
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "user" or not _SEC_UID_RE.fullmatch(parts[1]):
        return None
    return parts[1]


def extract_target_url(target: str) -> str | None:
    match = _URL_RE.search(target)
    if not match:
        return None
    return match.group(0).rstrip("，。！？、,;!)）]}")


def _find_sec_uid(value: Any) -> str | None:
    if isinstance(value, dict):
        candidate = value.get("sec_uid")
        if isinstance(candidate, str) and _SEC_UID_RE.fullmatch(candidate):
            return candidate
        for nested in value.values():
            found = _find_sec_uid(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_sec_uid(nested)
            if found:
                return found
    return None


class DouyinResolver:
    def __init__(self, page: Any, *, timeout_ms: int = 30_000):
        self.page = page
        self.timeout_ms = timeout_ms

    def resolve_share_url(self, target: str) -> ResolvedTarget:
        direct = _DIRECT_RE.fullmatch(target.strip())
        if direct:
            creator_id = direct.group("sec_uid")
            return self._result(creator_id, target)

        target_url = extract_target_url(target)
        if not target_url:
            raise TargetResolutionError("Douyin target must contain a valid URL or douyin:sec_uid")
        direct_creator = extract_sec_uid(target_url)
        if direct_creator:
            return self._result(direct_creator, target)

        captured: list[str] = []

        def capture(response: Any) -> None:
            if "/aweme/" not in str(getattr(response, "url", "")):
                return
            try:
                creator_id = _find_sec_uid(response.json())
            except Exception:
                return
            if creator_id:
                captured.append(creator_id)

        on = getattr(self.page, "on", None)
        if callable(on):
            on("response", capture)
        self.page.goto(target_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        creator_id = extract_sec_uid(str(self.page.url)) or (captured[-1] if captured else None)
        if not creator_id:
            wait = getattr(self.page, "wait_for_timeout", None)
            if callable(wait):
                wait(min(1_000, self.timeout_ms))
            creator_id = captured[-1] if captured else None
        if not creator_id:
            raise TargetResolutionError(
                "Unable to resolve sec_uid from the Douyin share link; login may have expired"
            )
        return self._result(creator_id, target)

    @staticmethod
    def _result(creator_id: str, original_target: str) -> ResolvedTarget:
        return ResolvedTarget(
            platform="douyin",
            creator_id=creator_id,
            canonical_url=f"https://www.douyin.com/user/{creator_id}",
            original_target=original_target,
        )
