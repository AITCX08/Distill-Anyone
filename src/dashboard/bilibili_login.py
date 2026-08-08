"""Short-lived, local-only Bilibili QR login sessions for the Dashboard."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from threading import Lock, Thread
from typing import Any, Callable
from uuid import uuid4


@dataclass(frozen=True)
class BilibiliLoginSnapshot:
    operation_id: str
    status: str
    message: str


@dataclass
class _LoginOperation:
    operation_id: str
    status: str = "preparing_qr"
    message: str = "正在生成二维码"
    qr_png: bytes | None = None

    def snapshot(self) -> BilibiliLoginSnapshot:
        return BilibiliLoginSnapshot(self.operation_id, self.status, self.message)


def _default_qr_login_factory() -> tuple[Any, Any]:
    from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginChannel, QrCodeLoginEvents

    # The upstream WEB flow can report DONE with an empty Credential on recent
    # Bilibili responses.  The TV flow returns cookie fields directly.
    return QrCodeLogin(QrCodeLoginChannel.TV), QrCodeLoginEvents


async def _default_buvid_fetcher() -> str:
    try:
        from bilibili_api.utils.network import get_buvid

        result = await get_buvid()
        return str(result[0]) if result else ""
    except Exception:
        return ""


class BilibiliLoginCoordinator:
    """Own one Bilibili QR session and never expose its eventual credential."""

    _ACTIVE_STATUSES = frozenset({"preparing_qr", "waiting_for_scan", "waiting_for_confirmation"})

    def __init__(
        self,
        *,
        qr_login_factory: Callable[[], tuple[Any, Any]] = _default_qr_login_factory,
        buvid_fetcher: Callable[[], Any] = _default_buvid_fetcher,
        poll_seconds: float = 1.0,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._qr_login_factory = qr_login_factory
        self._buvid_fetcher = buvid_fetcher
        self._poll_seconds = poll_seconds
        self._timeout_seconds = timeout_seconds
        self._lock = Lock()
        self._operations: dict[str, _LoginOperation] = {}
        self._active_operation_id: str | None = None

    def start(self, save_credential: Callable[[Any, str], None]) -> BilibiliLoginSnapshot:
        with self._lock:
            if self._active_operation_id is not None:
                active = self._operations[self._active_operation_id]
                if active.status in self._ACTIVE_STATUSES:
                    return active.snapshot()
            operation = _LoginOperation(operation_id=uuid4().hex)
            self._operations[operation.operation_id] = operation
            self._active_operation_id = operation.operation_id

        Thread(
            target=self._run_in_background,
            args=(operation.operation_id, save_credential),
            daemon=True,
            name=f"dashboard-bilibili-login-{operation.operation_id[:8]}",
        ).start()
        return operation.snapshot()

    def get(self, operation_id: str) -> BilibiliLoginSnapshot:
        with self._lock:
            return self._get_operation(operation_id).snapshot()

    def qr_png(self, operation_id: str) -> bytes:
        with self._lock:
            png = self._get_operation(operation_id).qr_png
        if png is None:
            raise LookupError("二维码仍在生成")
        return png

    def _get_operation(self, operation_id: str) -> _LoginOperation:
        try:
            return self._operations[operation_id]
        except KeyError as error:
            raise LookupError("登录会话不存在或已过期") from error

    def _update(self, operation_id: str, *, status: str, message: str, qr_png: bytes | None = None) -> None:
        with self._lock:
            operation = self._get_operation(operation_id)
            operation.status = status
            operation.message = message
            if qr_png is not None:
                operation.qr_png = qr_png
            if status not in self._ACTIVE_STATUSES and self._active_operation_id == operation_id:
                self._active_operation_id = None

    def _run_in_background(self, operation_id: str, save_credential: Callable[[Any, str], None]) -> None:
        try:
            asyncio.run(self._run_login(operation_id, save_credential))
        except Exception:
            self._update(
                operation_id,
                status="failed",
                message="二维码登录失败，请重新发起登录。",
            )

    async def _run_login(self, operation_id: str, save_credential: Callable[[Any, str], None]) -> None:
        qr, events = self._qr_login_factory()
        await qr.generate_qrcode()
        picture = qr.get_qrcode_picture()
        png = bytes(picture.content)
        if not png:
            raise RuntimeError("二维码图片为空")
        self._update(operation_id, status="waiting_for_scan", message="请使用哔哩哔哩 App 扫码", qr_png=png)

        deadline = time.monotonic() + self._timeout_seconds
        while time.monotonic() < deadline:
            await asyncio.sleep(self._poll_seconds)
            state = await qr.check_state()
            if state == events.DONE:
                credential = qr.get_credential()
                if not getattr(credential, "sessdata", "") or not getattr(credential, "bili_jct", ""):
                    self._update(
                        operation_id,
                        status="failed",
                        message="登录结果缺少有效凭据，请重新发起二维码登录。",
                    )
                    return
                buvid3 = await self._buvid_fetcher()
                save_credential(credential, buvid3)
                self._update(operation_id, status="succeeded", message="登录成功，凭据已安全保存到本机。")
                return
            if state == events.CONF:
                self._update(operation_id, status="waiting_for_confirmation", message="已扫码，请在手机上确认登录。")
            elif state == events.SCAN:
                self._update(operation_id, status="waiting_for_scan", message="请使用哔哩哔哩 App 扫码。")
            elif state == events.TIMEOUT:
                self._update(operation_id, status="expired", message="二维码已过期，请重新发起登录。")
                return

        self._update(operation_id, status="expired", message="二维码已过期，请重新发起登录。")
