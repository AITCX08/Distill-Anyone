"""
知识建模模块

使用 Claude API 从清洗后的文本中提取结构化知识，
并综合所有视频生成UP主的知识画像。
"""

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import anthropic
from rich.console import Console

console = Console()


@dataclass
class VideoKnowledge:
    """单个视频的知识提取结果"""
    bvid: str = ""
    title: str = ""
    summary: str = ""
    core_views: list[str] = field(default_factory=list)
    key_concepts: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    arguments: list[dict] = field(default_factory=list)


@dataclass
class BloggerProfile:
    """UP主知识画像"""
    name: str = ""
    uid: int = 0
    domain: list[str] = field(default_factory=list)
    core_views: list[str] = field(default_factory=list)
    style: str = ""
    signature_phrases: list[str] = field(default_factory=list)
    knowledge_boundary: dict = field(default_factory=lambda: {"strong": [], "weak": []})
    typical_qa_pairs: list[dict] = field(default_factory=list)
    video_sources: list[dict] = field(default_factory=list)


class KnowledgeExtractor:
    """
    知识提取器。

    使用 Claude API 从清洗后的视频文本中提取结构化知识，
    并综合多个视频生成UP主的完整知识画像。
    """

    def __init__(self, client: anthropic.Anthropic,
                 model: str = "claude-sonnet-4-20250514"):
        """
        初始化知识提取器。

        Args:
            client: Anthropic客户端
            model: 使用的模型名称
        """
        self.client = client
        self.model = model

    def extract_from_video(self, cleaned_doc: dict) -> VideoKnowledge:
        """
        从单个视频的清洗文本中提取知识。

        Args:
            cleaned_doc: 清洗后的文档数据

        Returns:
            VideoKnowledge 视频知识提取结果
        """
        bvid = cleaned_doc.get("bvid", "")
        title = cleaned_doc.get("title", "")
        full_text = cleaned_doc.get("full_text", "")

        console.print(f"[blue]提取知识: {bvid} - {title}")

        # 限制文本长度，防止超出上下文窗口
        text_input = full_text[:10000]

        prompt = VIDEO_KNOWLEDGE_PROMPT.format(
            title=title,
            text=text_input,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return VideoKnowledge(
                    bvid=bvid,
                    title=title,
                    summary=data.get("summary", ""),
                    core_views=data.get("core_views", []),
                    key_concepts=data.get("key_concepts", []),
                    topics=data.get("topics", []),
                    arguments=data.get("arguments", []),
                )
        except Exception as e:
            console.print(f"[red]知识提取失败 {bvid}: {e}")

        return VideoKnowledge(bvid=bvid, title=title)

    def merge_knowledge(self, all_knowledge: list[VideoKnowledge],
                        up_name: str = "", up_uid: int = 0) -> BloggerProfile:
        """
        综合所有视频知识，生成UP主的知识画像。

        Args:
            all_knowledge: 所有视频的知识提取结果
            up_name: UP主名称
            up_uid: UP主UID

        Returns:
            BloggerProfile 博主画像
        """
        console.print(f"[blue]综合 {len(all_knowledge)} 个视频，生成知识画像...")

        # 汇总所有视频的知识摘要
        summaries = []
        for k in all_knowledge:
            summaries.append(
                f"视频《{k.title}》:\n"
                f"  摘要: {k.summary}\n"
                f"  核心观点: {', '.join(k.core_views[:3])}\n"
                f"  关键概念: {', '.join(k.key_concepts[:5])}"
            )

        summary_text = "\n\n".join(summaries[:50])  # 限制数量

        prompt = PROFILE_SYNTHESIS_PROMPT.format(
            up_name=up_name or "未知",
            video_count=len(all_knowledge),
            summaries=summary_text,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return BloggerProfile(
                    name=data.get("name", up_name),
                    uid=up_uid,
                    domain=data.get("domain", []),
                    core_views=data.get("core_views", []),
                    style=data.get("style", ""),
                    signature_phrases=data.get("signature_phrases", []),
                    knowledge_boundary=data.get("knowledge_boundary",
                                                {"strong": [], "weak": []}),
                    typical_qa_pairs=data.get("typical_qa_pairs", []),
                    video_sources=[
                        {"bvid": k.bvid, "title": k.title}
                        for k in all_knowledge
                    ],
                )
        except Exception as e:
            console.print(f"[red]知识画像生成失败: {e}")

        # 降级：基于规则生成基础画像
        return self._fallback_profile(all_knowledge, up_name, up_uid)

    def _fallback_profile(self, all_knowledge: list[VideoKnowledge],
                          up_name: str, up_uid: int) -> BloggerProfile:
        """LLM调用失败时的降级画像生成。"""
        all_views = []
        all_concepts = []
        all_topics = []
        for k in all_knowledge:
            all_views.extend(k.core_views)
            all_concepts.extend(k.key_concepts)
            all_topics.extend(k.topics)

        # 统计词频取Top
        from collections import Counter
        top_topics = [t for t, _ in Counter(all_topics).most_common(5)]
        top_concepts = [c for c, _ in Counter(all_concepts).most_common(10)]

        return BloggerProfile(
            name=up_name,
            uid=up_uid,
            domain=top_topics,
            core_views=all_views[:10],
            style="（自动生成，建议人工补充）",
            signature_phrases=[],
            knowledge_boundary={"strong": top_concepts, "weak": []},
            typical_qa_pairs=[],
            video_sources=[
                {"bvid": k.bvid, "title": k.title}
                for k in all_knowledge
            ],
        )


def save_video_knowledge(knowledge: VideoKnowledge, output_dir: Path) -> Path:
    """保存单个视频的知识提取结果。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{knowledge.bvid}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(knowledge), f, ensure_ascii=False, indent=2)
    return output_path


def save_blogger_profile(profile: BloggerProfile, output_path: Path) -> Path:
    """保存博主画像。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(profile), f, ensure_ascii=False, indent=2)
    console.print(f"[green]博主画像已保存到 {output_path}")
    return output_path


def load_blogger_profile(input_path: Path) -> BloggerProfile:
    """从JSON文件加载博主画像。"""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return BloggerProfile(**data)


# ===== Prompt 模板 =====

VIDEO_KNOWLEDGE_PROMPT = """你是一个知识提取专家。请从以下视频转写文本中提取结构化知识。

视频标题：{title}

转写文本：
{text}

请提取以下信息并以JSON格式返回：
{{
  "summary": "视频内容的简要概括（100-200字）",
  "core_views": ["核心观点1", "核心观点2", ...],
  "key_concepts": ["关键概念/术语1", "关键概念2", ...],
  "topics": ["涉及的主题领域1", "主题2", ...],
  "arguments": [
    {{"claim": "论点", "evidence": "论据/例证"}},
    ...
  ]
}}

只返回JSON对象，不要有其他内容。"""

PROFILE_SYNTHESIS_PROMPT = """你是一个内容分析专家。请根据以下UP主的多个视频知识摘要，综合分析生成该UP主的完整知识画像。

UP主名称：{up_name}
视频总数：{video_count}

各视频知识摘要：
{summaries}

请综合分析并以JSON格式返回UP主的知识画像：
{{
  "name": "UP主名称",
  "domain": ["擅长领域1", "擅长领域2", ...],
  "core_views": ["该UP主反复强调的核心观点1", "观点2", ...],
  "style": "该UP主的表达风格描述（语气、修辞特点、互动方式等，100-200字）",
  "signature_phrases": ["标志性用语/口头禅1", "用语2", ...],
  "knowledge_boundary": {{
    "strong": ["深入了解的领域1", "领域2", ...],
    "weak": ["较少涉及的领域1", "领域2", ...]
  }},
  "typical_qa_pairs": [
    {{"question": "用户可能问的问题", "answer": "基于该UP主风格和知识的回答"}},
    ...
  ]
}}

只返回JSON对象，不要有其他内容。"""
