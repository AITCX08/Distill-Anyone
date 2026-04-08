"""
视频列表获取模块

使用 bilibili-api-python 获取指定UP主的所有视频列表，
包括BV号、标题、时长、发布时间等元信息。
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

from bilibili_api import user, Credential
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


async def fetch_user_videos(
    uid: int,
    credential: Credential,
    max_videos: int = 0,
) -> list[dict]:
    """
    获取指定UP主的所有视频列表。

    Args:
        uid: UP主的UID
        credential: B站认证凭据
        max_videos: 最大获取数量，0表示获取全部

    Returns:
        视频信息列表，每个元素包含 bvid, title, duration, pubdate 等字段
    """
    u = user.User(uid=uid, credential=credential)
    all_videos = []
    page = 1
    page_size = 30

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]正在获取视频列表..."),
        console=console,
    ) as progress:
        task = progress.add_task("获取中", total=None)

        while True:
            try:
                resp = await u.get_videos(pn=page, ps=page_size)
            except Exception as e:
                console.print(f"[red]获取第 {page} 页视频列表失败: {e}")
                break

            vlist = resp.get("list", {}).get("vlist", [])
            if not vlist:
                break

            for v in vlist:
                video_info = {
                    "bvid": v.get("bvid", ""),
                    "title": v.get("title", ""),
                    "duration": v.get("length", ""),
                    "pubdate": v.get("created", 0),
                    "description": v.get("description", ""),
                    "view_count": v.get("play", 0),
                    "comment_count": v.get("comment", 0),
                    "aid": v.get("aid", 0),
                }
                all_videos.append(video_info)

            total_count = resp.get("page", {}).get("count", 0)
            progress.update(
                task,
                description=f"[bold blue]已获取 {len(all_videos)}/{total_count} 个视频",
            )

            # 检查是否已获取足够数量
            if 0 < max_videos <= len(all_videos):
                all_videos = all_videos[:max_videos]
                break

            # 检查是否已获取所有视频
            if page * page_size >= total_count:
                break

            page += 1
            # 防止触发B站风控，间隔1秒
            await asyncio.sleep(1)

    console.print(f"[green]共获取 {len(all_videos)} 个视频信息")
    return all_videos


def save_video_list(videos: list[dict], output_path: Path) -> None:
    """将视频列表保存为JSON文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)
    console.print(f"[green]视频列表已保存到 {output_path}")


def load_video_list(input_path: Path) -> list[dict]:
    """从JSON文件加载视频列表。"""
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_credential(sessdata: str, bili_jct: str, buvid3: str) -> Credential:
    """从Cookie参数创建B站认证凭据。"""
    return Credential(sessdata=sessdata, bili_jct=bili_jct, buvid3=buvid3)


def run_crawl(uid: int, credential: Credential, output_path: Path,
              max_videos: int = 0) -> list[dict]:
    """
    同步入口：获取视频列表并保存。

    Args:
        uid: UP主UID
        credential: B站认证凭据
        output_path: 视频列表保存路径
        max_videos: 最大获取数量

    Returns:
        视频信息列表
    """
    videos = asyncio.run(fetch_user_videos(uid, credential, max_videos))
    save_video_list(videos, output_path)
    return videos
