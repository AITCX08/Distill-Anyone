import pytest

from src.feishu.client import FeishuClient
from src.feishu.errors import FeishuError


class _FakeResp:
    def __init__(self, json_data, status_ok=True):
        self._json = json_data
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("http error")

    def json(self):
        return self._json


def test_empty_credentials_raises():
    with pytest.raises(FeishuError):
        FeishuClient("", "")
    with pytest.raises(FeishuError):
        FeishuClient("cli_x", "")


def test_get_token_success_and_cached(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        assert url.endswith("/auth/v3/tenant_access_token/internal")
        assert json == {"app_id": "cli_x", "app_secret": "sec_y"}
        return _FakeResp({"code": 0, "tenant_access_token": "t-abc", "expire": 7200})

    monkeypatch.setattr("src.feishu.client.requests.post", fake_post)

    client = FeishuClient("cli_x", "sec_y")
    assert client.get_tenant_access_token() == "t-abc"
    # 第二次走缓存，不再 POST
    assert client.get_tenant_access_token() == "t-abc"
    assert calls["n"] == 1


def test_get_token_force_refresh(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        return _FakeResp({"code": 0, "tenant_access_token": f"t-{calls['n']}", "expire": 7200})

    monkeypatch.setattr("src.feishu.client.requests.post", fake_post)
    client = FeishuClient("cli_x", "sec_y")
    assert client.get_tenant_access_token() == "t-1"
    assert client.get_tenant_access_token(force_refresh=True) == "t-2"
    assert calls["n"] == 2


def test_get_token_api_error_raises(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        return _FakeResp({"code": 99991663, "msg": "app not found"})

    monkeypatch.setattr("src.feishu.client.requests.post", fake_post)
    client = FeishuClient("cli_x", "sec_y")
    with pytest.raises(FeishuError):
        client.get_tenant_access_token()


def test_get_token_missing_field_raises(monkeypatch):
    monkeypatch.setattr(
        "src.feishu.client.requests.post",
        lambda url, json=None, timeout=None: _FakeResp({"code": 0, "expire": 7200}),
    )
    client = FeishuClient("cli_x", "sec_y")
    with pytest.raises(FeishuError):
        client.get_tenant_access_token()


def test_auth_headers(monkeypatch):
    monkeypatch.setattr(
        "src.feishu.client.requests.post",
        lambda url, json=None, timeout=None: _FakeResp(
            {"code": 0, "tenant_access_token": "t-xyz", "expire": 7200}
        ),
    )
    client = FeishuClient("cli_x", "sec_y")
    assert client.auth_headers() == {"Authorization": "Bearer t-xyz"}


def test_get_token_network_error_wrapped(monkeypatch):
    import requests
    def boom(url, json=None, timeout=None):
        raise requests.ConnectionError("no network")
    monkeypatch.setattr("src.feishu.client.requests.post", boom)
    client = FeishuClient("cli_x", "sec_y")
    with pytest.raises(FeishuError):
        client.get_tenant_access_token()
