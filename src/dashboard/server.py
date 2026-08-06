"""Dashboard server lifecycle with an intentionally fixed loopback bind."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

from src.application.service import DistillationService
from src.dashboard.app import create_dashboard_app
from src.dashboard.series_bridge import SeriesTaskBridge, SeriesTaskMonitor
from src.dashboard.security import validate_host


def _probe_health(url: str) -> bool:
    try:
        with urlopen(f"{url}/api/v1/health", timeout=1) as response:  # noqa: S310
            return response.status == 200
    except (OSError, URLError):
        return False


def _open_browser_when_healthy(
    server: uvicorn.Server,
    url: str,
    *,
    timeout_seconds: float = 10,
    poll_seconds: float = 0.05,
) -> bool:
    """Open only after the local server can answer its safe health check."""

    deadline = monotonic() + timeout_seconds
    while monotonic() <= deadline:
        if server.should_exit:
            return False
        if server.started and _probe_health(url):
            webbrowser.open(url)
            return True
        sleep(poll_seconds)
    return False


def run_dashboard(service: DistillationService, port: int, open_browser: bool) -> None:
    """Run the Dashboard locally; remote binding is deliberately unavailable."""

    if not 1 <= port <= 65535:
        raise ValueError("Dashboard port must be between 1 and 65535")
    host = validate_host("127.0.0.1")
    static_dir = Path(__file__).with_name("static")
    app = create_dashboard_app(service, static_dir, session_secret="process-local")
    monitor = SeriesTaskMonitor(
        SeriesTaskBridge(data_dir=service.repository.root.parent, events=service.events)
    )
    monitor.start()
    app.state.series_task_monitor = monitor
    url = f"http://{host}:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    if open_browser:
        Thread(
            target=_open_browser_when_healthy,
            args=(server, url),
            daemon=True,
            name="distill-dashboard-browser",
        ).start()
    server.run()
