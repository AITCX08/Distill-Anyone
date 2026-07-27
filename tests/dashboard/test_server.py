from types import SimpleNamespace

from src.dashboard import server


def test_browser_opens_only_after_the_loopback_health_probe(monkeypatch):
    opened = []
    instance = SimpleNamespace(started=True, should_exit=False)
    monkeypatch.setattr(server, "_probe_health", lambda url: True)
    monkeypatch.setattr(server.webbrowser, "open", opened.append)

    opened_after_health = server._open_browser_when_healthy(
        instance,
        "http://127.0.0.1:8765",
        timeout_seconds=0.01,
        poll_seconds=0,
    )

    assert opened_after_health is True
    assert opened == ["http://127.0.0.1:8765"]


def test_browser_is_not_opened_when_the_health_probe_fails(monkeypatch):
    opened = []
    instance = SimpleNamespace(started=True, should_exit=False)
    monkeypatch.setattr(server, "_probe_health", lambda url: False)
    monkeypatch.setattr(server.webbrowser, "open", opened.append)

    opened_after_health = server._open_browser_when_healthy(
        instance,
        "http://127.0.0.1:8765",
        timeout_seconds=0.01,
        poll_seconds=0,
    )

    assert opened_after_health is False
    assert opened == []
