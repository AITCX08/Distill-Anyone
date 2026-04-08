"""
FunASR 语音识别引擎模块

封装 FunASR 的 paraformer-zh 模型，提供带时间戳的中文语音识别功能。
支持 VAD（语音活动检测）和标点恢复。
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

console = Console()


@dataclass
class TranscriptSegment:
    """单个转写片段"""
    id: str = ""
    text: str = ""
    start: float = 0.0    # 开始时间（秒）
    end: float = 0.0      # 结束时间（秒）
    confidence: float = 0.0


@dataclass
class TranscriptResult:
    """完整转写结果"""
    bvid: str = ""
    audio_path: str = ""
    full_text: str = ""
    segments: list[TranscriptSegment] = field(default_factory=list)
    model_name: str = ""
    source: str = "funasr"


class FunASREngine:
    """
    FunASR 语音识别引擎。

    使用阿里达摩院的 paraformer-zh 模型进行中文语音识别，
    配合 FSMN-VAD 进行语音活动检测，CT-Punc 进行标点恢复。
    """

    def __init__(
        self,
        model_name: str = "paraformer-zh",
        vad_model: str = "fsmn-vad",
        punc_model: str = "ct-punc",
        device: str = "cpu",
    ):
        """
        初始化 FunASR 引擎。

        Args:
            model_name: ASR模型名称
            vad_model: VAD模型名称
            punc_model: 标点恢复模型名称
            device: 计算设备 ("cpu" 或 "cuda:0")
        """
        self.model_name = model_name
        self.device = device

        console.print(f"[blue]正在加载 FunASR 模型: {model_name}...")

        from funasr import AutoModel

        self.model = AutoModel(
            model=model_name,
            vad_model=vad_model,
            vad_kwargs={"max_single_segment_time": 60000},  # 单段最长60秒
            punc_model=punc_model,
            device=device,
        )

        console.print("[green]FunASR 模型加载完成")

    def transcribe(self, audio_path: Path, bvid: str = "") -> TranscriptResult:
        """
        对单个音频文件进行语音识别。

        Args:
            audio_path: 音频文件路径
            bvid: 视频BV号（用于标识）

        Returns:
            TranscriptResult 转写结果
        """
        console.print(f"[blue]正在转写: {audio_path.name}")

        result = self.model.generate(
            input=str(audio_path),
            batch_size_s=300,  # 动态批处理300秒
        )

        # 解析 FunASR 输出
        segments = []
        full_text = ""

        if result and len(result) > 0:
            for idx, item in enumerate(result):
                text = item.get("text", "")
                full_text += text

                # 解析时间戳
                timestamp = item.get("timestamp", [])
                if timestamp and len(timestamp) >= 2:
                    # timestamp 格式: [[start_ms, end_ms], ...]
                    start_ms = timestamp[0][0] if timestamp[0] else 0
                    end_ms = timestamp[-1][1] if timestamp[-1] else 0
                    seg = TranscriptSegment(
                        id=f"{bvid}_seg_{idx:04d}" if bvid else f"seg_{idx:04d}",
                        text=text,
                        start=start_ms / 1000.0,
                        end=end_ms / 1000.0,
                    )
                else:
                    seg = TranscriptSegment(
                        id=f"{bvid}_seg_{idx:04d}" if bvid else f"seg_{idx:04d}",
                        text=text,
                        start=0.0,
                        end=0.0,
                    )
                segments.append(seg)

        return TranscriptResult(
            bvid=bvid,
            audio_path=str(audio_path),
            full_text=full_text,
            segments=segments,
            model_name=self.model_name,
            source="funasr",
        )

    def transcribe_batch(self, audio_paths: list[Path],
                         bvids: Optional[list[str]] = None) -> list[TranscriptResult]:
        """
        批量转写音频文件。

        Args:
            audio_paths: 音频文件路径列表
            bvids: 对应的BV号列表

        Returns:
            转写结果列表
        """
        if bvids is None:
            bvids = [p.stem for p in audio_paths]

        results = []
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("语音识别", total=len(audio_paths))

            for audio_path, bvid in zip(audio_paths, bvids):
                progress.update(task, description=f"转写 {bvid}")
                try:
                    result = self.transcribe(audio_path, bvid)
                    results.append(result)
                except Exception as e:
                    console.print(f"[red]转写失败 {bvid}: {e}")

                progress.advance(task)

        console.print(f"[green]语音识别完成: {len(results)}/{len(audio_paths)} 成功")
        return results


def save_transcript(result: TranscriptResult, video_meta: dict,
                    output_dir: Path) -> Path:
    """
    保存转写结果为RAG兼容的JSON格式。

    Args:
        result: 转写结果
        video_meta: 视频元信息（标题、播放量等）
        output_dir: 输出目录

    Returns:
        保存的文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{result.bvid}.json"

    data = {
        "bvid": result.bvid,
        "title": video_meta.get("title", ""),
        "source": result.source,
        "model": result.model_name,
        "full_text": result.full_text,
        "segments": [asdict(seg) for seg in result.segments],
        "metadata": {
            "pubdate": video_meta.get("pubdate", 0),
            "duration": video_meta.get("duration", ""),
            "view_count": video_meta.get("view_count", 0),
            "comment_count": video_meta.get("comment_count", 0),
            "description": video_meta.get("description", ""),
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path


def load_transcript(input_path: Path) -> dict:
    """从JSON文件加载转写结果。"""
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)
