import pytest

from src.feishu.errors import (
    FeishuError,
    MinuteNotReadyError,
    MinutePermissionError,
    MinuteNotFoundError,
    raise_for_feishu_code,
)


def test_code_zero_is_noop():
    # code==0 不抛
    raise_for_feishu_code(0, "ok")


def test_not_ready_2091003():
    with pytest.raises(MinuteNotReadyError) as ei:
        raise_for_feishu_code(2091003, "not ready")
    assert ei.value.code == 2091003


def test_permission_2091005():
    with pytest.raises(MinutePermissionError):
        raise_for_feishu_code(2091005, "permission deny")


def test_not_found_2091002_and_2091004():
    with pytest.raises(MinuteNotFoundError):
        raise_for_feishu_code(2091002, "not found")
    with pytest.raises(MinuteNotFoundError):
        raise_for_feishu_code(2091004, "deleted")


def test_unknown_code_falls_back_to_base():
    with pytest.raises(FeishuError) as ei:
        raise_for_feishu_code(99999, "weird")
    assert ei.value.code == 99999
    # 子类不应命中
    assert not isinstance(ei.value, (MinuteNotReadyError, MinutePermissionError, MinuteNotFoundError))


def test_log_id_passthrough():
    with pytest.raises(FeishuError) as ei:
        raise_for_feishu_code(2091006, "internal", log_id="lg-123")
    assert ei.value.log_id == "lg-123"
