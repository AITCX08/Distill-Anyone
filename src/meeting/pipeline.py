"""会议纪要管线复用层：MeetingTranscript → 智能纪要 MD(+PDF)。

meeting（本地 txt / 音频）与 feishu-meeting（妙记录音）两个命令共用「转写之后」的
逻辑，避免在 main.py 里重复 LLM 生成 + 渲染 + PDF 降级。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console

from src.meeting.minutes_generator import MeetingMinutesGenerator
from src.meeting.models import MeetingTranscript
from src.meeting.renderer import render_markdown, render_pdf

console = Console()


def meeting_output_paths(output_dir: Path, name: str) -> Tuple[Path, Path]:
    """生成带时间戳的会议纪要 MD / PDF 路径，每次新增不覆盖。

    格式：{output_dir}/{name}-纪要-{YYYYMMDD-HHMMSS}.{md,pdf}
    """
    safe_name = (name or "meeting").strip() or "meeting"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"{safe_name}-纪要-{timestamp}"
    return output_dir / f"{stem}.md", output_dir / f"{stem}.pdf"


def transcript_to_minutes_files(
    transcript: MeetingTranscript,
    llm_client,
    output_dir: Path,
    no_pdf: bool = False,
) -> Tuple[Path, Optional[Path]]:
    """从 MeetingTranscript 生成智能纪要并渲染 MD(+PDF)。

    返回 (md_path, pdf_path|None)。先落 MD 保证有产物；PDF 失败降级为 None 不抛。
    llm_client 由调用方用 create_llm_client(provider, config) 构造好传入（本函数不碰
    LLM 工厂，便于单测注入 fake）。
    """
    console.print("[blue]生成智能纪要中...")
    minutes = MeetingMinutesGenerator(llm_client).generate(transcript)

    md_path, pdf_path = meeting_output_paths(output_dir, transcript.title)
    md_text = render_markdown(minutes, transcript)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_text, encoding="utf-8")
    console.print(f"[green]Markdown 已生成: {md_path}")

    if no_pdf:
        return md_path, None

    try:
        render_pdf(md_text, pdf_path)
        return md_path, pdf_path
    except Exception as e:
        console.print(f"[yellow]PDF 生成失败（Markdown 已生成）: {e}")
        console.print(
            "[dim]提示: weasyprint 需系统库，执行 `brew install pango`；或加 --no-pdf 只出 Markdown"
        )
        return md_path, None
