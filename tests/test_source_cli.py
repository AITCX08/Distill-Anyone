from click.testing import CliRunner
from pathlib import Path

import main
from src.config import AppConfig


def test_cli_help_and_background_runner_use_distill_everything_identifier():
    result = CliRunner().invoke(main.cli, ["--help"])
    runner_script = Path("scripts/run-pytest-background.cmd").read_text(encoding="utf-8")

    assert result.exit_code == 0, result.output
    assert "Distill-Everything" in result.output
    assert "DISTILL_EVERYTHING_PYTHON" in runner_script
    assert "DISTILL_ANYONE_PYTHON" not in runner_script


def test_source_creator_defaults_to_both_and_three_one_three(monkeypatch):
    captured = []
    monkeypatch.setattr(main, "execute_source_request", lambda request: captured.append(request) or 0)

    result = CliRunner().invoke(
        main.cli,
        ["source", "creator", "https://v.douyin.com/x/", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    request = captured[0]
    assert request.emit == ("episodes", "skill")
    assert (request.download_workers, request.asr_workers, request.llm_workers) == (3, 1, 3)
    assert request.max_active_items == 3
    assert request.dry_run is True


def test_source_help_lists_public_commands():
    result = CliRunner().invoke(main.cli, ["source", "--help"])

    assert result.exit_code == 0
    for command in ("platforms", "status", "login", "creator"):
        assert command in result.output


def test_creator_help_documents_recovery_and_output_controls():
    result = CliRunner().invoke(main.cli, ["source", "creator", "--help"])

    assert result.exit_code == 0
    for option in (
        "--download-workers",
        "--asr-workers",
        "--llm-workers",
        "--resume",
        "--retry-failed",
        "--keep-media",
        "--headful",
        "--dry-run",
        "--emit",
        "--rag-chunks",
    ):
        assert option in result.output


def test_distillation_config_defaults_match_cli():
    config = AppConfig()

    assert config.distillation.emit == ("episodes", "skill")
    assert (
        config.distillation.download_workers,
        config.distillation.asr_workers,
        config.distillation.llm_workers,
    ) == (3, 1, 3)
    assert config.distillation.max_active_items == 3
    assert config.douyin.profile_dir == config.data_dir / "browser" / "douyin"


def test_source_event_hub_persists_only_redacted_events_under_data_dir(tmp_path):
    events = main.build_source_event_hub(AppConfig(data_dir=tmp_path))

    events.publish("trace.appended", {"line": "SESSDATA=not-for-disk"})

    persisted = (tmp_path / "dashboard-events.jsonl").read_text(encoding="utf-8")
    assert "not-for-disk" not in persisted
    assert "[REDACTED]" in persisted


def test_source_creator_uses_environment_defaults(monkeypatch, tmp_path):
    captured = []
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("DISTILL_DOWNLOAD_WORKERS", "5")
    monkeypatch.setenv("DISTILL_LLM_WORKERS", "4")
    monkeypatch.setenv("DISTILL_MAX_ACTIVE", "2")
    monkeypatch.setenv("DISTILL_RETRY_LIMIT", "6")
    monkeypatch.setenv("DISTILL_KEEP_MEDIA", "true")
    monkeypatch.setattr(main, "execute_source_request", lambda request: captured.append(request) or 0)

    result = CliRunner().invoke(
        main.cli,
        ["source", "creator", "https://v.douyin.com/x/", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    request = captured[0]
    assert request.download_workers == 5
    assert request.llm_workers == 4
    assert request.max_active_items == 2
    assert request.retry_limit == 6
    assert request.keep_media is True


def test_explicit_source_options_override_environment(monkeypatch, tmp_path):
    captured = []
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("DISTILL_DOWNLOAD_WORKERS", "5")
    monkeypatch.setattr(main, "execute_source_request", lambda request: captured.append(request) or 0)

    result = CliRunner().invoke(
        main.cli,
        [
            "source",
            "creator",
            "https://v.douyin.com/x/",
            "--dry-run",
            "--download-workers",
            "7",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured[0].download_workers == 7


def test_legacy_run_uid_delegates_to_bilibili_source_request(monkeypatch):
    captured = []
    monkeypatch.setattr(main, "execute_source_request", lambda request: captured.append(request) or 0)

    result = CliRunner().invoke(main.cli, ["run", "--uid", "12345678"])

    assert result.exit_code == 0, result.output
    assert len(captured) == 1
    request = captured[0]
    assert request.target == "https://space.bilibili.com/12345678"
    assert request.platform == "bilibili"
    assert request.emit == ("skill",)
