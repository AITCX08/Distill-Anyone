from click.testing import CliRunner

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
