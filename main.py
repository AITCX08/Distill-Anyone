"""
Distill-Anyone: B站UP主知识蒸馏工具

将B站知识区UP主的视频内容，通过语音识别和LLM分析，
转化为结构化的SKILL.md知识文件。

用法:
    python main.py crawl    # 阶段1: 爬取视频列表并下载音频
    python main.py asr      # 阶段2: FunASR语音转文字
    python main.py clean    # 阶段3: 文本清洗与结构化
    python main.py model    # 阶段4: 知识建模
    python main.py generate # 阶段5: 生成SKILL.md
    python main.py run      # 一键运行（可通过 --stages 选择阶段）
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from src.config import LLM_PROVIDERS

console = Console()

# CLI 中 --llm 可选值
LLM_CHOICES = click.Choice(LLM_PROVIDERS)


def parse_stages(stages_str: str) -> list[int]:
    """
    解析阶段选择字符串。

    支持格式:
      - "1,2,3"    → [1, 2, 3]
      - "3-5"      → [3, 4, 5]
      - "1,3-5"    → [1, 3, 4, 5]
      - "all"      → [1, 2, 3, 4, 5]

    Returns:
        排序后的阶段编号列表
    """
    if stages_str.strip().lower() == "all":
        return [1, 2, 3, 4, 5]

    result = set()
    for part in stages_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            for i in range(int(start), int(end) + 1):
                if 1 <= i <= 5:
                    result.add(i)
        else:
            val = int(part)
            if 1 <= val <= 5:
                result.add(val)
    return sorted(result)


@click.group()
@click.version_option(version="0.2.0", prog_name="Distill-Anyone")
def cli():
    """Distill-Anyone: B站UP主知识蒸馏工具

    将B站知识区UP主的视频内容转化为结构化的SKILL.md知识文件。
    """
    pass


@cli.command()
@click.option("--uid", type=int, default=None, help="UP主UID（覆盖.env中的配置）")
@click.option("--max-videos", type=int, default=0, help="最大获取视频数量，0为全部")
def crawl(uid, max_videos):
    """阶段1: 爬取视频列表并下载音频"""
    from src.config import load_config
    from src.crawl.video_list import run_crawl, create_credential
    from src.crawl.audio_download import (
        batch_download,
        generate_cookies_file,
    )

    config = load_config()
    target_uid = uid or config.up_uid

    if not target_uid:
        console.print("[red]错误: 请指定UP主UID（--uid 参数或 .env 中配置 UP_UID）")
        sys.exit(1)

    console.print(Panel(f"[bold]阶段1: 数据采集[/bold]\nUP主UID: {target_uid}",
                        title="Distill-Anyone"))

    # 创建B站认证凭据
    credential = create_credential(
        sessdata=config.bilibili.sessdata,
        bili_jct=config.bilibili.bili_jct,
        buvid3=config.bilibili.buvid3,
    )

    # 获取视频列表
    video_list_path = config.data_dir / "video_list.json"
    videos = run_crawl(target_uid, credential, video_list_path, max_videos)

    if not videos:
        console.print("[yellow]未获取到任何视频")
        return

    # 生成cookies文件并下载音频
    cookies_file = generate_cookies_file(
        sessdata=config.bilibili.sessdata,
        bili_jct=config.bilibili.bili_jct,
        buvid3=config.bilibili.buvid3,
    )
    batch_download(videos, config.audio_dir, cookies_file=cookies_file)

    console.print("[bold green]阶段1完成!")


@cli.command()
def asr():
    """阶段2: FunASR语音转文字"""
    from src.config import load_config
    from src.asr.funasr_engine import FunASREngine, save_transcript
    from src.crawl.video_list import load_video_list

    config = load_config()

    console.print(Panel("[bold]阶段2: 语音识别[/bold]", title="Distill-Anyone"))

    # 加载视频列表（用于元信息）
    video_list_path = config.data_dir / "video_list.json"
    if not video_list_path.exists():
        console.print("[red]错误: 请先运行 crawl 阶段获取视频列表")
        sys.exit(1)

    videos = load_video_list(video_list_path)
    video_meta_map = {v["bvid"]: v for v in videos}

    # 查找所有已下载的音频文件
    audio_files = list(config.audio_dir.glob("BV*.*"))
    if not audio_files:
        console.print("[red]错误: 未找到音频文件，请先运行 crawl 阶段")
        sys.exit(1)

    # 过滤已转写的文件
    pending_files = []
    pending_bvids = []
    for audio_file in audio_files:
        bvid = audio_file.stem
        transcript_path = config.transcripts_dir / f"{bvid}.json"
        if not transcript_path.exists():
            pending_files.append(audio_file)
            pending_bvids.append(bvid)

    if not pending_files:
        console.print("[yellow]所有音频文件已转写完毕")
        return

    console.print(f"[blue]待转写: {len(pending_files)} 个音频文件")

    # 初始化ASR引擎
    engine = FunASREngine(
        model_name=config.funasr.model,
        vad_model=config.funasr.vad_model,
        punc_model=config.funasr.punc_model,
    )

    # 批量转写
    results = engine.transcribe_batch(pending_files, pending_bvids)

    # 保存转写结果
    for result in results:
        meta = video_meta_map.get(result.bvid, {})
        save_transcript(result, meta, config.transcripts_dir)

    console.print("[bold green]阶段2完成!")


@cli.command()
@click.option("--llm", "llm_provider", type=LLM_CHOICES,
              default=None, help="LLM提供商（覆盖.env中的 LLM_PROVIDER 配置）")
def clean(llm_provider):
    """阶段3: 文本清洗与结构化"""
    from src.config import load_config
    from src.clean.text_processor import (
        TextProcessor, save_cleaned, create_llm_client,
    )
    from src.asr.funasr_engine import load_transcript

    config = load_config()
    provider = llm_provider or config.llm_provider

    console.print(Panel(
        f"[bold]阶段3: 文本清洗[/bold]\nLLM: {provider}",
        title="Distill-Anyone",
    ))

    # 查找所有转写结果
    transcript_files = list(config.transcripts_dir.glob("*.json"))
    if not transcript_files:
        console.print("[red]错误: 未找到转写结果，请先运行 asr 阶段")
        sys.exit(1)

    # 过滤已清洗的文件
    pending_files = [
        f for f in transcript_files
        if not (config.cleaned_dir / f.name).exists()
    ]

    if not pending_files:
        console.print("[yellow]所有文本已清洗完毕")
        return

    console.print(f"[blue]待清洗: {len(pending_files)} 个文件")

    # 根据配置创建 LLM 客户端
    llm_client = create_llm_client(provider, config)
    processor = TextProcessor(llm_client=llm_client)

    # 批量清洗
    for f in pending_files:
        transcript_data = load_transcript(f)
        cleaned_doc = processor.process_transcript(transcript_data)
        save_cleaned(cleaned_doc, config.cleaned_dir)

    console.print("[bold green]阶段3完成!")


@cli.command("model")
@click.option("--llm", "llm_provider", type=LLM_CHOICES,
              default=None, help="LLM提供商（覆盖.env中的 LLM_PROVIDER 配置）")
def model_cmd(llm_provider):
    """阶段4: 知识建模"""
    from src.config import load_config
    from src.clean.text_processor import load_cleaned, create_llm_client
    from src.model.knowledge_extractor import (
        KnowledgeExtractor,
        save_video_knowledge,
        save_blogger_profile,
    )

    config = load_config()
    provider = llm_provider or config.llm_provider

    console.print(Panel(
        f"[bold]阶段4: 知识建模[/bold]\nLLM: {provider}",
        title="Distill-Anyone",
    ))

    # 查找所有清洗结果
    cleaned_files = list(config.cleaned_dir.glob("*.json"))
    if not cleaned_files:
        console.print("[red]错误: 未找到清洗结果，请先运行 clean 阶段")
        sys.exit(1)

    # 创建 LLM 客户端
    llm_client = create_llm_client(provider, config)
    if not llm_client:
        console.print("[red]错误: 知识建模需要可用的 LLM，请配置对应的 API Key")
        sys.exit(1)

    extractor = KnowledgeExtractor(llm_client=llm_client)

    # 逐个视频提取知识
    all_knowledge = []
    for f in cleaned_files:
        cleaned_doc = load_cleaned(f)
        knowledge = extractor.extract_from_video(cleaned_doc)
        save_video_knowledge(knowledge, config.knowledge_dir)
        all_knowledge.append(knowledge)

    # 综合生成博主画像
    profile = extractor.merge_knowledge(all_knowledge, up_uid=config.up_uid)
    profile_path = config.knowledge_dir / "blogger_profile.json"
    save_blogger_profile(profile, profile_path)

    console.print("[bold green]阶段4完成!")


@cli.command()
def generate():
    """阶段5: 生成SKILL.md"""
    from src.config import load_config
    from src.model.knowledge_extractor import load_blogger_profile
    from src.generate.skill_generator import SkillGenerator

    config = load_config()

    console.print(Panel("[bold]阶段5: 生成SKILL.md[/bold]", title="Distill-Anyone"))

    # 加载博主画像
    profile_path = config.knowledge_dir / "blogger_profile.json"
    if not profile_path.exists():
        console.print("[red]错误: 未找到博主画像，请先运行 model 阶段")
        sys.exit(1)

    profile = load_blogger_profile(profile_path)

    # 生成SKILL.md
    generator = SkillGenerator(template_dir="templates")
    output_path = config.output_dir / f"{profile.name or 'skill'}.skill.md"
    generator.generate_and_save(profile, output_path)

    console.print("[bold green]阶段5完成!")
    console.print(f"[green]输出文件: {output_path}")


@cli.command()
@click.option("--uid", type=int, default=None, help="UP主UID")
@click.option("--max-videos", type=int, default=0, help="最大获取视频数量")
@click.option("--llm", "llm_provider", type=LLM_CHOICES,
              default=None, help="LLM提供商（覆盖.env中的 LLM_PROVIDER 配置）")
@click.option("--stages", "stages_str", type=str, default="all",
              help="要执行的阶段，如: all, 1,2,3, 3-5, 1,3-5（默认 all）")
def run(uid, max_videos, llm_provider, stages_str):
    """一键运行流水线（可通过 --stages 选择阶段）"""
    from src.config import load_config

    config = load_config()
    target_uid = uid or config.up_uid
    provider = llm_provider or config.llm_provider

    try:
        stages = parse_stages(stages_str)
    except ValueError:
        console.print(f"[red]错误: 无效的阶段格式 '{stages_str}'，示例: all, 1,2,3, 3-5")
        sys.exit(1)

    if not stages:
        console.print("[red]错误: 未选择任何阶段")
        sys.exit(1)

    # 阶段1需要UID
    if 1 in stages and not target_uid:
        console.print("[red]错误: 请指定UP主UID")
        sys.exit(1)

    stage_names = {1: "数据采集", 2: "语音识别", 3: "文本清洗", 4: "知识建模", 5: "生成SKILL.md"}
    selected = ", ".join(f"{s}-{stage_names[s]}" for s in stages)

    console.print(Panel(
        f"[bold]Distill-Anyone 流水线[/bold]\n"
        f"UP主UID: {target_uid or '(无需)'}\n"
        f"最大视频数: {'不限' if max_videos == 0 else max_videos}\n"
        f"LLM: {provider}\n"
        f"执行阶段: {selected}",
        title="Distill-Anyone",
    ))

    ctx = click.Context(cli)
    total = len(stages)

    if 1 in stages:
        console.print(f"\n[bold]═══ [{stages.index(1)+1}/{total}] 阶段1: 数据采集 ═══[/bold]")
        ctx.invoke(crawl, uid=target_uid, max_videos=max_videos)

    if 2 in stages:
        console.print(f"\n[bold]═══ [{stages.index(2)+1}/{total}] 阶段2: 语音识别 ═══[/bold]")
        ctx.invoke(asr)

    if 3 in stages:
        console.print(f"\n[bold]═══ [{stages.index(3)+1}/{total}] 阶段3: 文本清洗 ═══[/bold]")
        ctx.invoke(clean, llm_provider=provider)

    if 4 in stages:
        console.print(f"\n[bold]═══ [{stages.index(4)+1}/{total}] 阶段4: 知识建模 ═══[/bold]")
        ctx.invoke(model_cmd, llm_provider=provider)

    if 5 in stages:
        console.print(f"\n[bold]═══ [{stages.index(5)+1}/{total}] 阶段5: 生成SKILL.md ═══[/bold]")
        ctx.invoke(generate)

    console.print(f"\n[bold green]流水线完成! 已执行阶段: {selected}")


if __name__ == "__main__":
    cli()
