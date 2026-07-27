import pytest
from src.meeting.models import TranscriptLine, MeetingTranscript, MeetingMinutes
from src.meeting.renderer import render_markdown, markdown_to_html, _render_task_items


def _fixtures():
    transcript = MeetingTranscript(
        title="全托管",
        lines=[
            TranscriptLine("说话人 1", "00:03", "全托管的目标是降低门槛。"),
            TranscriptLine("说话人 2", "00:42", "策略组是干什么的？"),
        ],
    )
    minutes = MeetingMinutes(
        meeting_title="全托管",
        meeting_date="2026年6月2日 下午 5:51",
        meeting_time="2026年6月2日 下午 5:51（时长 14分钟 43秒）",
        participants=["说话人 1", "说话人 2"],
        keywords=["策略", "创作者"],
        summary_intro="本次会议讨论全托管目标，内容如下：",
        outline=[
            {"title": "全托管目标", "children": [
                {"title": "降低门槛", "points": [
                    {"title": "面向低操作能力达人", "detail": "直接给做好的视频。"},
                    {"title": "无 detail 的要点", "detail": ""},
                ]}
            ]}
        ],
        todos=[{"task": "梳理策略组分发逻辑", "assignee": "说话人 2"}],
    )
    return minutes, transcript


def test_render_markdown_title_and_metadata():
    minutes, transcript = _fixtures()
    md = render_markdown(minutes, transcript)
    assert md.startswith("# 智能纪要：全托管 2026年6月2日 下午 5:51")
    assert "> 会议主题：全托管" in md
    assert "> 会议时间：2026年6月2日 下午 5:51（时长 14分钟 43秒）" in md
    assert "> 参会人：@说话人 1@说话人 2" in md
    assert "> 智能会议纪要由 AI 生成，可能不准确，请谨慎甄别后使用" in md


def test_render_markdown_three_level_outline_indent():
    minutes, transcript = _fixtures()
    md = render_markdown(minutes, transcript)
    assert "# 总结" in md
    assert "本次会议讨论全托管目标，内容如下：" in md
    assert "- **全托管目标**" in md
    assert "    - **降低门槛**" in md            # 第 2 层 4 空格缩进
    assert "        - 面向低操作能力达人：直接给做好的视频。" in md  # 第 3 层 8 空格，不加粗（对齐飞书参考）
    assert "        - 无 detail 的要点" in md  # 无 detail 时不带冒号
    assert "        - 无 detail 的要点：" not in md


def test_render_markdown_todos_and_keywords():
    minutes, transcript = _fixtures()
    md = render_markdown(minutes, transcript)
    assert "# 待办" in md
    assert "* [ ] 梳理策略组分发逻辑 @说话人 2" in md
    assert "# 关键词" in md
    assert "策略、创作者" in md


def test_render_markdown_transcript_appendix():
    minutes, transcript = _fixtures()
    md = render_markdown(minutes, transcript)
    assert "# 文字记录" in md
    assert "**说话人 1** 00:03" in md
    assert "全托管的目标是降低门槛。" in md
    # 板块顺序：总结 → 待办 → 关键词 → 文字记录
    assert md.index("# 总结") < md.index("# 待办") < md.index("# 关键词") < md.index("# 文字记录")


def test_render_markdown_omits_empty_sections():
    transcript = MeetingTranscript(title="空会议", lines=[])
    minutes = MeetingMinutes(meeting_title="空会议")
    md = render_markdown(minutes, transcript)
    assert "# 待办" not in md       # 无 todos
    assert "# 关键词" not in md     # 无 keywords
    assert "# 文字记录" in md       # 文字记录段总是有（即使为空）


def test_render_task_items_converts_checkboxes():
    html = "<ul><li>[ ] 做事 A</li><li>[x] 完成 B</li></ul>"
    out = _render_task_items(html)
    assert '<li class="todo">☐ 做事 A</li>' in out
    assert '<li class="todo done">☑ 完成 B</li>' in out


def test_markdown_to_html_renders_nested_list_and_checkbox():
    md = (
        "# 总结\n\n- **A**\n    - **B**\n        - **C**：说明\n\n"
        "# 待办\n\n* [ ] 任务 @说话人 1\n"
    )
    html = markdown_to_html(md)
    assert "<h1" in html
    assert "<strong>A</strong>" in html
    # 嵌套：B 应在 A 的子列表里（出现嵌套 <ul>）
    assert html.count("<ul>") >= 2 or html.count("<ul") >= 2
    assert "☐ 任务 @说话人 1" in html


def test_render_pdf_creates_nonempty_file(tmp_path):
    try:
        __import__("weasyprint")
    except (ImportError, OSError) as exc:
        pytest.skip(f"WeasyPrint native renderer is unavailable: {exc}")
    from src.meeting.renderer import render_pdf
    md = (
        "# 智能纪要：测试 2026年6月2日\n\n> 会议主题：测试\n>\n"
        "> 智能会议纪要由 AI 生成，可能不准确，请谨慎甄别后使用\n\n"
        "# 总结\n\n本次会议内容如下：\n\n- **大主题**\n    - **子主题**\n"
        "        - **要点**：中文说明，确保不乱码。\n\n"
        "# 待办\n\n* [ ] 中文任务 @说话人 1\n\n"
        "# 文字记录\n\n**说话人 1** 00:03\n你好世界。\n"
    )
    out = tmp_path / "test.pdf"
    render_pdf(md, out)
    assert out.exists()
    assert out.stat().st_size > 1000        # 非空 PDF
    assert out.read_bytes()[:5] == b"%PDF-"  # PDF 文件头
