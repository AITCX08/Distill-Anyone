"""飞书妙记「文字记录」txt 解析。

飞书导出 txt 结构：
    <日期 时段 时间>|<时长>            # 第 1 行，例 "2026年6月2日 下午 5:51|14分钟 43秒"
    关键词:
    词1、词2、…                        # 可能跨多行，直到 "文字记录:"
    文字记录:
    说话人 N HH:MM                     # 段头（行尾可能带空格）
    <文本，可能跨多行>
    （空行）
    说话人 M HH:MM
    …
"""

import re

from src.meeting.models import TranscriptLine, MeetingTranscript

# 段头：说话人 + 编号 + 时间戳（MM:SS 或 HH:MM:SS），行尾允许空白
_SPEAKER_RE = re.compile(r"^说话人\s*(\d+)\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*$")
# 第 1 行的 日期|时长
_HEADER_RE = re.compile(r"^(.*?)\|(.*)$")
# 关键词分隔符：顿号 / 中英逗号 / 分号 / 空白
_KW_SPLIT_RE = re.compile(r"[、,，;；\s]+")


def parse_feishu_txt(text: str) -> MeetingTranscript:
    """把飞书妙记文字记录 txt 解析为 MeetingTranscript。"""
    transcript = MeetingTranscript()
    lines = text.splitlines()

    section = "head"       # head -> keywords -> body
    kw_buf: list[str] = []
    cur: TranscriptLine | None = None
    seen_speakers: set[str] = set()

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        # 段头标记
        if stripped in ("关键词:", "关键词："):
            section = "keywords"
            continue
        if stripped in ("文字记录:", "文字记录："):
            # 关键词收尾
            if kw_buf:
                transcript.keywords = _split_keywords(" ".join(kw_buf))
            section = "body"
            continue

        if section == "head":
            if not stripped:
                continue
            m = _HEADER_RE.match(stripped)
            if m:
                transcript.date_str = m.group(1).strip()
                transcript.duration_str = m.group(2).strip()
            continue

        if section == "keywords":
            if stripped:
                kw_buf.append(stripped)
            continue

        # section == "body"
        m = _SPEAKER_RE.match(stripped)
        if m:
            # 收尾上一段
            if cur is not None:
                transcript.lines.append(cur)
            speaker = f"说话人 {m.group(1)}"
            cur = TranscriptLine(speaker=speaker, timestamp=m.group(2), text="")
            if speaker not in seen_speakers:
                seen_speakers.add(speaker)
                transcript.speakers.append(speaker)
        elif cur is not None:
            if stripped:
                cur.text = (cur.text + stripped) if cur.text else stripped
        # 在 body 里、还没遇到任何说话人头的杂行：忽略

    if cur is not None:
        transcript.lines.append(cur)

    # 关键词可能没有 "文字记录:" 分隔（极端样本），兜底收尾
    if not transcript.keywords and kw_buf:
        transcript.keywords = _split_keywords(" ".join(kw_buf))

    return transcript


def _split_keywords(raw: str) -> list[str]:
    """按顿号/逗号/分号/空白切关键词，去空。"""
    return [w for w in _KW_SPLIT_RE.split(raw.strip()) if w]
