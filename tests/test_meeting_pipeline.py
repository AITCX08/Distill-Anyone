from src.meeting.models import MeetingTranscript, TranscriptLine
from src.meeting.pipeline import meeting_output_paths, transcript_to_minutes_files


class _FakeLLM:
    """MeetingMinutesGenerator 内部会调 llm_client.chat(prompt, max_tokens) -> str。
    返回一段最小可解析的 JSON，让 generate() 走正常路径产出 MeetingMinutes。"""

    def chat(self, prompt, max_tokens=4096):
        return (
            '{"summary_intro": "这是一次测试会议。", '
            '"outline": [{"title": "议题A", "children": []}], '
            '"todos": [{"task": "跟进X", "assignee": "说话人 1"}], '
            '"keywords": ["测试"]}'
        )


def _transcript():
    return MeetingTranscript(
        title="管线测试",
        lines=[TranscriptLine("说话人 1", "00:03", "大家好，开始开会。")],
        speakers=["说话人 1"],
    )


def test_meeting_output_paths_format(tmp_path):
    md, pdf = meeting_output_paths(tmp_path, "周会")
    assert md.parent == tmp_path
    assert md.name.startswith("周会-纪要-") and md.suffix == ".md"
    assert pdf.name.startswith("周会-纪要-") and pdf.suffix == ".pdf"
    assert md.stem == pdf.stem


def test_transcript_to_minutes_files_no_pdf_writes_md(tmp_path):
    md_path, pdf_path = transcript_to_minutes_files(
        _transcript(), _FakeLLM(), tmp_path, no_pdf=True
    )
    assert md_path.exists()
    assert pdf_path is None
    text = md_path.read_text(encoding="utf-8")
    assert text.startswith("# 智能纪要：管线测试")
    assert "# 文字记录" in text


def test_transcript_to_minutes_files_pdf_failure_degrades(tmp_path, monkeypatch):
    def boom(md_text, output_path, template_dir="templates"):
        raise RuntimeError("weasyprint missing pango")

    monkeypatch.setattr("src.meeting.pipeline.render_pdf", boom)
    md_path, pdf_path = transcript_to_minutes_files(
        _transcript(), _FakeLLM(), tmp_path, no_pdf=False
    )
    assert md_path.exists()
    assert pdf_path is None


def test_transcript_to_minutes_files_pdf_success_returns_both(tmp_path, monkeypatch):
    calls = {}

    def fake_render_pdf(md_text, output_path, template_dir="templates"):
        calls["pdf"] = output_path
        return output_path

    monkeypatch.setattr("src.meeting.pipeline.render_pdf", fake_render_pdf)
    md_path, pdf_path = transcript_to_minutes_files(
        _transcript(), _FakeLLM(), tmp_path, no_pdf=False
    )
    assert md_path.exists()
    assert pdf_path is not None
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.stem == md_path.stem      # 同一次调用，md/pdf 共享时间戳 stem
    assert calls["pdf"] == pdf_path           # render_pdf 收到的就是返回的 pdf_path
