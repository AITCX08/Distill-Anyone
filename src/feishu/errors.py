"""飞书 API 异常 + 妙记错误码映射。

错误码来自 open.feishu.cn 妙记 media 接口文档：
2091001 参数非法 / 2091002 找不到 / 2091003 未转写完成 /
2091004 已删除 / 2091005 无权限 / 2091006 服务内部错误。
"""

from __future__ import annotations

from typing import Optional


class FeishuError(Exception):
    """飞书 API 调用异常基类。"""

    def __init__(self, message: str, code: Optional[int] = None, log_id: Optional[str] = None):
        self.code = code
        self.log_id = log_id
        super().__init__(message)


class MinuteNotReadyError(FeishuError):
    """妙记尚未转写完成（2091003），可稍后重试。"""


class MinutePermissionError(FeishuError):
    """应用对该妙记无读权限 / scope 未授予（2091005）。"""


class MinuteNotFoundError(FeishuError):
    """妙记不存在或已删除（2091002 / 2091004）。"""


# code -> (中文提示, 异常类)
_CODE_MAP = {
    2091001: ("参数非法，请检查 minute_token 是否为 24 位", FeishuError),
    2091002: ("妙记不存在，请检查链接 / token 是否正确", MinuteNotFoundError),
    2091003: ("妙记尚未转写完成，请稍后再试", MinuteNotReadyError),
    2091004: ("妙记已被删除", MinuteNotFoundError),
    2091005: (
        "应用对该妙记无读权限：请确认已授予 minutes:minutes.media:export 权限，"
        "且应用可访问该篇妙记",
        MinutePermissionError,
    ),
    2091006: ("飞书服务内部错误，请稍后重试", FeishuError),
}


def raise_for_feishu_code(code: int, msg: str = "", log_id: Optional[str] = None) -> None:
    """根据飞书返回码抛出对应异常；code==0 时不抛。"""
    if code == 0:
        return
    text, exc_cls = _CODE_MAP.get(code, (f"飞书 API 调用失败：code={code} msg={msg}", FeishuError))
    raise exc_cls(text, code=code, log_id=log_id)
