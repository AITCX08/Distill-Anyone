"""飞书妙记（Minutes）下载：链接 → minute_token → 临时 download_url → 本地文件。"""

from __future__ import annotations

import re
from pathlib import Path

import requests

from src.feishu.errors import FeishuError, raise_for_feishu_code

# 妙记 token：恰好 24 位 [A-Za-z0-9]，两侧需为非 alphanumeric 边界（避免在更长串里误截前 24 位）
_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{24}(?![A-Za-z0-9])")


def extract_minute_token(url_or_token: str) -> str:
    """从妙记分享链接或原始 token 中提取 24 位 minute_token。

    支持：
      - 原始 token："obcnq3b9jl72l83w4f149w9c"
      - 完整链接："https://xxx.feishu.cn/minutes/<token>"
      - 带 == 掩码 / ?query / #anchor 的链接
    取不到 24 位 token 时抛 ValueError。
    """
    if not url_or_token or not url_or_token.strip():
        raise ValueError("妙记链接或 token 不能为空")
    text = url_or_token.strip()
    if "/minutes/" in text:
        text = text.split("/minutes/", 1)[1]
    text = text.split("?", 1)[0].split("#", 1)[0]
    m = _TOKEN_RE.search(text)
    if not m:
        raise ValueError(f"无法从输入中提取 24 位 minute_token：{url_or_token!r}")
    return m.group(0)


def get_media_download_url(client, minute_token: str) -> str:
    """调妙记 media 接口，返回临时下载地址 download_url（有效期约 1 天）。

    注意：该接口返回 JSON（含 download_url），不是二进制流。失败按飞书错误码抛
    对应异常（见 src/feishu/errors.py）。client 需提供 base_url / timeout / auth_headers()。
    """
    resp = requests.get(
        f"{client.base_url}/minutes/v1/minutes/{minute_token}/media",
        headers=client.auth_headers(),
        timeout=client.timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    log_id = resp.headers.get("X-Tt-Logid") if getattr(resp, "headers", None) else None
    raise_for_feishu_code(data.get("code", -1), data.get("msg", ""), log_id=log_id)
    url = (data.get("data") or {}).get("download_url")
    if not url:
        raise FeishuError(
            f"妙记 media 接口 code=0 但缺 download_url，响应体：{data}", code=0, log_id=log_id
        )
    return url


def download_file(url: str, dest_path, timeout: int = 60, chunk_size: int = 8192) -> Path:
    """流式下载 url 到 dest_path（自动建父目录）。返回 dest_path。"""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True, timeout=timeout)
    try:
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
    finally:
        resp.close()
    return dest_path


def download_minute_media(client, minute_token: str, dest_path) -> Path:
    """端到端：取 download_url → 下载到本地文件。返回 dest_path。

    minute_token 须为已提取的 24 位 token（调用方先用 extract_minute_token 提取）。
    """
    download_url = get_media_download_url(client, minute_token)
    return download_file(download_url, dest_path)
