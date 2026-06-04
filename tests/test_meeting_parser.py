from pathlib import Path

from src.meeting.models import TranscriptLine, MeetingTranscript, MeetingMinutes
from src.meeting.transcript_parser import parse_feishu_txt

FIXTURE = Path(__file__).parent / "fixtures" / "feishu_sample.txt"


def test_meeting_transcript_defaults_and_full_text():
    t = MeetingTranscript()
    assert t.title == ""
    assert t.keywords == []
    assert t.speakers == []
    assert t.lines == []
    assert t.full_text == ""

    t.lines = [
        TranscriptLine(speaker="说话人 1", timestamp="00:03", text="你好"),
        TranscriptLine(speaker="说话人 2", timestamp="00:42", text="在的"),
    ]
    assert t.full_text == "说话人 1 00:03 你好\n说话人 2 00:42 在的"


def test_meeting_minutes_defaults():
    m = MeetingMinutes()
    assert m.meeting_title == ""
    assert m.participants == []
    assert m.outline == []
    assert m.todos == []
    assert m.keywords == []
    assert m.summary_intro == ""


def test_parse_feishu_txt_header_and_keywords():
    text = FIXTURE.read_text(encoding="utf-8")
    t = parse_feishu_txt(text)
    assert t.date_str == "2026年6月2日 下午 5:51"
    assert t.duration_str == "14分钟 43秒"
    assert t.keywords == ["策略", "创作者", "上传", "内容池"]


def test_parse_feishu_txt_speakers_and_lines():
    text = FIXTURE.read_text(encoding="utf-8")
    t = parse_feishu_txt(text)
    # 4 段发言，3 位去重说话人（说话人 1 出现两次）
    assert len(t.lines) == 4
    assert t.speakers == ["说话人 1", "说话人 2", "说话人 3"]
    first = t.lines[0]
    assert first.speaker == "说话人 1"
    assert first.timestamp == "00:03"
    assert first.text == "首先我们要明确全托管的目标，就是降低达人的使用门槛。"
    # 第二段说话人 2
    assert t.lines[1].speaker == "说话人 2"
    assert t.lines[1].text == "这个策略组是干什么用的？"


def test_parse_feishu_txt_multiline_text_merged():
    # 一段发言文本跨多行时应被合并为一行
    sample = (
        "2026年1月1日 上午 9:00|1分钟 0秒\n\n"
        "关键词:\nA、B\n\n文字记录:\n"
        "说话人 1 00:01 \n第一行。\n第二行。\n\n"
        "说话人 2 00:05 \n回应。\n"
    )
    t = parse_feishu_txt(sample)
    assert len(t.lines) == 2
    assert t.lines[0].text == "第一行。第二行。"
    assert t.lines[1].text == "回应。"


def test_parse_feishu_txt_supports_hms_timestamp():
    sample = "文字记录:\n说话人 1 01:02:03 \n超过一小时的会议。\n"
    t = parse_feishu_txt(sample)
    assert t.lines[0].timestamp == "01:02:03"
