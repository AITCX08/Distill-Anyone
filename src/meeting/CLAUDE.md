[← 返回 Distill-Anyone](../../CLAUDE.md) > **src/meeting**

# src/meeting -- 飞书妙记文字记录 → 智能会议纪要（MD + PDF）

## 变更记录 (Changelog)

| 日期 | 变更 |
|---|---|
| 2026-06-04 | 初始化模块：`models.py` / `transcript_parser.py` / `minutes_generator.py` / `renderer.py`，`meeting` CLI 命令（阶段一：txt 路径） |
| 2026-06-05 | 阶段二实现：新增 `audio_transcriber.py`（ffmpeg 转码 + FunASR cam++ 说话人分离 + 相邻同说话人合并）；`meeting` 命令按文件后缀分流，音频路径走 `audio_to_transcript`，txt 路径走 `parse_feishu_txt` |
| 2026-06-23 | Stage1 复用重构：抽出 pipeline.py（meeting_output_paths + transcript_to_minutes_files），meeting() 改为调用它；feishu-meeting 命令复用同一管线 |

---

## 模块职责

本模块将飞书妙记导出的**文字记录 `.txt`** 加工成**飞书风格「智能纪要」**，输出 Markdown + PDF：

1. **解析阶段**：`transcript_parser` 读取妙记 txt，解析日期 / 时长 / 关键词 / 说话人+时间戳+正文，产出客观事实 `MeetingTranscript`。
2. **生成阶段**：`minutes_generator` 把 `MeetingTranscript` 发给 LLM，产出主观摘要 `MeetingMinutes`（总结导言 / 三层大纲 / 待办事项）。
3. **渲染阶段**：`renderer` 把两者拼成飞书风格 Markdown，再经 HTML 中间层转成 PDF（weasyprint + PingFang 字体）。

**调用方**：`main.py::meeting()` CLI 命令。

**阶段一（已实现）**：支持飞书妙记 txt 文字记录路径。
**阶段二（已实现）**：音频路径（`.mp3/.wav/.m4a/.flac/.aac/.ogg`）→ `audio_transcriber.audio_to_transcript`：ffmpeg 转码为 16kHz 单声道 WAV → `FunASREngine(spk_model="cam++")` 转写并带说话人标签 → 相邻同说话人合并 → `MeetingTranscript`。`meeting` 命令按后缀自动分流两条路径。

---

## 数据流

```
飞书妙记 txt 文件
        │
        ▼
parse_feishu_txt(text)
        │  MeetingTranscript（客观事实）
        │  title / date_str / duration_str / keywords
        │  speakers / lines / full_text (property)
        ▼
MeetingMinutesGenerator.generate(transcript)
        │  LLM（summary_intro / outline / todos）
        │  MeetingMinutes（主观摘要）
        │  meeting_title / meeting_date / meeting_time
        │  participants / keywords / summary_intro
        │  outline: list[dict] (三层) / todos: list[dict]
        ▼
render_markdown(minutes, transcript)  ──→  .md 文件
render_pdf(md_text, output_path)      ──→  .pdf 文件
```

输出路径：`output/{name}-纪要-{时间戳}.{md,pdf}`（由 `src/meeting/pipeline.py::meeting_output_paths()` 构造）。

---

## 入口与启动

| 文件 | 关键函数 / 类 | 签名 |
|---|---|---|
| `audio_transcriber.py` | `audio_to_transcript` | `(audio_path: Path, config: AppConfig) -> MeetingTranscript`（ffmpeg + FunASR cam++ + merge） |
| `audio_transcriber.py` | `convert_to_wav16k` | `(src: Path, dst: Path) -> None`（ffmpeg 转 16kHz 单声道 WAV） |
| `audio_transcriber.py` | `_merge_consecutive` | `(segments: list[TranscriptSegment]) -> list[TranscriptLine]`（相邻同说话人合并） |
| `audio_transcriber.py` | `_fmt_ts` | `(seconds: float) -> str`（秒 → MM:SS 或 HH:MM:SS） |
| `models.py` | `TranscriptLine` | `dataclass: speaker, timestamp, text` |
| `models.py` | `MeetingTranscript` | `dataclass: title, date_str, duration_str, keywords, speakers, lines` + `full_text: str`（property，拼接所有 `line.text`） |
| `models.py` | `MeetingMinutes` | `dataclass: meeting_title, meeting_date, meeting_time, participants, keywords, summary_intro, outline: list[dict], todos: list[dict]` |
| `transcript_parser.py` | `parse_feishu_txt` | `(text: str) -> MeetingTranscript` |
| `minutes_generator.py` | `MeetingMinutesGenerator` | `(llm_client: LLMClient)` |
| `minutes_generator.py` | `MeetingMinutesGenerator.generate` | `(transcript: MeetingTranscript) -> MeetingMinutes` |
| `minutes_generator.py` | `MEETING_MINUTES_PROMPT` | 文件底部常量（Prompt 位置硬规则，见下） |
| `renderer.py` | `render_markdown` | `(minutes: MeetingMinutes, transcript: MeetingTranscript) -> str` |
| `renderer.py` | `markdown_to_html` | `(md_text: str) -> str`（python-markdown extra/sane_lists/nl2br + 复选框转换） |
| `renderer.py` | `_render_task_items` | 内部辅助：把 `todos` 渲染为 Markdown 复选框 |
| `renderer.py` | `render_pdf` | `(md_text: str, output_path: Path) -> None`（MD → HTML → weasyprint PDF） |
| `main.py` | `meeting()` | CLI 命令：`--file`, `--llm`, `--title`, `--no-pdf` |
| `src/meeting/pipeline.py` | `meeting_output_paths()` | 构造 `.md` / `.pdf` 输出路径 |

