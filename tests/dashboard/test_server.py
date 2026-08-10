from types import SimpleNamespace
from pathlib import Path

from fastapi import FastAPI

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


def test_dashboard_builds_a_local_task_manager_alongside_its_service(tmp_path):
    service = SimpleNamespace(repository=SimpleNamespace(root=tmp_path / "jobs"))

    manager = server._build_task_manager(service)

    assert manager.worker_root == tmp_path / "workers"
    assert manager.store.database_path == tmp_path / "orchestration.sqlite3"


def test_task_manager_loop_ticks_until_the_dashboard_server_stops():
    calls = []
    server_state = SimpleNamespace(should_exit=False)

    class Manager:
        def tick(self):
            calls.append("tick")
            server_state.should_exit = True

    server._run_task_manager_loop(Manager(), server_state, interval_seconds=0)

    assert calls == ["tick"]


def test_dashboard_server_does_not_require_console_streams() -> None:
    """The local Dashboard must also launch through pythonw without stdout/stderr."""

    dashboard_server = server.build_dashboard_server(FastAPI(), host="127.0.0.1", port=8765)

    assert dashboard_server.config.log_config is None
    assert dashboard_server.config.access_log is False
