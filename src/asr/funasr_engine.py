"""
FunASR 语音识别引擎模块

封装 FunASR 的 paraformer-zh 模型，提供带时间戳的中文语音识别功能。
支持 VAD（语音活动检测）和标点恢复。
"""

import json
import os
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
        device: Optional[str] = None,
        model_dir: Optional[Path] = None,
    ):
        """
        初始化 FunASR 引擎。

        Args:
            model_name: ASR模型名称
            vad_model: VAD模型名称
            punc_model: 标点恢复模型名称
            device: 计算设备 ("cpu" 或 "cuda:0")，None 时自动检测
            model_dir: 模型缓存目录，None 时使用系统默认路径
        """
        self.model_name = model_name

        import torch
        if device is None:
            if torch.cuda.is_available():
                device = "cuda:0"
                gpu_name = torch.cuda.get_device_name(0)
                total_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
                console.print(f"[green]检测到 GPU: {gpu_name} ({total_mem:.1f}GB)，使用 CUDA 加速")
            else:
                device = "cpu"
                console.print("[yellow]未检测到可用 GPU，使用 CPU 运行")
        else:
            console.print(f"[blue]使用指定设备: {device}")

        self.device = device
        self._use_cuda = device.startswith("cuda")

        # 减少 CUDA 显存碎片
        if self._use_cuda:
            os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

        if model_dir is not None:
            model_dir.mkdir(parents=True, exist_ok=True)
            os.environ["MODELSCOPE_CACHE"] = str(model_dir)
            os.environ["MS_CACHE_HOME"] = str(model_dir)
            console.print(f"[dim]模型缓存目录: {model_dir}")

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

        result = self._generate_with_oom_retry(audio_path)

        # 解析 FunASR 输出
        segments = []
        full_text = ""

        if result and len(result) > 0:
            for item in result:
                text = item.get("text", "")
                full_text += text

                # 优先使用 sentence_info 获取句子级时间戳
                sentence_info = item.get("sentence_info", [])
                if sentence_info:
                    for sent in sentence_info:
                        seg = TranscriptSegment(
                            id=f"{bvid}_seg_{len(segments):04d}" if bvid else f"seg_{len(segments):04d}",
                            text=sent.get("text", ""),
                            start=sent.get("start", 0) / 1000.0,
                            end=sent.get("end", 0) / 1000.0,
                        )
                        segments.append(seg)
                else:
                    # 降级：整块作为一个 segment
                    timestamp = item.get("timestamp", [])
                    start_ms = timestamp[0][0] if timestamp else 0
                    end_ms = timestamp[-1][1] if timestamp else 0
                    seg = TranscriptSegment(
                        id=f"{bvid}_seg_{len(segments):04d}" if bvid else f"seg_{len(segments):04d}",
                        text=text,
                        start=start_ms / 1000.0,
                        end=end_ms / 1000.0,
                    )
                    segments.append(seg)

        result_obj = TranscriptResult(
            bvid=bvid,
            audio_path=str(audio_path),
            full_text=full_text,
            segments=segments,
            model_name=self.model_name,
            source="funasr",
        )

        self._free_cuda_cache()
        return result_obj

    def _generate_with_oom_retry(self, audio_path: Path) -> list:
        """调用 FunASR 推理，CUDA OOM 时清理缓存后重试一次。"""
        try:
            return self.model.generate(
                input=str(audio_path),
                batch_size_s=300,
                sentence_timestamp=True,
            )
        except RuntimeError as e:
            if "out of memory" not in str(e).lower() or not self._use_cuda:
                raise
            console.print("[yellow]显存不足，清理缓存后重试...")
            self._free_cuda_cache()
            # 缩小 batch_size_s 重试
            return self.model.generate(
                input=str(audio_path),
                batch_size_s=60,
                sentence_timestamp=True,
            )

    def _free_cuda_cache(self) -> None:
        """释放未使用的 CUDA 显存。"""
        if self._use_cuda:
            import torch
            torch.cuda.empty_cache()

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


def check_transcript_integrity(
    transcript_path: Path,
    audio_path: Optional[Path] = None,
    tolerance: float = 60.0,
) -> tuple[bool, str]:
    """
    检查转写文件的完整性。

    Args:
        transcript_path: 转写JSON文件路径
        audio_path: 对应的音频文件路径，若提供则对比音频时长判断是否需要重新转写
        tolerance: 音频时长与转写时长允许误差（秒），默认60秒

    Returns:
        (is_valid, reason) — is_valid=False 时 reason 说明问题
    """
    if not transcript_path.exists():
        return False, "文件不存在"

    if transcript_path.stat().st_size == 0:
        return False, "文件为空"

    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return False, f"JSON 解析失败: {e}"

    if not data.get("full_text", "").strip():
        return False, "full_text 为空"

    segments = data.get("segments")
    if not segments:
        return False, "segments 为空"

    # 若提供了音频路径，对比音频实际时长与转写覆盖时长
    # 避免付费视频补全后转写内容仍是旧的短版本
    if audio_path and audio_path.exists():
        import wave
        try:
            with wave.open(str(audio_path), "rb") as wf:
                audio_duration = wf.getnframes() / float(wf.getframerate())
            transcript_end = max((s.get("end", 0) for s in segments), default=0)
            if audio_duration - transcript_end > tolerance:
                return False, (
                    f"音频已更新（时长 {audio_duration:.0f}s），"
                    f"转写仅覆盖至 {transcript_end:.0f}s，需重新转写"
                )
        except Exception:
            pass  # 无法读取音频时长，跳过此项检查

    return True, "ok"
