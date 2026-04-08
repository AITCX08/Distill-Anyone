"""
字幕获取模块

从B站获取视频的官方CC字幕（如果有的话）。
优先使用官方字幕可以跳过ASR步骤，提高效率和准确性。
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

from bilibili_api import video, Credential
from rich.console import Console

console = Console()


async def fetch_subtitle(
    bvid: str,
    credential: Credential,
) -> Optional[list[dict]]:
    """
    获取视频的官方CC字幕。

    Args:
        bvid: 视频BV号
        credential: B站认证凭据

    Returns:
        字幕片段列表 [{"start": float, "end": float, "text": str}]，
        无字幕则返回 None
    """
    try:
        v = video.Video(bvid=bvid, credential=credential)
        info = await v.get_info()

        # 获取字幕列表
        subtitle_list = info.get("subtitle", {}).get("list", [])
        if not subtitle_list:
            return None

        # 优先选择中文字幕
        target_subtitle = None
        for sub in subtitle_list:
            lang = sub.get("lan", "")
            if lang.startswith("zh") or lang.startswith("ai-zh"):
                target_subtitle = sub
                break

        # 没有中文字幕就取第一个
        if target_subtitle is None:
            target_subtitle = subtitle_list[0]

        # 下载字幕内容
        subtitle_url = target_subtitle.get("subtitle_url", "")
        if not subtitle_url:
            return None

        # 确保URL有协议头
        if subtitle_url.startswith("//"):
            subtitle_url = "https:" + subtitle_url

        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(subtitle_url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

        # 解析字幕数据
        segments = []
        for item in data.get("body", []):
            segments.append({
                "start": item.get("from", 0.0),
                "end": item.get("to", 0.0),
                "text": item.get("content", ""),
            })

        console.print(f"[green]获取到 {bvid} 的官方字幕，共 {len(segments)} 条")
        return segments

    except Exception as e:
        console.print(f"[yellow]获取 {bvid} 字幕失败: {e}")
        return None


def save_subtitle(bvid: str, segments: list[dict], output_dir: Path) -> Path:
    """
    保存字幕为RAG兼容的JSON格式。

    Args:
        bvid: 视频BV号
        segments: 字幕片段列表
        output_dir: 输出目录

    Returns:
        保存的文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{bvid}.json"

    # 转换为统一的转写格式
    full_text = "".join(seg["text"] for seg in segments)
    transcript_data = {
        "bvid": bvid,
        "source": "bilibili_cc_subtitle",
        "full_text": full_text,
        "segments": [
            {
                "id": f"{bvid}_seg_{i:04d}",
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
            }
            for i, seg in enumerate(segments)
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    return output_path


def run_fetch_subtitle(bvid: str, credential: Credential,
                       output_dir: Path) -> Optional[Path]:
    """同步入口：获取并保存字幕。"""
    segments = asyncio.run(fetch_subtitle(bvid, credential))
    if segments:
        return save_subtitle(bvid, segments, output_dir)
    return None
