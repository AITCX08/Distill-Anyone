"""
知识建模模块

使用 LLM（Claude / OpenAI / Qwen / DeepSeek）从清洗后的文本中提取
结构化知识，并综合所有视频生成UP主的知识画像。
"""

import json
import re
from dataclasses import dataclass, field, asdict


def _safe_json_loads(json_str: str) -> dict:
    """解析 JSON，自动修复 LLM 输出中常见的格式问题，多轮尝试。"""
    # 第1轮：直接解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    cleaned = json_str

    # 第2轮：修复控制字符 + 字符串内裸换行
    cleaned = re.sub(r'(?<!\\)[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', cleaned)
    cleaned = re.sub(r'("(?:[^"\\]|\\.)*")', _escape_inner_newlines, cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 第3轮：移除尾随逗号（,} 或 ,]）
    cleaned = re.sub(r',\s*([\}\]])', r'\1', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 第4轮：将 ... 占位符替换为空字符串或空数组
    cleaned = re.sub(r':\s*\.\.\.', ': ""', cleaned)        # value 位置的 ...
    cleaned = re.sub(r',\s*\.\.\.', '', cleaned)             # 数组末尾的 , ...
    cleaned = re.sub(r'\[\s*\.\.\.\s*\]', '[]', cleaned)    # [...] 整体
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 第5轮：截断到最后一个合法的 } 处（处理截断输出）
    last_brace = cleaned.rfind('}')
    if last_brace != -1:
        try:
            return json.loads(cleaned[:last_brace + 1])
        except json.JSONDecodeError:
            pass

    # 全部失败则抛出原始错误
    return json.loads(json_str)


def _escape_inner_newlines(m: re.Match) -> str:
    """将 JSON 字符串值内的裸换行替换为 \\n。"""
    return m.group(0).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from src.clean.text_processor import LLMClient

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
    # nuwa 新增：思维框架线索、判断准则示例、表达样本
    mental_model_hints: list[dict] = field(default_factory=list)
    decision_examples: list[dict] = field(default_factory=list)
    expression_samples: list[str] = field(default_factory=list)


@dataclass
class BloggerProfile:
    """UP主知识画像（nuwa-skill 增强版）"""
    name: str = ""
    uid: int = 0
    domain: list[str] = field(default_factory=list)
    # 原有字段
    core_views: list[str] = field(default_factory=list)
    style: str = ""
    signature_phrases: list[str] = field(default_factory=list)
    knowledge_boundary: dict = field(default_factory=lambda: {"strong": [], "weak": []})
    typical_qa_pairs: list[dict] = field(default_factory=list)
    video_sources: list[dict] = field(default_factory=list)
    # nuwa-skill 新增字段
    self_intro: str = ""                          # 用本人口吻的自我介绍（50字）
    mental_models: list[dict] = field(default_factory=list)   # 思维框架
    decision_heuristics: list[dict] = field(default_factory=list)  # 判断准则
    expression_dna: dict = field(default_factory=dict)         # 表达DNA
    values: list[str] = field(default_factory=list)            # 价值观
    anti_patterns: list[str] = field(default_factory=list)     # 反模式（明确拒绝的）
    honest_boundaries: list[str] = field(default_factory=list) # 诚实边界/局限性


