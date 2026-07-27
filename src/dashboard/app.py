"""FastAPI application factory for the loopback-only Dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response

from src.application.service import DistillationService
from src.dashboard.api.health import router as health_router
from src.dashboard.security import CSRF_COOKIE, SESSION_COOKIE, new_local_session

_CSP = "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"


def create_dashboard_app(
    service: DistillationService,
    static_dir: Path,
    session_secret: str,
) -> FastAPI:
    """Create a docs-free Dashboard app backed by one application service."""

    del session_secret  # A fresh process-local session is safer than a serialized secret.
    index_path = static_dir / "index.html"
    if not index_path.is_file():
        raise FileNotFoundError(f"Dashboard static index is missing: {index_path}")

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service
    app.state.static_dir = static_dir.resolve()
    app.state.static_compatible = True
    app.state.local_session = new_local_session()
    app.include_router(health_router)

    @app.middleware("http")
    async def protect_dashboard(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", _CSP)
        session = request.app.state.local_session
        if request.cookies.get(SESSION_COOKIE) != session.value:
            response.set_cookie(
                SESSION_COOKIE,
                session.value,
                httponly=True,
                samesite="strict",
                secure=False,
            )
            response.set_cookie(
                CSRF_COOKIE,
                session.csrf_token,
                httponly=False,
                samesite="strict",
                secure=False,
            )
        return response

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        candidate = (app.state.static_dir / path).resolve()
        if candidate.is_file() and candidate.is_relative_to(app.state.static_dir):
            return FileResponse(candidate)
        return FileResponse(index_path)

    return app
