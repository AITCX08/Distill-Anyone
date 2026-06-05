"""音频 → 带说话人的 MeetingTranscript（阶段二）。

流程：ffmpeg 转 16kHz 单声道 WAV → FunASR(cam++ 说话人分离) → 合并同一人连续发言。
产出的 MeetingTranscript 与阶段一 txt 解析同构，下游 generate/render 完全复用。
"""

import subprocess
import tempfile
from pathlib import Path

from rich.console import Console

from src.meeting.models import TranscriptLine, MeetingTranscript

console = Console()

# 依赖 PATH 里的 ffmpeg（/opt/homebrew/bin 已在 PATH）
FFMPEG_BIN = "ffmpeg"


def convert_to_wav16k(src: Path, dst: Path, ffmpeg_bin: str = FFMPEG_BIN) -> None:
    """用 ffmpeg 把任意音频转成 16kHz 单声道 WAV（paraformer 要求）。失败抛 RuntimeError。

    ffmpeg_bin 可由调用方（命令层从 config.ffmpeg_bin）覆盖，默认走 PATH 里的 "ffmpeg"。
    """
    cmd = [
        ffmpeg_bin, "-i", str(src),
        "-ar", "16000", "-ac", "1", "-y", str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "ignore")[:500]
        raise RuntimeError(f"ffmpeg 转码失败（exit={proc.returncode}）: {stderr}")


def _fmt_ts(seconds: float) -> str:
    """秒 → MM:SS（<1h）或 HH:MM:SS（≥1h），零填充。"""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _merge_consecutive(segments) -> list:
    """把相邻同一说话人的句子合并成一个发言块（贴飞书逐字稿风格）。

    speaker 为空时归 "说话人 1"；timestamp 取该段首句起点；跳过空文本。
    返回 list[TranscriptLine]。
    """
    lines: list[TranscriptLine] = []
    cur = None
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        speaker = seg.speaker or "说话人 1"
        if cur is not None and cur.speaker == speaker:
            cur.text += text
        else:
            if cur is not None:
                lines.append(cur)
            cur = TranscriptLine(speaker=speaker, timestamp=_fmt_ts(seg.start), text=text)
    if cur is not None:
        lines.append(cur)
    return lines


def audio_to_transcript(audio_path: Path, config) -> MeetingTranscript:
    """音频文件 → MeetingTranscript（带说话人）。"""
    # FunASR/torch 是重依赖，函数内 lazy import（根级硬规则 #4）
    from src.asr.funasr_engine import FunASREngine

    audio_path = Path(audio_path)
    transcript = MeetingTranscript()

    with tempfile.TemporaryDirectory() as tmpd:
        wav = Path(tmpd) / "audio_16k.wav"
        console.print(f"[blue]转码音频 → 16kHz 单声道 WAV: {audio_path.name}")
        convert_to_wav16k(audio_path, wav, ffmpeg_bin=getattr(config, "ffmpeg_bin", FFMPEG_BIN))
        console.print("[blue]FunASR 转写 + cam++ 说话人分离中（首次会下载 cam++ 模型）...")
        engine = FunASREngine(spk_model="cam++", model_dir=config.model_cache_dir)
        result = engine.transcribe(wav)

    transcript.lines = _merge_consecutive(result.segments)
    if not transcript.lines:
        console.print("[yellow]转写结果为空（可能是静默音频或转码/识别异常），仅生成空纪要")

    # 说话人去重保序
    seen = set()
    for ln in transcript.lines:
        if ln.speaker not in seen:
            seen.add(ln.speaker)
            transcript.speakers.append(ln.speaker)

    # 时长 = 末句 end
    if result.segments:
        transcript.duration_str = _fmt_ts(result.segments[-1].end)

    return transcript
