"""
B站认证模块

提供统一的凭据获取入口，支持三级策略：
1. .env 手动配置（优先）
2. 本地缓存文件
3. 浏览器弹出二维码扫码登录
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


def save_credential(credential, buvid3: str, cache_path: Path) -> None:
    """将凭据序列化为 JSON 缓存文件。"""
    data = {
        "sessdata": credential.sessdata,
        "bili_jct": credential.bili_jct,
        "dedeuserid": getattr(credential, "dedeuserid", ""),
        "buvid3": buvid3,
        "ac_time_value": getattr(credential, "ac_time_value", ""),
        "saved_at": datetime.now().isoformat(),
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    cache_path.chmod(0o600)
    console.print(f"[green]凭据已保存到 {cache_path}")


def load_cached_credential(cache_path: Path) -> Optional[tuple]:
    """
    从缓存文件加载凭据。

    Returns:
        (Credential, buvid3, saved_at) 元组，文件不存在或格式错误返回 None
    """
    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        sessdata = data.get("sessdata", "")
        bili_jct = data.get("bili_jct", "")
        if not sessdata or not bili_jct:
            return None

        from bilibili_api import Credential

        credential = Credential(
            sessdata=sessdata,
            bili_jct=bili_jct,
            dedeuserid=data.get("dedeuserid", ""),
            ac_time_value=data.get("ac_time_value", ""),
        )
        buvid3 = data.get("buvid3", "")
        saved_at = data.get("saved_at", "")
        return credential, buvid3, saved_at
    except Exception as e:
        console.print(f"[yellow]读取凭据缓存失败: {e}")
        return None


async def _check_credential_valid(credential) -> bool:
    """调用轻量 API 验证凭据是否仍有效。"""
    try:
        from bilibili_api import user

        u = user.User(uid=0, credential=credential)
        await u.get_self_info()
        return True
    except Exception:
        return False


def is_credential_valid(credential) -> bool:
    """同步包装：检查凭据有效性。"""
    try:
        return asyncio.run(_check_credential_valid(credential))
    except Exception:
        return False


async def _qrcode_login() -> tuple:
    """
    二维码扫码登录（浏览器弹出二维码图片）。

    Returns:
        (Credential, buvid3) 元组
    """
    import tempfile
    import webbrowser

    from bilibili_api.login_v2 import (
        QrCodeLogin,
        QrCodeLoginChannel,
        QrCodeLoginEvents,
    )

    qr = QrCodeLogin(QrCodeLoginChannel.WEB)
    await qr.generate_qrcode()

    # 在浏览器中打开二维码图片
    qr_image_path = Path(tempfile.gettempdir()) / "qrcode.png"
    if qr_image_path.exists():
        webbrowser.open(f"file://{qr_image_path}")
        console.print("[bold blue]已在浏览器中打开二维码，请使用B站App扫码登录[/bold blue]")
    else:
        console.print("[yellow]无法打开二维码图片，请手动访问以下链接扫码：")
        # fallback: 获取二维码链接（私有属性，通过 name mangling 访问）
        qr_link = getattr(qr, "_QrCodeLogin__qr_link", "")
        if qr_link:
            console.print(f"[blue]{qr_link}")
        else:
            console.print("[red]无法获取二维码链接")

    # 轮询等待扫码
    last_state = None
    elapsed = 0
    timeout = 120

    while elapsed < timeout:
        await asyncio.sleep(2)
        elapsed += 2

        state = await qr.check_state()

        if state == QrCodeLoginEvents.DONE:
            console.print("[green]登录成功!")
            credential = qr.get_credential()

            # 获取 buvid3
            buvid3 = ""
            try:
                from bilibili_api.utils.network import get_buvid

                buvid_result = await get_buvid()
                buvid3 = buvid_result[0] if buvid_result else ""
            except Exception as e:
                console.print(f"[yellow]获取 buvid3 失败（不影响主要功能）: {e}")

            return credential, buvid3

        if state != last_state:
            if state == QrCodeLoginEvents.SCAN:
                console.print("[yellow]已扫码，请在手机上确认登录...")
            elif state == QrCodeLoginEvents.CONF:
                console.print("[yellow]等待确认中...")
            elif state == QrCodeLoginEvents.TIMEOUT:
                console.print("[red]二维码已过期")
                break
            last_state = state

    raise RuntimeError("二维码登录超时或已过期，请重试")


def run_qrcode_login() -> tuple:
    """同步包装：执行二维码扫码登录。"""
    return asyncio.run(_qrcode_login())


def get_credential(config) -> tuple:
    """
    统一凭据获取入口。

    三级策略：
    1. .env 配置优先
    2. 缓存文件（验证有效性）
    3. 触发扫码登录

    Args:
        config: AppConfig 实例

    Returns:
        (Credential, buvid3) 元组
    """
    # 策略一：.env 手动配置
    if config.bilibili.sessdata:
        from bilibili_api import Credential

        console.print("[dim]使用 .env 中的 Cookie 凭据")
        credential = Credential(
            sessdata=config.bilibili.sessdata,
            bili_jct=config.bilibili.bili_jct,
        )
        return credential, config.bilibili.buvid3

    # 策略二：缓存文件
    cached = load_cached_credential(config.credentials_cache)
    if cached is not None:
        credential, buvid3, saved_at = cached
        # 24h 内跳过 API 验证，减少网络请求
        skip_check = False
        if saved_at:
            try:
                age = (datetime.now() - datetime.fromisoformat(saved_at)).total_seconds()
                skip_check = age < 86400
            except (ValueError, TypeError):
                pass
        if skip_check:
            console.print("[dim]使用缓存凭据（24h 内）")
            return credential, buvid3
        console.print("[dim]检查缓存凭据有效性...")
        if is_credential_valid(credential):
            console.print("[dim]使用缓存凭据")
            # 刷新 saved_at 时间戳
            save_credential(credential, buvid3, config.credentials_cache)
            return credential, buvid3
        else:
            console.print("[yellow]缓存凭据已过期，将重新登录")

    # 策略三：扫码登录
    try:
        credential, buvid3 = run_qrcode_login()
        save_credential(credential, buvid3, config.credentials_cache)
        return credential, buvid3
    except Exception as e:
        console.print(f"[red]扫码登录失败: {e}")
        console.print(
            "[red]无法获取B站凭据。请手动在 .env 中配置 BILIBILI_SESSDATA 和 BILIBILI_BILI_JCT，"
            "或运行 python main.py login 重新扫码登录"
        )
        sys.exit(1)
