"""飞书自建应用 REST 客户端（raw HTTP）：换取并缓存 tenant_access_token。"""

from __future__ import annotations

from typing import Optional

import requests

from src.feishu.errors import FeishuError

FEISHU_BASE = "https://open.feishu.cn/open-apis"


class FeishuClient:
    """飞书自建应用客户端。

    负责用 app_id/app_secret 换取 tenant_access_token（自建应用），并提供带鉴权的
    请求头。单次 CLI 运行内缓存 token（一次命令只下载一篇妙记，几秒内完成，无需做
    30 分钟续期逻辑——那是 Stage 3 长连接场景才需要的）。
    """

    def __init__(self, app_id: str, app_secret: str, base_url: str = FEISHU_BASE, timeout: int = 15):
        if not app_id or not app_secret:
            raise FeishuError(
                "缺少飞书应用凭证：请在 .env 设置 FEISHU_APP_ID / FEISHU_APP_SECRET"
            )
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token: Optional[str] = None

    def get_tenant_access_token(self, force_refresh: bool = False) -> str:
        """换取 tenant_access_token；进程内缓存，force_refresh 强制重换。"""
        if self._token and not force_refresh:
            return self._token
        resp = requests.post(
            f"{self.base_url}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", -1) != 0:
            raise FeishuError(
                f"获取 tenant_access_token 失败：code={data.get('code')} msg={data.get('msg')}",
                code=data.get("code"),
            )
        token = data.get("tenant_access_token")
        if not token:
            raise FeishuError(
                f"换取 tenant_access_token 成功码为 0 但 token 字段缺失，响应体：{data}",
                code=data.get("code"),
            )
        self._token = token
        return self._token

    def auth_headers(self) -> dict:
        """带 tenant_access_token 的鉴权请求头。"""
        return {"Authorization": f"Bearer {self.get_tenant_access_token()}"}
