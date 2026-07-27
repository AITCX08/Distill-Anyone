"""Local-session, origin, and loopback protections for the Dashboard."""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

SESSION_COOKIE = "distill_session"
CSRF_COOKIE = "distill_csrf"
CSRF_HEADER = "X-Distill-CSRF"


@dataclass(frozen=True)
class LocalSession:
    value: str
    csrf_token: str


def validate_host(host: str) -> str:
    """Accept the sole address this single-user Dashboard may bind."""

    if host != "127.0.0.1":
        raise ValueError("Dashboard must bind only to 127.0.0.1")
    return host


def new_local_session() -> LocalSession:
    return LocalSession(
        value=secrets.token_urlsafe(32),
        csrf_token=secrets.token_urlsafe(32),
    )


def require_local_session(request: Request) -> LocalSession:
    session: LocalSession = request.app.state.local_session
    supplied = request.cookies.get(SESSION_COOKIE, "")
    if not hmac.compare_digest(supplied, session.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="local session required")
    return session


def require_mutation_security(request: Request) -> None:
    session = require_local_session(request)
    origin = request.headers.get("origin")
    expected_origin = f"{request.url.scheme}://{request.url.netloc}"
    csrf_token = request.headers.get(CSRF_HEADER, "")
    if origin != expected_origin or not hmac.compare_digest(csrf_token, session.csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="mutation rejected")