---

## 对外接口 / 数据契约

### `MeetingTranscript`（解析产物，客观事实）

```python
@dataclass
class TranscriptLine:
    speaker: str     # 说话人N（如 "说话人1"）
    timestamp: str   # 原始时间戳字符串
    text: str        # 正文（多行合并后）

@dataclass
class MeetingTranscript:
    title: str
    date_str: str
    duration_str: str
    keywords: list[str]
    speakers: list[str]   # 去重保序
    lines: list[TranscriptLine]

    @property
    def full_text(self) -> str: ...   # 拼接所有 line.text
```

### `MeetingMinutes`（LLM 产物，主观摘要）

```python
@dataclass
class MeetingMinutes:
    meeting_title: str
    meeting_date: str
    meeting_time: str
    participants: list[str]
    keywords: list[str]
    summary_intro: str
    outline: list[dict]   # 三层嵌套（见下），渲染时 L1/L2 加粗、L3 普通，对齐飞书参考
    todos: list[dict]     # 待办复选框
```

`outline` 是**三层嵌套**的 `list[dict]`（不是带 `level` 的扁平列表）：

```python
outline = [
    {
        "title": "大主题",            # 第 1 层
        "children": [
            {
                "title": "子主题",     # 第 2 层
                "points": [
                    {"title": "要点短句", "detail": "一两句具体说明"}  # 第 3 层
                ],
            },
        ],
    },
]
```

`todos` 每个 `dict` 形如 `{"task": "任务描述", "assignee": "说话人 N" 或 ""}`（`assignee` 无法判断时为空字符串）。

> 以 `src/meeting/models.py` 的 `MeetingMinutes` docstring 与 `minutes_generator.py` 底部 `MEETING_MINUTES_PROMPT` 的 JSON schema 为准。

---

## 复用点

| 复用来源 | 用法 |
|---|---|
| `src/asr/funasr_engine.FunASREngine(spk_model="cam++")` | `audio_transcriber.py` 内部 lazy import，启用说话人分离转写 |
| `src/reader/document_reader.read_document` | `meeting()` CLI 读取 txt 文件内容 |
| `src/clean/text_processor.create_llm_client` | 构造 `MeetingMinutesGenerator` 所用的 LLM 客户端 |
| `src/model/knowledge_extractor._safe_json_loads` | `minutes_generator.py` 内 lazy import，修复 LLM JSON 输出抖动（7 轮容错） |
| `src/model/knowledge_extractor._extract_json_payload` | 同上，剥 `<think>` / ` ```json ` 代码块 + 括号计数找完整 JSON 块 |
| `src/model/knowledge_extractor._dump_llm_failure` | 同上，LLM 失败时落盘到 `data/llm_debug/`，不抛异常 |

> **延迟导入（lazy import）铁律**：`minutes_generator.py` 在函数体内部 import 上述三个私有函数，绝不在模块顶部 import `knowledge_extractor`，以避免循环依赖并保持 CLI 启动速度。

---

## Prompt 位置（硬规则）

- **唯一运行时 Prompt**：`MEETING_MINUTES_PROMPT` 常量位于 `minutes_generator.py` **文件底部**。
- 修改 Prompt 时，JSON schema 注释（outline 结构 / todos 结构）必须保留，否则 LLM 输出格式会漂移。
- `prompts/` 目录里若存在参考文件，**只是只读参考，不影响运行时行为**。

---

## 渲染结构（飞书参考）

`render_markdown` 产出的 Markdown 结构（纯 Python 字符串拼接）：

```
# {会议标题}

> 日期：…  时长：…  参与人：…  关键词：…

# 总结

{summary_intro}

  **L1 标题**（加粗，缩进 2 空格）
    **L2 内容**（加粗，缩进 4 空格）
      L3 细节（不加粗，缩进 6 空格）

