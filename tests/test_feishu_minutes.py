import pytest

from src.feishu import minutes as M
from src.feishu.errors import MinuteNotReadyError, MinutePermissionError


class _Client:
    """get_media_download_url 只用到 base_url / timeout / auth_headers()。"""
    base_url = "https://open.feishu.cn/open-apis"
    timeout = 15

    def auth_headers(self):
        return {"Authorization": "Bearer t-test"}


class _MediaResp:
    def __init__(self, json_data):
        self._json = json_data
        self.headers = {"X-Tt-Logid": "lg-1"}

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_get_media_download_url_success(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _MediaResp({"code": 0, "data": {"download_url": "https://dl.example/abc"}})

    monkeypatch.setattr("src.feishu.minutes.requests.get", fake_get)
    url = M.get_media_download_url(_Client(), "obcnq3b9jl72l83w4f149w9c")
    assert url == "https://dl.example/abc"
    assert captured["url"].endswith("/minutes/v1/minutes/obcnq3b9jl72l83w4f149w9c/media")
    assert captured["headers"] == {"Authorization": "Bearer t-test"}


def test_get_media_download_url_not_ready(monkeypatch):
    monkeypatch.setattr(
        "src.feishu.minutes.requests.get",
        lambda url, headers=None, timeout=None: _MediaResp({"code": 2091003, "msg": "not ready"}),
    )
    with pytest.raises(MinuteNotReadyError):
        M.get_media_download_url(_Client(), "obcnq3b9jl72l83w4f149w9c")


def test_get_media_download_url_permission(monkeypatch):
    monkeypatch.setattr(
        "src.feishu.minutes.requests.get",
        lambda url, headers=None, timeout=None: _MediaResp({"code": 2091005, "msg": "deny"}),
    )
    with pytest.raises(MinutePermissionError):
        M.get_media_download_url(_Client(), "obcnq3b9jl72l83w4f149w9c")


def test_get_media_download_url_missing_url_raises(monkeypatch):
    from src.feishu.errors import FeishuError
    monkeypatch.setattr(
        "src.feishu.minutes.requests.get",
        lambda url, headers=None, timeout=None: _MediaResp({"code": 0, "data": {}}),
    )
    with pytest.raises(FeishuError):
        M.get_media_download_url(_Client(), "obcnq3b9jl72l83w4f149w9c")


class _HttpErrResp:
    headers = {}

    def raise_for_status(self):
        import requests
        raise requests.HTTPError("500 Server Error")

    def json(self):  # 不应被调用：raise_for_status 必须先于业务码解析
        raise AssertionError("json() should not be reached after raise_for_status")


def test_get_media_download_url_http_error_before_business(monkeypatch):
    from src.feishu.errors import FeishuError
    monkeypatch.setattr(
        "src.feishu.minutes.requests.get",
        lambda url, headers=None, timeout=None: _HttpErrResp(),
    )
    with pytest.raises(FeishuError):
        M.get_media_download_url(_Client(), "obcnq3b9jl72l83w4f149w9c")


class _StreamResp:
    def __init__(self, chunks):
        self._chunks = chunks
        self.closed = False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=8192):
        for c in self._chunks:
            yield c

    def close(self):
        self.closed = True


def test_download_file_writes_bytes(monkeypatch, tmp_path):
    resp = _StreamResp([b"hello ", b"world"])
    monkeypatch.setattr(
        "src.feishu.minutes.requests.get",
        lambda url, stream=False, timeout=None: resp,
    )
    dest = tmp_path / "sub" / "out.media"
    result = M.download_file("https://dl.example/abc", dest)
    assert result == dest
    assert dest.exists()
    assert dest.read_bytes() == b"hello world"
    assert resp.closed is True  # 确保连接关闭


def test_download_minute_media_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setattr(M, "get_media_download_url", lambda client, token: "https://dl/x")
    monkeypatch.setattr(
        "src.feishu.minutes.requests.get",
        lambda url, stream=False, timeout=None: _StreamResp([b"AUDIO"]),
    )
    dest = tmp_path / "feishu-tok.media"
    out = M.download_minute_media(object(), "obcnq3b9jl72l83w4f149w9c", dest)
    assert out == dest
    assert dest.read_bytes() == b"AUDIO"


def test_get_media_download_url_network_error_wrapped(monkeypatch):
    import requests
    from src.feishu.errors import FeishuError
    def boom(url, headers=None, timeout=None):
        raise requests.ConnectionError("no network")
    monkeypatch.setattr("src.feishu.minutes.requests.get", boom)
    with pytest.raises(FeishuError):
        M.get_media_download_url(_Client(), "obcnq3b9jl72l83w4f149w9c")


def test_download_file_network_error_wrapped(monkeypatch, tmp_path):
    import requests
    from src.feishu.errors import FeishuError
    def boom(url, stream=False, timeout=None):
        raise requests.ConnectionError("no network")
    monkeypatch.setattr("src.feishu.minutes.requests.get", boom)
    with pytest.raises(FeishuError):
        M.download_file("https://dl/x", tmp_path / "out.media")
