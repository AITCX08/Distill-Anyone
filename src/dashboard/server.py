"""Dashboard server lifecycle with an intentionally fixed loopback bind."""

from __future__ import annotations

import json
import os
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


def _worker_python_executable() -> str:
    """Use the console interpreter for child work while keeping it windowless.

    Dashboard itself is deliberately launched through ``pythonw.exe``. A
    checkpointed worker needs the matching ``python.exe`` instead: it honors
    redirected stderr and gives the runner a normal process environment.
    ``CREATE_NO_WINDOW`` below prevents a console from appearing.
    """

    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        console_executable = executable.with_name("python.exe")
        if console_executable.is_file():
            return str(console_executable)
    return str(executable)


def _record_series_runner_exit(process: subprocess.Popen[object], log_path: Path) -> None:
    """Persist the child exit result without ever opening a terminal window."""

    return_code = process.wait()
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[dashboard] series runner exited with code {return_code}\n")


def _series_worker_environment(data_dir: Path) -> dict[str, str]:
    """Read local Bilibili credentials without exposing them to UI or logs."""

    try:
        credentials = json.loads((data_dir / ".credentials.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("本地哔哩哔哩登录凭据不可用，请先在 Dashboard 登录") from error
    if not isinstance(credentials, dict) or not credentials.get("sessdata") or not credentials.get("bili_jct"):
        raise RuntimeError("本地哔哩哔哩登录凭据不可用，请先在 Dashboard 登录")
    environment = dict(os.environ)
    environment.update(
        {
            "BILIBILI_SESSDATA": str(credentials["sessdata"]),
            "BILIBILI_BILI_JCT": str(credentials["bili_jct"]),
            "BILIBILI_BUVID3": str(credentials.get("buvid3") or ""),
        }
    )
    return environment


def _series_worker_creation_flags() -> int:
    """Create a fully detached, windowless Windows worker process."""

    return (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
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


def build_dashboard_server(app: object, *, host: str, port: int) -> uvicorn.Server:
    """Build a server that remains valid when launched by ``pythonw``.

    Uvicorn's default color formatter reads ``sys.stdout.isatty()`` during
    configuration.  ``pythonw`` deliberately exposes no stdout/stderr, so the
    Dashboard must opt out of Uvicorn's console log configuration.
    """

    return uvicorn.Server(
        uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            log_config=None,
            access_log=False,
        )
    )


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
    app.state.task_manager.claim_ownership()
    app.state.task_manager.reconcile()
    data_dir = service.repository.root.parent

    def launch_series(bvid: str) -> int:
        if bvid != "BV18bLkztE7R":
            raise LookupError("the requested series has no registered local runner")
        runner = data_dir.parent / ".local-artifacts" / "bilibili-series" / "distill_tianji_sizhu.py"
        log_path = data_dir / "series" / bvid / "runner.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        flags = _series_worker_creation_flags()
        with log_path.open("a", encoding="utf-8") as log_file:
            interpreter = _worker_python_executable()
            log_file.write(f"[dashboard] starting series runner with {interpreter}\n")
            log_file.flush()
            process = subprocess.Popen(
                [interpreter, str(runner)],
                cwd=data_dir.parent,
                creationflags=flags,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=_series_worker_environment(data_dir),
            )
        Thread(
            target=_record_series_runner_exit,
            args=(process, log_path),
            daemon=True,
            name=f"distill-series-runner-{bvid}",
        ).start()
        return process.pid

    app.state.series_controller = SeriesController(data_dir, launcher=launch_series)
    monitor = SeriesTaskMonitor(
        SeriesTaskBridge(
            data_dir=data_dir,
            events=service.events,
            orchestration_store=app.state.task_manager.store,
        ),
        reconcile=app.state.series_controller.reconcile,
    )
    monitor.start()
    app.state.series_task_monitor = monitor
    url = f"http://{host}:{port}"
    server = build_dashboard_server(app, host=host, port=port)
    try:
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
    finally:
        monitor.stop()
        app.state.task_manager.release_ownership()
