from src.meeting.models import TranscriptLine, MeetingTranscript
from src.meeting.minutes_generator import MeetingMinutesGenerator


def _transcript():
    t = MeetingTranscript(
        title="全托管",
        date_str="2026年6月2日 下午 5:51",
        duration_str="14分钟 43秒",
        keywords=["策略", "创作者"],
        speakers=["说话人 1", "说话人 2"],
        lines=[
            TranscriptLine("说话人 1", "00:03", "全托管的目标是降低门槛。"),
            TranscriptLine("说话人 2", "00:42", "策略组是干什么的？"),
        ],
    )
    return t


class FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.last_prompt = None

    def chat(self, prompt: str, max_tokens: int = 4096) -> str:
        self.last_prompt = prompt
        return self.response


GOOD_JSON = """```json
{
  "summary_intro": "本次会议讨论全托管目标与策略组，内容如下：",
  "outline": [
    {"title": "全托管目标", "children": [
      {"title": "降低门槛", "points": [
        {"title": "面向低操作能力达人", "detail": "直接给做好的视频，点击即发。"}
      ]}
    ]}
  ],
  "todos": [
    {"task": "梳理策略组分发逻辑", "assignee": "说话人 2"}
  ]
}
```"""


def test_generate_maps_llm_json_and_keeps_facts():
    gen = MeetingMinutesGenerator(FakeLLM(GOOD_JSON))
    m = gen.generate(_transcript())
    # LLM 提炼字段
    assert m.summary_intro.startswith("本次会议讨论全托管")
    assert m.outline[0]["title"] == "全托管目标"
    assert m.outline[0]["children"][0]["points"][0]["title"] == "面向低操作能力达人"
    assert m.todos[0]["task"] == "梳理策略组分发逻辑"
    assert m.todos[0]["assignee"] == "说话人 2"
    # 来自 transcript 的客观事实
    assert m.meeting_title == "全托管"
    assert m.meeting_date == "2026年6月2日 下午 5:51"
    assert "14分钟 43秒" in m.meeting_time
    assert m.participants == ["说话人 1", "说话人 2"]
    assert m.keywords == ["策略", "创作者"]


def test_generate_tolerates_trailing_comma_json():
    # 尾随逗号 —— 复用 _safe_json_loads 第 3 轮修复
    dirty = '{"summary_intro": "x", "outline": [], "todos": [],}'
    gen = MeetingMinutesGenerator(FakeLLM(dirty))
    m = gen.generate(_transcript())
    assert m.summary_intro == "x"
    assert m.outline == []


def test_generate_falls_back_when_llm_unparseable():
    gen = MeetingMinutesGenerator(FakeLLM("这是一段完全不是 JSON 的自然语言回复。"))
    m = gen.generate(_transcript())
    # 不抛异常，outline 空，summary_intro 给兜底，事实字段仍在
    assert m.outline == []
    assert m.summary_intro != ""
    assert m.participants == ["说话人 1", "说话人 2"]


def test_generate_truncates_long_full_text_in_prompt():
    t = _transcript()
    t.lines = [TranscriptLine("说话人 1", "00:01", "字" * 20000)]
    fake = FakeLLM('{"summary_intro":"x","outline":[],"todos":[]}')
    MeetingMinutesGenerator(fake).generate(t)
    # full_text 截断到 12000 字喂入，prompt 不应包含第 13000 个字位置的内容
    assert fake.last_prompt is not None
    assert len(fake.last_prompt) < 13000 + 2000  # prompt 模板 + 截断正文
