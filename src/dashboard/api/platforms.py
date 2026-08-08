"""Platform capability and external-browser login endpoints."""

from threading import Thread
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from src.dashboard.security import require_local_session, require_mutation_security

router = APIRouter(prefix="/api/v1/platforms", tags=["platforms"])


class PlatformResponse(BaseModel):
    name: str
    item_types: tuple[str, ...]
    requires_browser: bool
    requires_auth: bool
    auth_status: str
    auth_message: str


class LoginResponse(BaseModel):
    operation_id: str
    platform: str
    status: str
    message: str | None = None
    qr_url: str | None = None


@router.get("", response_model=tuple[PlatformResponse, ...])
def list_platforms(request: Request):
    return tuple(
        PlatformResponse(
            name=descriptor.name,
            item_types=tuple(sorted(item.value for item in descriptor.item_types)),
            requires_browser=descriptor.requires_browser,
            requires_auth=descriptor.requires_auth,
            auth_status=auth.status,
            auth_message=auth.message,
        )
        for descriptor, auth in request.app.state.service.list_platforms()
    )


@router.get("/{platform}/auth", response_model=PlatformResponse)
def platform_auth(platform: str, request: Request):
    for descriptor, auth in request.app.state.service.list_platforms():
        if descriptor.name == platform:
            return PlatformResponse(
                name=descriptor.name,
                item_types=tuple(sorted(item.value for item in descriptor.item_types)),
                requires_browser=descriptor.requires_browser,
                requires_auth=descriptor.requires_auth,
                auth_status=auth.status,
                auth_message=auth.message,
            )
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="platform not found")


@router.post("/{platform}/login", response_model=LoginResponse, dependencies=[Depends(require_mutation_security)])
def login(platform: str, request: Request):
    if platform == "bilibili":
        adapter = request.app.state.service.platform_manager.get(platform)
        save_credential = getattr(adapter, "save_dashboard_credential", None)
        if not callable(save_credential):
            raise HTTPException(status_code=409, detail="Bilibili QR login is unavailable")
        snapshot = request.app.state.bilibili_login.start(save_credential)
        return LoginResponse(
            operation_id=snapshot.operation_id,
            platform=platform,
            status=snapshot.status,
            message=snapshot.message,
            qr_url=f"/api/v1/platforms/bilibili/login/{snapshot.operation_id}/qr",
        )
    operation_id = uuid4().hex
    Thread(
        target=request.app.state.service.login_platform,
        kwargs={"platform": platform, "headful": True},
        daemon=True,
        name=f"dashboard-login-{platform}",
    ).start()
    return LoginResponse(operation_id=operation_id, platform=platform, status="opening_browser")


@router.get("/bilibili/login/{operation_id}", dependencies=[Depends(require_local_session)])
def bilibili_login_status(operation_id: str, request: Request):
    try:
        snapshot = request.app.state.bilibili_login.get(operation_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return snapshot.__dict__


@router.get("/bilibili/login/{operation_id}/qr", dependencies=[Depends(require_local_session)])
def bilibili_login_qr(operation_id: str, request: Request) -> Response:
    try:
        png = request.app.state.bilibili_login.qr_png(operation_id)
    except LookupError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})
