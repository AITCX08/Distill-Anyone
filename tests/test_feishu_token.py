import pytest

from src.feishu.minutes import extract_minute_token


def test_extract_from_raw_token():
    tok = "obcnq3b9jl72l83w4f149w9c"  # 恰好 24 位
    assert extract_minute_token(tok) == tok


def test_extract_from_full_url():
    url = "https://sample.feishu.cn/minutes/obcnq3b9jl72l83w4f149w9c"
    assert extract_minute_token(url) == "obcnq3b9jl72l83w4f149w9c"


def test_extract_strips_equal_mask():
    url = "https://sample.feishu.cn/minutes/==obcnq3b9jl72l83w4f149w9c=="
    assert extract_minute_token(url) == "obcnq3b9jl72l83w4f149w9c"


def test_extract_ignores_query_and_anchor():
    url = "https://x.feishu.cn/minutes/obcnq3b9jl72l83w4f149w9c?from=share#top"
    assert extract_minute_token(url) == "obcnq3b9jl72l83w4f149w9c"


def test_extract_empty_raises():
    with pytest.raises(ValueError):
        extract_minute_token("   ")


def test_extract_no_token_raises():
    with pytest.raises(ValueError):
        extract_minute_token("https://x.feishu.cn/docs/short")


def test_extract_rejects_overlong_run():
    # 25 位连续 alphanumeric：没有恰好 24 位的边界匹配 → 应抛 ValueError，而不是静默截断
    with pytest.raises(ValueError):
        extract_minute_token("a" * 25)
