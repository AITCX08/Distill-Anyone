"""
文本清洗模块

对ASR转写结果进行清洗处理：
- 去除语气词和填充词
- 合并过短片段
- 使用Claude API进行主题切分
- 输出RAG兼容的结构化JSON
"""

import json
import re
from pathlib import Path
from typing import Optional

import anthropic
from rich.console import Console

console = Console()

# 中文常见语气词和填充词
FILLER_WORDS_PATTERN = re.compile(
    r"(?:^|(?<=[\u3000-\u9fff\uff00-\uffef]))"
    r"(?:嗯+|啊+|呃+|额+|哦+|噢+|唔+|"
    r"那个|这个|就是说|就是|然后呢|然后|"
    r"对吧|是吧|对不对|你知道吗|你看|"
    r"怎么说呢|说白了就是)"
    r"(?:(?=[\u3000-\u9fff\uff00-\uffef])|$)"
)

# 重复标点清理
REPEATED_PUNCT_PATTERN = re.compile(r"([，。！？、])\1+")


class TextProcessor:
    """文本清洗与结构化处理器。"""

    def __init__(self, anthropic_client: Optional[anthropic.Anthropic] = None,
                 model: str = "claude-sonnet-4-20250514"):
        """
        初始化文本处理器。

        Args:
            anthropic_client: Anthropic客户端（用于LLM辅助清洗）
            model: 使用的Claude模型名称
        """
        self.client = anthropic_client
        self.model = model

    def remove_filler_words(self, text: str) -> str:
        """
        去除中文语气词和填充词。

        Args:
            text: 原始文本

        Returns:
            清洗后的文本
        """
        cleaned = FILLER_WORDS_PATTERN.sub("", text)
        # 清理多余空格和重复标点
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = REPEATED_PUNCT_PATTERN.sub(r"\1", cleaned)
        return cleaned

    def merge_short_segments(self, segments: list[dict],
                             min_length: int = 10) -> list[dict]:
        """
        合并过短的文本片段。

        Args:
            segments: 转写片段列表
            min_length: 最小文本长度

        Returns:
            合并后的片段列表
        """
        if not segments:
            return []

        merged = []
        current = dict(segments[0])

        for seg in segments[1:]:
            if len(current.get("text", "")) < min_length:
                # 当前片段太短，与下一个合并
                current["text"] = current.get("text", "") + seg.get("text", "")
                current["end"] = seg.get("end", current.get("end", 0))
            else:
                merged.append(current)
                current = dict(seg)

        merged.append(current)
        return merged

    def segment_by_topic(self, full_text: str, video_title: str) -> list[dict]:
        """
        使用Claude API进行主题切分。

        Args:
            full_text: 完整清洗后的文本
            video_title: 视频标题（提供上下文）

        Returns:
            主题分段列表 [{"title": str, "content": str, "tags": [str]}]
        """
        if not self.client:
            # 无LLM客户端时，按段落简单分段
            paragraphs = [p.strip() for p in full_text.split("\n") if p.strip()]
            return [{"title": f"段落{i+1}", "content": p, "tags": []}
                    for i, p in enumerate(paragraphs)]

        prompt = TOPIC_SEGMENT_PROMPT.format(
            video_title=video_title,
            text=full_text[:8000],  # 限制输入长度
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            # 解析JSON响应
            content = response.content[0].text
            # 尝试提取JSON部分
            json_match = re.search(r"\[.*\]", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            console.print(f"[yellow]主题切分失败，使用简单分段: {e}")

        # 降级为简单分段
        return [{"title": "全文", "content": full_text, "tags": []}]

    def process_transcript(self, transcript_data: dict) -> dict:
        """
        处理单个视频的转写结果，完成完整清洗流程。

        Args:
            transcript_data: 转写结果JSON数据

        Returns:
            清洗后的结构化文档
        """
        bvid = transcript_data.get("bvid", "")
        title = transcript_data.get("title", "")
        segments = transcript_data.get("segments", [])

        console.print(f"[blue]清洗文本: {bvid} - {title}")

        # 步骤1：去除填充词
        for seg in segments:
            seg["text"] = self.remove_filler_words(seg.get("text", ""))

        # 步骤2：合并短片段
        segments = self.merge_short_segments(segments)

        # 步骤3：生成清洗后的完整文本
        full_text = "".join(seg.get("text", "") for seg in segments)
        full_text = self.remove_filler_words(full_text)

        # 步骤4：主题切分
        topics = self.segment_by_topic(full_text, title)

        # 构建清洗后的文档
        cleaned_doc = {
            "bvid": bvid,
            "title": title,
            "source": transcript_data.get("source", ""),
            "full_text": full_text,
            "topics": [
                {
                    "id": f"{bvid}_topic_{i:03d}",
                    "title": t.get("title", ""),
                    "content": t.get("content", ""),
                    "tags": t.get("tags", []),
                }
                for i, t in enumerate(topics)
            ],
            "segments": segments,
            "metadata": transcript_data.get("metadata", {}),
        }

        console.print(f"[green]清洗完成: {bvid}，共 {len(topics)} 个主题段")
        return cleaned_doc


def save_cleaned(cleaned_doc: dict, output_dir: Path) -> Path:
    """保存清洗结果为JSON文件。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{cleaned_doc['bvid']}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_doc, f, ensure_ascii=False, indent=2)

    return output_path


def load_cleaned(input_path: Path) -> dict:
    """从JSON文件加载清洗结果。"""
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ===== Prompt 模板 =====

TOPIC_SEGMENT_PROMPT = """你是一个文本分析专家。请将以下视频转写文本按主题进行分段。

视频标题：{video_title}

转写文本：
{text}

请将文本分成若干个主题段落，每个主题段落包含：
- title: 主题名称（简短概括）
- content: 该主题的具体内容
- tags: 相关标签（2-5个关键词）

请以JSON数组格式返回，示例：
[
  {{"title": "主题名称", "content": "主题内容...", "tags": ["标签1", "标签2"]}}
]

只返回JSON数组，不要有其他内容。"""