class KnowledgeExtractor:
    """
    知识提取器。

    使用统一的 LLMClient 接口从清洗后的视频文本中提取结构化知识，
    并综合多个视频生成UP主的完整知识画像。
    支持 Claude / OpenAI / Qwen / DeepSeek 等后端。
    """

    def __init__(self, llm_client: "LLMClient"):
        """
        初始化知识提取器。

        Args:
            llm_client: 统一的 LLM 客户端（由 create_llm_client 创建）
        """
        self.llm_client = llm_client

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
            content = self.llm_client.chat(prompt, max_tokens=4096)
            # 优先提取 ```json 代码块，降级为贪婪匹配
            json_str = None
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            else:
                m = re.search(r"\{.*\}", content, re.DOTALL)
                if m:
                    json_str = m.group()
            if json_str:
                data = _safe_json_loads(json_str)
                return VideoKnowledge(
                    bvid=bvid,
                    title=title,
                    summary=data.get("summary", ""),
                    core_views=data.get("core_views", []),
                    key_concepts=data.get("key_concepts", []),
                    topics=data.get("topics", []),
                    arguments=data.get("arguments", []),
                    mental_model_hints=data.get("mental_model_hints", []),
                    decision_examples=data.get("decision_examples", []),
                    expression_samples=data.get("expression_samples", []),
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

        # 汇总所有视频的知识摘要，包含 nuwa 新增字段
        summaries = []
        for k in all_knowledge:
            mental_hint = ""
            if k.mental_model_hints:
                mental_hint = f"\n  思维框架线索: {k.mental_model_hints[0].get('hint', '')}"
            decision_ex = ""
            if k.decision_examples:
                decision_ex = f"\n  决策示例: {k.decision_examples[0].get('scenario', '')}"
            expr_sample = ""
            if k.expression_samples:
                expr_sample = f"\n  表达样本: {k.expression_samples[0][:80]}"
            summaries.append(
                f"视频《{k.title}》:\n"
                f"  摘要: {k.summary}\n"
                f"  核心观点: {', '.join(k.core_views[:3])}\n"
                f"  关键概念: {', '.join(k.key_concepts[:5])}"
                f"{mental_hint}{decision_ex}{expr_sample}"
            )

        summary_text = "\n\n".join(summaries[:50])  # 限制数量

        prompt = PROFILE_SYNTHESIS_PROMPT.format(
            up_name=up_name or "未知",
            video_count=len(all_knowledge),
            summaries=summary_text,
        )

        try:
            content = self.llm_client.chat(prompt, max_tokens=8192)
            json_str = None
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            else:
                m = re.search(r"\{.*\}", content, re.DOTALL)
                if m:
                    json_str = m.group()
            if json_str:
                data = _safe_json_loads(json_str)
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
                    self_intro=data.get("self_intro", ""),
                    mental_models=data.get("mental_models", []),
                    decision_heuristics=data.get("decision_heuristics", []),
                    expression_dna=data.get("expression_dna", {}),
                    values=data.get("values", []),
                    anti_patterns=data.get("anti_patterns", []),
                    honest_boundaries=data.get("honest_boundaries", []),
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


def check_knowledge_integrity(knowledge_path: Path) -> tuple[bool, str]:
    """
    检查单视频知识文件的完整性。

    Returns:
        (is_valid, reason)
    """
    if not knowledge_path.exists():
        return False, "文件不存在"
    if knowledge_path.stat().st_size == 0:
        return False, "文件为空"
    try:
        with open(knowledge_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return False, f"JSON 解析失败: {e}"
    if not data.get("summary", "").strip():
        return False, "summary 为空"
    if not data.get("core_views"):
        return False, "core_views 为空"
    return True, "ok"


def load_video_knowledge(input_path: Path) -> VideoKnowledge:
    """从JSON文件加载单个视频的知识提取结果。"""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    valid_keys = {f.name for f in VideoKnowledge.__dataclass_fields__.values()}
    return VideoKnowledge(**{k: v for k, v in data.items() if k in valid_keys})


def load_blogger_profile(input_path: Path) -> BloggerProfile:
    """从JSON文件加载博主画像。"""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    valid_keys = {f.name for f in BloggerProfile.__dataclass_fields__.values()}
    return BloggerProfile(**{k: v for k, v in data.items() if k in valid_keys})


# ===== Prompt 模板 =====

VIDEO_KNOWLEDGE_PROMPT = """你是一个深度知识提取专家。请从以下视频转写文本中提取结构化知识，\
重点捕捉博主独特的思维方式、决策逻辑和表达风格。

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
  ],
  "mental_model_hints": [
    {{"hint": "博主用来分析问题的框架或方法论线索（如：先看本质再看表象）", "context": "使用场景简述"}}
  ],
  "decision_examples": [
    {{"scenario": "面对什么情境", "reasoning": "博主的推理过程", "conclusion": "得出的结论或行动"}}
  ],
  "expression_samples": [
    "博主的原话片段，能体现其独特表达方式（1-2句）"
  ]
}}

只返回JSON对象，不要有其他内容。"""

PROFILE_SYNTHESIS_PROMPT = """你是一个深度人物画像专家。请根据以下UP主的多个视频知识摘要，\
综合分析生成该UP主的完整知识画像，目标是让AI助手能够真实模拟该UP主的思考和表达方式。

UP主名称：{up_name}
视频总数：{video_count}

各视频知识摘要：
{summaries}

请综合分析并以JSON格式返回UP主的完整知识画像：
{{
  "name": "UP主名称",
  "domain": ["擅长领域1", "擅长领域2", ...],
  "self_intro": "用本人第一人称口吻写的自我介绍（50字左右，体现其核心身份认同和价值主张）",
  "core_views": ["该UP主反复强调的核心观点1（完整表述）", "观点2", ...],
  "style": "该UP主的整体表达风格（语气特点、思维习惯、互动方式、常用比喻等，150-200字）",
  "signature_phrases": ["标志性口头禅或常用句式1", "用语2", ...],
  "mental_models": [
    {{
      "name": "框架名称（如：第一性原理、能力圈思维）",
      "description": "该博主如何实际运用这个框架",
      "trigger": "在什么类型的问题中会触发使用"
    }}
  ],
  "decision_heuristics": [
    {{
      "rule": "判断准则（如：宁可少赚也不违背原则）",
      "source": "来源于哪类视频或场景",
      "application": "在回答什么类型问题时应用"
    }}
  ],
  "expression_dna": {{
    "opening_patterns": ["常见开场方式1", "开场方式2"],
    "reasoning_connectors": ["连接逻辑的惯用词1", "惯用词2"],
    "emphasis_patterns": ["强调时的表达方式1", "方式2"],
    "closing_patterns": ["收尾时的惯用表达1", "表达2"]
  }},
  "values": ["核心价值观1（具体的，非泛泛的）", "价值观2", ...],
  "anti_patterns": ["明确拒绝或反对的做法/观点1", "反对的观点2", ...],
  "honest_boundaries": ["知识局限声明1（如：我不是XXX专业，只是…）", "局限2", ...],
  "knowledge_boundary": {{
    "strong": ["深入了解的领域1", "领域2", ...],
    "weak": ["较少涉及或主动回避的领域1", "领域2", ...]
  }},
  "typical_qa_pairs": [
    {{
      "question": "用户可能问的具体问题",
      "answer": "完全按照该UP主风格、用其惯用表达方式给出的回答（100字以上）"
    }}
  ]
}}

只返回JSON对象，不要有其他内容。"""
