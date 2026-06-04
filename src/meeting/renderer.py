"""会议纪要渲染：MeetingMinutes(+Transcript) → Markdown；Markdown → HTML → PDF。

为什么 Markdown 用纯 Python 拼接而非 jinja2：飞书「总结」是缩进敏感的三层嵌套列表
（4/8 空格），jinja2 的 trim_blocks/lstrip_blocks 会吃掉或注入空白，破坏 Markdown
列表层级。PDF 的 HTML 外壳无缩进敏感问题，仍用 jinja2 模板（templates/feishu_minutes.html.j2）。
"""

import re
from pathlib import Path

from rich.console import Console

from src.meeting.models import MeetingMinutes, MeetingTranscript

console = Console()


def render_markdown(minutes: MeetingMinutes, transcript: MeetingTranscript) -> str:
    """渲染为飞书妙记风格的 Markdown 字符串。"""
    out: list[str] = []

    # 标题
    title = f"# 智能纪要：{minutes.meeting_title}"
    if minutes.meeting_date:
        title += f" {minutes.meeting_date}"
    out.append(title)
    out.append("")

    # 元信息 blockquote
    meta: list[str] = []
    if minutes.meeting_title:
        meta.append(f"> 会议主题：{minutes.meeting_title}")
    if minutes.meeting_time:
        meta.append(">")
        meta.append(f"> 会议时间：{minutes.meeting_time}")
    if minutes.participants:
        meta.append(">")
        meta.append("> 参会人：" + "".join(f"@{p}" for p in minutes.participants))
    meta.append(">")
    meta.append("> 智能会议纪要由 AI 生成，可能不准确，请谨慎甄别后使用")
    out.extend(meta)
    out.append("")

    # 总结
    out.append("# 总结")
    out.append("")
    if minutes.summary_intro:
        out.append(minutes.summary_intro)
        out.append("")
    for topic in minutes.outline:
        out.append(f"- **{_g(topic, 'title')}**")
        for sub in topic.get("children", []) or []:
            out.append(f"    - **{_g(sub, 'title')}**")
            for point in sub.get("points", []) or []:
                ptitle = _g(point, "title")
                detail = _g(point, "detail")
                if detail:
                    out.append(f"        - **{ptitle}**：{detail}")
                else:
                    out.append(f"        - **{ptitle}**")
        out.append("")

    # 待办
    if minutes.todos:
        out.append("# 待办")
        out.append("")
        for todo in minutes.todos:
            task = _g(todo, "task")
            assignee = _g(todo, "assignee")
            line = f"* [ ] {task}"
            if assignee:
                line += f" @{assignee}"
            out.append(line)
        out.append("")

    # 关键词
    if minutes.keywords:
        out.append("# 关键词")
        out.append("")
        out.append("、".join(minutes.keywords))
        out.append("")

    # 文字记录（附录，总是输出）
    out.append("# 文字记录")
    out.append("")
    for ln in transcript.lines:
        out.append(f"**{ln.speaker}** {ln.timestamp}")
        if ln.text:
            out.append(ln.text)
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def _g(d: dict, key: str) -> str:
    """宽容取值：非 dict 或缺键返回空串（防 LLM 输出畸形）。"""
    if isinstance(d, dict):
        return str(d.get(key) or "")
    return ""


# ===== HTML / PDF =====

_TASK_DONE_RE = re.compile(r"<li>\s*\[[xX]\]\s*")
_TASK_OPEN_RE = re.compile(r"<li>\s*\[ \]\s*")


def _render_task_items(html: str) -> str:
    """把 markdown 渲染出的 `<li>[ ] …` / `<li>[x] …` 转成飞书复选框样式。"""
    html = _TASK_DONE_RE.sub('<li class="todo done">☑ ', html)
    html = _TASK_OPEN_RE.sub('<li class="todo">☐ ', html)
    return html


def markdown_to_html(markdown_text: str) -> str:
    """Markdown → HTML 片段（含复选框转换）。"""
    import markdown as md_lib  # 延迟导入（根级硬规则 #4）

    body = md_lib.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "nl2br"],
    )
    return _render_task_items(body)


def render_pdf(markdown_text: str, output_path: Path,
               template_dir: str = "templates") -> Path:
    """Markdown → HTML（飞书 CSS 外壳）→ PDF。

    需要 weasyprint（依赖系统库 pango）。调用方应捕获异常做降级（MD 已单独产出）。
    """
    from jinja2 import Environment, FileSystemLoader  # 延迟导入
    from weasyprint import HTML                        # 延迟导入（重 + 需系统库）

    body_html = markdown_to_html(markdown_text)
    env = Environment(loader=FileSystemLoader(template_dir))
    html_doc = env.get_template("feishu_minutes.html.j2").render(body=body_html)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_doc).write_pdf(str(output_path))
    console.print(f"[green]PDF 已生成: {output_path}")
    return output_path
