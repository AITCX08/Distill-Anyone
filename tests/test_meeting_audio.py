from pathlib import Path

import pytest

from src.meeting import audio_transcriber as at


def test_fmt_ts():
    assert at._fmt_ts(0) == "00:00"
    assert at._fmt_ts(59) == "00:59"
    assert at._fmt_ts(63) == "01:03"
    assert at._fmt_ts(3723) == "01:02:03"     # ≥1h 用 HH:MM:SS


def test_merge_consecutive_groups_same_speaker():
    from src.asr.funasr_engine import TranscriptSegment
    segs = [
        TranscriptSegment(text="大家好。", start=0.0, end=2.0, speaker="说话人 1"),
        TranscriptSegment(text="先说目标。", start=2.0, end=4.0, speaker="说话人 1"),
        TranscriptSegment(text="我补充一点。", start=4.0, end=6.0, speaker="说话人 2"),
        TranscriptSegment(text="好的。", start=6.0, end=7.0, speaker="说话人 1"),
    ]
    lines = at._merge_consecutive(segs)
    assert len(lines) == 3
    assert lines[0].speaker == "说话人 1"
    assert lines[0].text == "大家好。先说目标。"      # 同一人连续合并
    assert lines[0].timestamp == "00:00"             # 取段首时间
    assert lines[1].speaker == "说话人 2"
    assert lines[2].speaker == "说话人 1"             # 换回来另起一段


def test_merge_consecutive_empty_speaker_defaults_speaker1():
    from src.asr.funasr_engine import TranscriptSegment
    segs = [
        TranscriptSegment(text="一句", start=0.0, end=1.0, speaker=""),
        TranscriptSegment(text="两句", start=1.0, end=2.0, speaker=""),
    ]
    lines = at._merge_consecutive(segs)
    assert len(lines) == 1
    assert lines[0].speaker == "说话人 1"
    assert lines[0].text == "一句两句"


def test_merge_consecutive_skips_blank_text():
    from src.asr.funasr_engine import TranscriptSegment
    segs = [
        TranscriptSegment(text="  ", start=0.0, end=1.0, speaker="说话人 1"),
        TranscriptSegment(text="有内容", start=1.0, end=2.0, speaker="说话人 1"),
    ]
    lines = at._merge_consecutive(segs)
    assert len(lines) == 1
    assert lines[0].text == "有内容"


def test_convert_to_wav16k_builds_cmd(monkeypatch, tmp_path):
    captured = {}

    class FakeProc:
        returncode = 0
        stderr = b""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(at.subprocess, "run", fake_run)
    at.convert_to_wav16k(Path("in.m4a"), tmp_path / "out.wav")
    cmd = captured["cmd"]
    assert "-ar" in cmd and "16000" in cmd
    assert "-ac" in cmd and "1" in cmd
    assert str(tmp_path / "out.wav") in cmd


def test_convert_to_wav16k_raises_on_failure(monkeypatch, tmp_path):
    class FakeProc:
        returncode = 1
        stderr = b"ffmpeg: bad input"

    monkeypatch.setattr(at.subprocess, "run", lambda cmd, **kw: FakeProc())
    with pytest.raises(RuntimeError, match="ffmpeg"):
        at.convert_to_wav16k(Path("in.m4a"), tmp_path / "out.wav")


def test_audio_to_transcript_assembles(monkeypatch, tmp_path):
    from src.asr.funasr_engine import TranscriptResult, TranscriptSegment

    # 不真跑 ffmpeg
    monkeypatch.setattr(at, "convert_to_wav16k", lambda src, dst: Path(dst).write_bytes(b"x"))

    class StubEngine:
        def __init__(self, **kwargs):
            assert kwargs.get("spk_model") == "cam++"     # 验证启用了说话人分离

        def transcribe(self, audio_path, bvid=""):
            return TranscriptResult(segments=[
                TranscriptSegment(text="大家好。", start=0.0, end=3.0, speaker="说话人 1"),
                TranscriptSegment(text="继续。", start=3.0, end=6.0, speaker="说话人 1"),
                TranscriptSegment(text="我来补充。", start=6.0, end=9.0, speaker="说话人 2"),
            ])

    # audio_to_transcript 内部 `from src.asr.funasr_engine import FunASREngine`
    monkeypatch.setattr("src.asr.funasr_engine.FunASREngine", StubEngine)

    class Cfg:
        model_cache_dir = tmp_path / "cache"

    t = at.audio_to_transcript(tmp_path / "x.m4a", Cfg())
    assert t.speakers == ["说话人 1", "说话人 2"]
    assert len(t.lines) == 2
    assert t.lines[0].text == "大家好。继续。"
    assert t.lines[1].speaker == "说话人 2"
    assert t.duration_str == "00:09"      # 末句 end=9s
    assert t.keywords == []               # 音频无关键词头
    assert t.date_str == ""


def test_is_audio_file():
    import main
    assert main._is_audio_file(Path("a.m4a")) is True
    assert main._is_audio_file(Path("a.MP3")) is True      # 大小写无关
    assert main._is_audio_file(Path("a.wav")) is True
    assert main._is_audio_file(Path("全托管.txt")) is False
    assert main._is_audio_file(Path("a.docx")) is False
