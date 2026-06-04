"""智能纪要生成：把 MeetingTranscript 交给 LLM，产出飞书风格「总结+待办」。

复用项目既有的 LLM JSON 容错工具（src/model/knowledge_extractor）：
- _extract_json_payload：剥 <think> 标签 / 代码块，括号计数找平衡块
- _safe_json_loads：7 轮修复
- _dump_llm_failure：失败落盘 data/llm_debug/
LLM 客户端由调用方通过 src/clean/text_processor.create_llm_client 注入。
"""

from rich.console import Console

from src.meeting.models import MeetingMinutes, MeetingTranscript

console = Console()

# 喂给 LLM 的正文截断上限（防 context 溢出，对齐项目惯例）
MAX_INPUT_CHARS = 12000


class MeetingMinutesGenerator:
    """LLM 智能纪要生成器。"""

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate(self, transcript: MeetingTranscript) -> MeetingMinutes:
        # 重依赖容错工具：函数内导入（根级硬规则 #4）
        from src.model.knowledge_extractor import (
            _safe_json_loads, _extract_json_payload, _dump_llm_failure,
        )

        minutes = MeetingMinutes(
            meeting_title=transcript.title,
            meeting_date=transcript.date_str,
            meeting_time=(
                f"{transcript.date_str}（时长 {transcript.duration_str}）"
                if transcript.duration_str else transcript.date_str
            ),
            participants=list(transcript.speakers),
            keywords=list(transcript.keywords),
        )

        prompt = MEETING_MINUTES_PROMPT.format(
            full_text=transcript.full_text[:MAX_INPUT_CHARS],
        )

        content = ""
        data: dict = {}
        try:
            content = self.llm_client.chat(prompt, max_tokens=8192)
            payload = _extract_json_payload(content, prefer_array=False) or content
            parsed = _safe_json_loads(payload)
            if isinstance(parsed, dict):
                data = parsed
            else:
                _dump_llm_failure("meeting_minutes", content, prompt, "not_object")
                console.print(f"[yellow]智能纪要返回非对象（{type(parsed).__name__}），走降级")
        except Exception as e:
            _dump_llm_failure("meeting_minutes", content, prompt, "parse_fail")
            console.print(f"[yellow]智能纪要 LLM 解析失败，走降级: {e}")

        minutes.summary_intro = (data.get("summary_intro") or "").strip()
        minutes.outline = data.get("outline") or []
        minutes.todos = data.get("todos") or []

        # 降级兜底：LLM 没给可用大纲时，至少有一句开场，渲染不空白
        if not minutes.outline and not minutes.summary_intro:
            minutes.summary_intro = "本次会议内容记录如下（智能纪要生成失败，仅保留文字记录）："

        return minutes


# ===== Prompt（硬规则：放文件底部）=====

MEETING_MINUTES_PROMPT = """你是一名专业的会议纪要整理助手。下面是一段会议的逐字记录（格式为「说话人 时间 内容」）。请阅读全文，提炼成结构化的「智能纪要」。

要求：
1. 用一句话概括整场会议（谁、围绕什么、得出什么），作为 summary_intro，以"内容如下："结尾。
2. 把会议内容组织成**三层**层级大纲 outline：
   - 第 1 层 title = 大主题（会议讨论的几个主要板块）
   - 第 2 层 children[].title = 子主题
   - 第 3 层 points[] = 具体要点，每个 point 有 title（要点短句）和 detail（一两句展开说明）
3. 提取明确的行动项/待办 todos，每个含 task（要做什么）和 assignee（负责人，用逐字稿里的"说话人 N"，无法判断就留空字符串）。没有明确待办则返回空数组。
4. 忠实于原文，不要编造内容；用简体中文。

严格只输出如下 JSON（不要输出任何解释文字、不要 markdown 代码块以外的内容）：

{{
  "summary_intro": "本次会议……内容如下：",
  "outline": [
    {{
      "title": "大主题",
      "children": [
        {{
          "title": "子主题",
          "points": [
            {{"title": "要点短句", "detail": "一两句具体说明"}}
          ]
        }}
      ]
    }}
  ],
  "todos": [
    {{"task": "任务描述", "assignee": "说话人 N 或 空字符串"}}
  ]
}}

会议逐字记录：
{full_text}
"""
