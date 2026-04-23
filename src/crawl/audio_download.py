"""
音频下载模块

使用 yt-dlp 下载B站视频的音频流，支持断点续传和批量下载。
"""

import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

console = Console()

# B站视频URL模板
BILIBILI_VIDEO_URL = "https://www.bilibili.com/video/{bvid}"


def generate_cookies_file(credential, buvid3: str = "",
                          output_path: Optional[Path] = None) -> Path:
    """
    从B站凭据生成 Netscape 格式的 cookies.txt 文件。
    yt-dlp 使用此文件进行认证。

    Args:
        credential: bilibili_api.Credential 对象
        buvid3: B站 buvid3 Cookie（可选）
        output_path: cookies文件输出路径，默认使用临时文件

    Returns:
        cookies文件路径
    """
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".txt", prefix="bilibili_cookies_"))

    sessdata = credential.sessdata
    bili_jct = credential.bili_jct

    cookies_content = "# Netscape HTTP Cookie File\n"
    cookies_content += f".bilibili.com\tTRUE\t/\tFALSE\t0\tSESSDATA\t{sessdata}\n"
    cookies_content += f".bilibili.com\tTRUE\t/\tFALSE\t0\tbili_jct\t{bili_jct}\n"
    if buvid3:
        cookies_content += f".bilibili.com\tTRUE\t/\tFALSE\t0\tbuvid3\t{buvid3}\n"

    output_path.write_text(cookies_content, encoding="utf-8")
    return output_path


def parse_duration_str(duration_str: str) -> float:
    """将 'MM:SS' 或 'HH:MM:SS' 格式转换为秒数。"""
    try:
        parts = str(duration_str).strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, AttributeError):
        pass
    return 0.0


def get_audio_duration(audio_path: Path) -> float:
    """获取 WAV 文件的实际时长（秒），失败返回 0。"""
    try:
        with wave.open(str(audio_path), "rb") as f:
            return f.getnframes() / float(f.getframerate())
    except Exception:
        return 0.0


def check_audio_completeness(audio_path: Path, expected_duration_str: str,
                              tolerance: float = 30.0) -> tuple[bool, str]:
    """
    检查音频文件是否完整。

    通过比较实际时长与视频列表中记录的预期时长判断。

    Args:
        audio_path: 音频文件路径
        expected_duration_str: 视频元信息中的时长字符串（如 "10:30"）
        tolerance: 允许误差秒数（默认30秒，容纳片头片尾差异）

    Returns:
        (is_complete, reason)
    """
    if not audio_path.exists():
        return False, "文件不存在"

    if audio_path.stat().st_size < 1024:  # 小于 1KB 明显不完整
        return False, f"文件过小 ({audio_path.stat().st_size} bytes)"

    expected_secs = parse_duration_str(expected_duration_str)
    if expected_secs <= 0:
        # 无法解析预期时长，只做基础大小检查
        return True, "无法获取预期时长，跳过时长校验"

    actual_secs = get_audio_duration(audio_path)
    if actual_secs <= 0:
        return False, "无法读取音频时长（可能文件损坏）"

    diff = expected_secs - actual_secs
    if diff > tolerance:
        return False, (
            f"时长不足: 实际 {actual_secs:.0f}s / 预期 {expected_secs:.0f}s"
            f"（差 {diff:.0f}s，可能为付费视频未完整获取）"
        )

    return True, "ok"


def download_audio(
    bvid: str,
    output_dir: Path,
    audio_format: str = "wav",
    cookies_file: Optional[Path] = None,
    force: bool = False,
) -> Optional[Path]:
    """
    使用 yt-dlp 下载B站视频的音频。

    Args:
        bvid: 视频BV号
        output_dir: 输出目录
        audio_format: 音频格式 (wav/m4a/mp3)
        cookies_file: cookies文件路径
        force: 强制重新下载（忽略已存在的文件）

    Returns:
        下载后的音频文件路径，失败返回 None
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / f"{bvid}.%(ext)s")
    expected_output = output_dir / f"{bvid}.{audio_format}"

    # 如果文件已存在且不强制重新下载，跳过
    if expected_output.exists() and not force:
        console.print(f"[yellow]音频已存在，跳过: {bvid}")
        return expected_output

    # 强制重新下载时先删除旧文件
    if force and expected_output.exists():
        expected_output.unlink()
        console.print(f"[yellow]删除旧文件，重新下载: {bvid}")

    url = BILIBILI_VIDEO_URL.format(bvid=bvid)
    cmd = [
        "yt-dlp",
        "-x",                           # 提取音频
        "--audio-format", audio_format,  # 音频格式
        "-o", output_template,           # 输出路径模板
        "--no-playlist",                 # 不下载播放列表
        "--retries", "3",                # 重试次数
        "--quiet",                       # 静默模式
        "--no-warnings",
    ]

    if cookies_file and cookies_file.exists():
        cmd.extend(["--cookies", str(cookies_file)])

    cmd.append(url)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5分钟超时
        )
        if result.returncode != 0:
            console.print(f"[red]下载失败 {bvid}: {result.stderr[:200]}")
            return None

        # yt-dlp 可能输出不同扩展名，查找实际文件
        if expected_output.exists():
            return expected_output

        # 查找同名不同后缀的文件
        for f in output_dir.glob(f"{bvid}.*"):
            if f.suffix != ".part":
                return f

        console.print(f"[red]下载完成但未找到音频文件: {bvid}")
        return None

    except subprocess.TimeoutExpired:
        console.print(f"[red]下载超时: {bvid}")
        return None
    except FileNotFoundError:
        console.print("[red]未找到 yt-dlp，请先安装: pip install yt-dlp")
        return None


def batch_download(
    videos: list[dict],
    output_dir: Path,
    audio_format: str = "wav",
    cookies_file: Optional[Path] = None,
) -> list[Path]:
    """
    批量下载视频音频，自动跳过已下载的文件。

    Args:
        videos: 视频信息列表（需包含 bvid 字段）
        output_dir: 输出目录
        audio_format: 音频格式
        cookies_file: cookies文件路径

    Returns:
        成功下载的音频文件路径列表
    """
    downloaded = []

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("下载音频", total=len(videos))

        for video in videos:
            bvid = video["bvid"]
            progress.update(task, description=f"下载 {bvid}")

            path = download_audio(bvid, output_dir, audio_format, cookies_file)
            if path:
                downloaded.append(path)

            progress.advance(task)

    console.print(f"[green]音频下载完成: {len(downloaded)}/{len(videos)} 成功")
    return downloaded
