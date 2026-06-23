"""飞书妙记（Minutes）下载：链接 → minute_token → 临时 download_url → 本地文件。"""

from __future__ import annotations

import re

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
