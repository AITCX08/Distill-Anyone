"""Platform capability and external-browser login endpoints."""

from threading import Thread
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.dashboard.security import require_mutation_security

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
    operation_id = uuid4().hex
    Thread(
        target=request.app.state.service.login_platform,
        kwargs={"platform": platform, "headful": True},
        daemon=True,
        name=f"dashboard-login-{platform}",
    ).start()
    return LoginResponse(operation_id=operation_id, platform=platform, status="opening_browser")
