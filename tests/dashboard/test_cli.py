from click.testing import CliRunner
from types import SimpleNamespace

import main


def test_dashboard_cli_uses_no_open_and_exposes_no_host_option(monkeypatch):
    service = object()
    captured = []
    monkeypatch.setattr(main, "build_dashboard_service", lambda config: service)
    monkeypatch.setattr(main, "run_dashboard", lambda value, port, open_browser: captured.append((value, port, open_browser)))

    result = CliRunner().invoke(main.cli, ["dashboard", "--port", "8765", "--no-open"])
    help_result = CliRunner().invoke(main.cli, ["dashboard", "--help"])

    assert result.exit_code == 0, result.output
    assert captured == [(service, 8765, False)]
    assert help_result.exit_code == 0
    assert "--host" not in help_result.output


def test_dashboard_service_uses_runner_preview_without_cli_live_renderer(monkeypatch, tmp_path):
    captured = {}

    class Runner:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.platform_manager = kwargs["platform_manager"]

        def preview(self, request):
            raise AssertionError("not invoked during service construction")

    monkeypatch.setattr(main, "SourceDistillationRunner", Runner)
    monkeypatch.setattr(main, "build_source_event_hub", lambda config: object())
    monkeypatch.setattr(main, "build_platform_manager", lambda config: object())

    service = main.build_dashboard_service(SimpleNamespace(data_dir=tmp_path))

    assert service.source_runner.platform_manager is captured["platform_manager"]
    assert service.commands.previewer == service.source_runner.preview
    assert "engine_executor" not in captured