# 待办事项

- [ ] 待办 1
- [ ] 待办 2

# 关键词

{keywords 逗号分隔}

# 文字记录

{说话人 + 时间戳 + 正文，逐行}
```

> **不要改用 jinja2 渲染总结大纲**：三层缩进对空白字符高度敏感，jinja2 的 `trim_blocks` / `lstrip_blocks` 会破坏对齐。保持纯 Python 字符串拼接。

---

## 反模式（不要做）

1. **不要**在 `audio_transcriber.py` 模块顶部 `import` `FunASREngine` —— 必须在 `audio_to_transcript` 函数体内 lazy import（FunASR 是重依赖，影响 CLI 启动速度）。
2. **不要**让 `render_markdown` 改用 jinja2 模板渲染「总结」三层缩进大纲 —— 空白敏感，jinja2 trim/lstrip 会破坏飞书对齐。
3. **不要**在 `minutes_generator.py` / `renderer.py` 模块顶部 `import markdown` / `import weasyprint` / `from jinja2 import ...` —— 这三个重依赖必须在函数体内 lazy import（根级硬规则 #4）。
4. **不要**在 `MeetingMinutes.outline` 里硬塞飞书参考里没有的板块（如"背景"、"决策理由"等额外层）—— 保持三层结构与飞书智能纪要对齐。
5. **不要**在 LLM 失败时抛异常让 CLI 崩溃 —— 应调用 `_dump_llm_failure` 落盘 + 降级返回空壳 `MeetingMinutes`（保持 `generate` 对外无异常的契约）。
6. **不要**直接把 `MeetingTranscript.full_text` 截断后跳过 `_extract_json_payload` 剥壳步骤 —— 各 LLM 供应商（特别是 DeepSeek-R1）会在 JSON 前后附加思考链 / markdown 代码块。

---

## 关键依赖

| 依赖 | 用途 | 安装方式 |
|---|---|---|
| `markdown` (python-markdown) | `renderer.py::markdown_to_html`：MD → HTML | `pip install markdown` |
| `weasyprint` | `renderer.py::render_pdf`：HTML → PDF | `pip install weasyprint` + `brew install pango`（必须） |
| `jinja2` | `renderer.py::render_pdf` HTML 外壳（`templates/feishu_minutes.html.j2`，PingFang CSS） | 已有（项目已依赖） |

> `brew install pango` 是 weasyprint 在 macOS 上的必要系统依赖，缺少时 `render_pdf` 会在 import 时报 OSError。

---

## 测试与质量

建议覆盖的测试文件：

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/test_meeting_parser.py` | `parse_feishu_txt`：正常 txt / 多行合并 / 说话人去重保序 / 缺关键词降级 |
| `tests/test_meeting_minutes.py` | `MeetingMinutesGenerator.generate`：LLM mock 正常路径 + JSON 容错 + LLM 失败降级（不抛异常） |
| `tests/test_meeting_renderer.py` | `render_markdown` MD 结构（标题/blockquote/大纲缩进/复选框）+ `render_pdf` 产物存在且非零字节 |

当前状态：**测试文件待补**（阶段一实施时尚未建立）。

---

## 相关文件清单

| 文件 | 用途 |
|---|---|
| `src/meeting/__init__.py` | 模块标记（空） |
| `src/meeting/models.py` | `TranscriptLine` / `MeetingTranscript` / `MeetingMinutes` 数据类 |
| `src/meeting/audio_transcriber.py` | 音频路径：ffmpeg 转码 + FunASR cam++ 转写 + 说话人合并 → `MeetingTranscript` |
| `src/meeting/transcript_parser.py` | `parse_feishu_txt`：解析妙记 txt → `MeetingTranscript` |
| `src/meeting/minutes_generator.py` | `MeetingMinutesGenerator.generate`：LLM 产出摘要 + `MEETING_MINUTES_PROMPT`（文件底部） |
| `src/meeting/renderer.py` | `render_markdown` / `render_pdf`：输出 MD + PDF |
| `templates/feishu_minutes.html.j2` | render_pdf 的 HTML 外壳（飞书 CSS + PingFang 字体） |
| `main.py::meeting()` | CLI 命令调用处（`--file`, `--llm`, `--title`, `--no-pdf`） |
| `src/meeting/pipeline.py` | 管线复用层：`MeetingTranscript` → MD/PDF，meeting/feishu-meeting 共用（`meeting_output_paths` + `transcript_to_minutes_files`） |
| `src/reader/document_reader.py` | 复用：`read_document` 读取 txt |
| `src/clean/text_processor.py` | 复用：`create_llm_client` LLM 工厂 |
| `src/model/knowledge_extractor.py` | 复用：`_safe_json_loads` / `_extract_json_payload` / `_dump_llm_failure` |
