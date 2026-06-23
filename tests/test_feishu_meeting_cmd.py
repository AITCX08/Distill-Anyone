from click.testing import CliRunner

import main as main_mod
from src.meeting.models import MeetingTranscript, TranscriptLine


def test_feishu_meeting_wires_download_transcribe_pipeline(monkeypatch, tmp_path):
    calls = {}

    # 1) 配置：给足凭证 + 输出到 tmp
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec_y")

    # 2) mock 下载：假装写出媒体文件
    def fake_download(client, minute_token, dest_path):
        from pathlib import Path
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"FAKEAUDIO")
        calls["download_token"] = minute_token
        calls["download_dest"] = dest_path
        return dest_path

    monkeypatch.setattr("src.feishu.minutes.download_minute_media", fake_download)

    # 3) mock 本地转写：返回一个最小 transcript
    def fake_transcribe(audio_path, config):
        calls["transcribe_path"] = audio_path
        return MeetingTranscript(
            title="", lines=[TranscriptLine("说话人 1", "00:01", "你好")], speakers=["说话人 1"]
        )

    monkeypatch.setattr("src.meeting.audio_transcriber.audio_to_transcript", fake_transcribe)

    # 4) mock LLM 工厂 + 管线（不真跑 LLM / 渲染）
    monkeypatch.setattr("src.clean.text_processor.create_llm_client", lambda provider, config: object())

    def fake_pipeline(transcript, llm_client, output_dir, no_pdf=False):
        calls["pipeline_title"] = transcript.title
        calls["pipeline_no_pdf"] = no_pdf
        return (tmp_path / "x.md", None)

    monkeypatch.setattr("src.meeting.pipeline.transcript_to_minutes_files", fake_pipeline)

    runner = CliRunner()
    result = runner.invoke(
        main_mod.cli,
        ["feishu-meeting", "--url",
         "https://x.feishu.cn/minutes/obcnq3b9jl72l83w4f149w9c", "--no-pdf"],
    )

    assert result.exit_code == 0, result.output
    assert calls["download_token"] == "obcnq3b9jl72l83w4f149w9c"
    # transcript.title 缺省回落到 minute_token
    assert calls["pipeline_title"] == "obcnq3b9jl72l83w4f149w9c"
    assert calls["pipeline_no_pdf"] is True


def test_feishu_meeting_download_error_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec_y")

    def boom(client, minute_token, dest_path):
        from src.feishu.errors import MinuteNotReadyError
        raise MinuteNotReadyError("妙记尚未转写完成，请稍后再试", code=2091003)

    monkeypatch.setattr("src.feishu.minutes.download_minute_media", boom)

    runner = CliRunner()
    result = runner.invoke(
        main_mod.cli,
        ["feishu-meeting", "--url", "obcnq3b9jl72l83w4f149w9c"],
    )
    assert result.exit_code != 0
    assert "妙记尚未转写完成" in result.output


def test_feishu_meeting_bad_url_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec_y")
    runner = CliRunner()
    # 链接里没有 24 位 token → extract_minute_token 抛 ValueError → 红字 + 非零退出
    result = runner.invoke(
        main_mod.cli, ["feishu-meeting", "--url", "https://x.feishu.cn/docs/short"]
    )
    assert result.exit_code != 0
    assert "无法解析" in result.output


def test_feishu_meeting_llm_none_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec_y")

    def fake_download(client, minute_token, dest_path):
        from pathlib import Path
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"FAKEAUDIO")
        return dest_path

    monkeypatch.setattr("src.feishu.minutes.download_minute_media", fake_download)
    monkeypatch.setattr(
        "src.meeting.audio_transcriber.audio_to_transcript",
        lambda audio_path, config: MeetingTranscript(
            title="", lines=[TranscriptLine("说话人 1", "00:01", "你好")], speakers=["说话人 1"]
        ),
    )
    # LLM 工厂返回 None → 命令应红字报错并以非零码退出
    monkeypatch.setattr(
        "src.clean.text_processor.create_llm_client", lambda provider, config: None
    )

    runner = CliRunner()
    result = runner.invoke(main_mod.cli, ["feishu-meeting", "--url", "obcnq3b9jl72l83w4f149w9c"])
    assert result.exit_code != 0
    assert "LLM" in result.output
