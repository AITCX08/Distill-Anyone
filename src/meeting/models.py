"""会议纪要数据结构。

设计原则（对齐项目惯例，见 src/model/CLAUDE.md）：
- 嵌套结构（outline / todos）用 list[dict] 而非深层 dataclass，便于宽容映射 LLM 输出
  与 jinja2/字符串渲染（参考 BloggerProfile.mental_models 的做法）。
- 解析得到的"客观事实"（标题/日期/参会人/关键词/逐字稿）放 dataclass 字段；
  LLM 产出的"主观提炼"（summary_intro/outline/todos）也放在 MeetingMinutes，由
  generator 合并两者。
"""

from dataclasses import dataclass, field


@dataclass
class TranscriptLine:
    """逐字稿的一段：说话人 + 时间戳 + 文本。"""
    speaker: str = ""        # "说话人 1"
    timestamp: str = ""      # "00:03" 或 "01:02:03"
    text: str = ""


@dataclass
class MeetingTranscript:
    """飞书妙记「文字记录」解析结果（阶段一的客观事实来源）。"""
    title: str = ""               # 会议主题（由命令层注入：--title 或文件名）
    date_str: str = ""            # "2026年6月2日 下午 5:51"
    duration_str: str = ""        # "14分钟 43秒"
    keywords: list = field(default_factory=list)   # ["策略", "创作者", ...]
    speakers: list = field(default_factory=list)   # ["说话人 1", "说话人 2", ...] 去重保序
    lines: list = field(default_factory=list)      # list[TranscriptLine]

    @property
    def full_text(self) -> str:
        """拼成「说话人 时间 文本」的全文，喂给 LLM。"""
        return "\n".join(
            f"{ln.speaker} {ln.timestamp} {ln.text}".strip()
            for ln in self.lines
        )


@dataclass
class MeetingMinutes:
    """飞书风格智能纪要（客观事实 + LLM 提炼合并后的渲染输入）。

    outline 结构（list[dict]，三层）：
        [{"title": 大主题, "children": [
            {"title": 子主题, "points": [
                {"title": 要点, "detail": 说明}
            ]}
        ]}]
    todos 结构（list[dict]）：[{"task": 任务, "assignee": "说话人 N" 或 ""}]
    """
    meeting_title: str = ""
    meeting_date: str = ""        # 进标题与元信息
    meeting_time: str = ""        # 元信息：日期（时长 …）
    participants: list = field(default_factory=list)   # ["说话人 1", ...]
    keywords: list = field(default_factory=list)
    summary_intro: str = ""       # "本次会议…内容如下："
    outline: list = field(default_factory=list)
    todos: list = field(default_factory=list)
