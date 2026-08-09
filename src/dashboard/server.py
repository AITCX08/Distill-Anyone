"""Dashboard server lifecycle with an intentionally fixed loopback bind."""

from __future__ import annotations

import webbrowser
import subprocess
import sys
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

from src.application.service import DistillationService
from src.dashboard.app import create_dashboard_app
from src.dashboard.series_bridge import SeriesTaskBridge, SeriesTaskMonitor
from src.dashboard.series_control import SeriesController
from src.dashboard.security import validate_host
from src.orchestration.manager import TaskManager
from src.orchestration.store import OrchestrationStore


def _probe_health(url: str) -> bool:
    try:
        with urlopen(f"{url}/api/v1/health", timeout=1) as response:  # noqa: S310
            return response.status == 200
    except (OSError, URLError):
        return False


def _build_task_manager(service: DistillationService) -> TaskManager:
    """Build the private process owner from the same local data root as Dashboard."""

    data_dir = service.repository.root.parent
    return TaskManager(
        store=OrchestrationStore(data_dir / "orchestration.sqlite3"),
        worker_root=data_dir / "workers",
    )


def _run_task_manager_loop(
    task_manager: TaskManager,
    server: uvicorn.Server,
    *,
    interval_seconds: float = 0.25,
) -> None:
    """Continuously harvest worker JSONL and launch queued work without a console window."""

    while not server.should_exit:
        task_manager.tick()
        sleep(interval_seconds)


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
    app.state.task_manager = _build_task_manager(service)
    app.state.task_manager.reconcile()
    monitor = SeriesTaskMonitor(
        SeriesTaskBridge(
            data_dir=service.repository.root.parent,
            events=service.events,
            orchestration_store=app.state.task_manager.store,
        )
    )
    monitor.start()
    app.state.series_task_monitor = monitor
    data_dir = service.repository.root.parent

    def launch_series(bvid: str) -> None:
        if bvid != "BV18bLkztE7R":
            raise LookupError("the requested series has no registered local runner")
        runner = data_dir.parent / ".local-artifacts" / "bilibili-series" / "resume_with_dashboard_credential.py"
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [sys.executable, str(runner)],
            cwd=data_dir.parent,
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    app.state.series_controller = SeriesController(data_dir, launcher=launch_series)
    url = f"http://{host}:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    Thread(
        target=_run_task_manager_loop,
        args=(app.state.task_manager, server),
        daemon=True,
        name="distill-task-manager",
    ).start()
    if open_browser:
        Thread(
            target=_open_browser_when_healthy,
            args=(server, url),
            daemon=True,
            name="distill-dashboard-browser",
        ).start()
    server.run()
