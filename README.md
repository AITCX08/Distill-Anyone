# Distill-Anyone

> 将公开内容转化为可复用的结构化知识：逐作品 Markdown、聚合 Skill 与 RAG 知识块。

Distill-Anyone 是一个本地优先的内容蒸馏工具。它可以从创作者主页枚举可见作品，完成下载、转写、清洗、知识提取与输出；也保留 PDF、DOCX、TXT 文档蒸馏和会议纪要能力。

当前正式支持 Bilibili 与抖音。平台接入、内容处理和输出形式相互解耦：增加一个平台不需要复制蒸馏流水线，增加一种输出也不需要了解平台的私有 ID 或抓取细节。

## 核心能力

- **多平台创作者蒸馏**：通过统一的 Source Adapter 接入 Bilibili、抖音；后续可扩展小红书等平台。
- **双输出形态**：每件作品生成独立 Markdown（episodes），也可聚合为一个 `SKILL.md`；两者可同时生成。
- **可恢复流水线**：任务状态、产物哈希与阶段进度持久化；中断后从最近的有效阶段恢复，支持单项重试。
- **真实进度与本地 Dashboard**：下载字节进度、阶段进度、ETA、实时 trace、暂停/恢复/取消和产物预览。
- **中文 ASR 与 LLM 知识提取**：FunASR 自动选择 CUDA / Apple Silicon MPS / CPU；支持 Claude、OpenAI、Qwen、DeepSeek 和 Ollama。
- **文档、融合与 RAG**：PDF/DOCX/TXT 按章节蒸馏；视频与书籍可融合为一个 Skill；可输出中立的 RAG chunks JSON。
- **本地安全边界**：Dashboard 固定监听 `127.0.0.1`；登录在外部浏览器完成，界面不展示或保存二维码、Cookie、API Key。

## 架构概览

```text
CLI / Local Dashboard
          │
          ▼
  DistillationService
          │
          ├── PlatformManager ── PlatformRegistry
          │       ├── BilibiliAdapter
          │       └── DouyinAdapter
          │
          ├── SourceDistillationRunner
          │       ├── 下载队列（默认 3）
          │       ├── ASR 队列（默认 1）
          │       └── LLM 队列（默认 3）
          │
          ├── JobState / ArtifactStore / EventHub
          │
          └── OutputManager ── OutputRegistry
                  ├── episodes/*.md
                  ├── SKILL.md
                  └── RAG chunks JSON
```

领域边界如下：

| 层 | 职责 |
| --- | --- |
| `src/platforms/` | 识别链接、登录、枚举作品、刷新素材地址和下载；不调用 ASR 或 LLM。 |
| `src/application/` | `DistillationService`、作业仓库、事件、并发租约、状态查询与控制。 |
| 既有处理模块 | `crawl`、`asr`、`clean`、`model`、`generate`、`rag` 负责可复用领域能力。 |
| `src/outputs/` | 将规范化产物写为 episodes、Skill 或 RAG；不依赖平台私有字段。 |
| `src/dashboard/` + `dashboard/` | FastAPI/SSE 本地服务与 React 作战台，均通过应用服务访问同一任务状态。 |

## 快速开始

### 1. 安装

要求：Python 3.10+（CI 使用 3.11）、`ffmpeg`。抖音适配器还需要 Playwright Chromium。

```bash
git clone https://github.com/AITCX08/Distill-Anyone.git
cd Distill-Anyone

python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

安装 `ffmpeg`：Windows 可使用 `winget install ffmpeg`；macOS 使用 `brew install ffmpeg`；Ubuntu/Debian 使用 `sudo apt install ffmpeg`。

### 2. 配置

复制模板并填写一个可用的 LLM 提供商配置：

```bash
copy config.example.env .env        # Windows
# cp config.example.env .env        # macOS / Linux
```

`.env` 中常用项目：

| 配置 | 用途 |
| --- | --- |
| `LLM_PROVIDER` | `claude`、`openai`、`qwen`、`deepseek` 或 `ollama`。 |
| 对应的 `*_API_KEY` | 使用云端 LLM 时填写；Ollama 不需要 API Key。 |
| `DATA_DIR` / `OUTPUT_DIR` | 中间产物和最终产物的根目录。 |
| `DOUYIN_PROFILE_DIR` | 抖音外部 Chromium 的持久化登录目录，默认在 `data/browser/douyin`。 |
| `DISTILL_*` | 多平台任务的并发、重试、临时媒体保留策略。 |

不要提交 `.env`、浏览器 profile、Cookie、下载媒体、任务状态或实际蒸馏产物。

### 3. 蒸馏一个创作者

先查看平台能力与登录状态。对需要认证的平台，使用外部可见浏览器扫码：

```bash
python main.py source platforms
python main.py source status douyin
python main.py source login douyin
```

创建者任务默认同时产出 episodes 与 Skill。建议先预检，确认枚举结果后再执行正式任务：

```bash
# 仅解析和枚举：不下载、不调用 ASR/LLM、不创建任务产物
python main.py source creator "https://www.douyin.com/user/SEC_UID" --dry-run

# 抖音：默认输出 episodes + skill
python main.py source creator "https://www.douyin.com/user/SEC_UID"

# Bilibili 走同一入口
python main.py source creator "https://space.bilibili.com/12345678" --platform bilibili
```

常用选项：

```bash
# 只保留逐作品 Markdown；或者只生成 Skill
python main.py source creator "<创作者主页>" --emit episodes
python main.py source creator "<创作者主页>" --emit skill

# 追加 RAG chunks，保留下载媒体，或只重试失败作品
python main.py source creator "<创作者主页>" --rag-chunks --keep-media
python main.py source creator "<创作者主页>" --resume --retry-failed

# 根据机器资源调整并发；ASR 始终限定为一个 worker
python main.py source creator "<创作者主页>" \
  --download-workers 3 --asr-workers 1 --llm-workers 3 --max-active 3
```

任务状态保存在 `data/jobs/<platform>/<creator-id>/job_state.json`。每个视频以下载 → 转写 → 清洗 → 知识提取 → 输出的顺序处理；图文作品当前会被明确标记为 `unsupported_note`，纳入 coverage，但不会被错误地报告为完成。

## 本地 Dashboard

Dashboard 是单用户、本地作战台，使用 FastAPI + SSE + React。它和 CLI 复用同一个 `DistillationService`、任务状态和事件流。

```bash
# 默认启动后打开 http://127.0.0.1:8765
python main.py dashboard

# 不自动打开浏览器，或指定端口
python main.py dashboard --no-open
python main.py dashboard --port 9000
```

Dashboard 提供：

- 平台状态与“打开外部登录浏览器”；扫码仍在 Chromium 中完成。
- 任务预检、创建、实时下载/阶段进度、ETA 与脱敏 trace。
- 暂停、恢复、取消和失败单项重试。
- 作业历史、产物列表、只读文本预览、复制和在本地资源管理器中定位文件。

服务只绑定 `127.0.0.1`，并对会话、Origin 与写操作使用本地会话/CSRF 校验。它不是局域网或公网服务；请勿通过端口转发把它暴露到不受信任网络。

## 输出与目录

创作者任务会按创作者隔离输出：

```text
output/
└── <creator>-<platform>-<creator-id>/
    ├── episodes/
    │   └── <item-id>.md
    ├── rag/
    │   └── <platform>_<item-id>.json
    └── SKILL.md

data/
├── jobs/<platform>/<creator-id>/job_state.json
├── browser/douyin/                 # 本地登录 profile
├── transcripts/                    # 转写 JSON
├── cleaned/                        # 清洗后的结构化文本
├── knowledge/                      # 单项知识与聚合画像
└── rag_chunks/                     # 中立 RAG chunks JSON
```

`episodes/*.md` 适合逐篇阅读、归档与检索；`SKILL.md` 是以全部有效作品为语料生成的聚合人格/知识文件。两种输出可独立选择。RAG 是第三种可组合输出，不影响 episodes/Skill 的选择。

## 保留的文档与会议能力

多平台架构没有替代原有能力，以下命令继续可用：

```bash
# PDF / DOCX / TXT：默认章节化蒸馏并生成 RAG chunks
python main.py distill --file "书籍.pdf" --name "作者名" --llm deepseek

# 视频与书籍章节作为对等素材融合为一个 Skill
python main.py fuse --name "人物名" --llm deepseek \
  --sources "BV*" --sources "BOOK_书名_*"

# 为已有素材重建 RAG chunks
python main.py chunks --source-id "BOOK_书名_*"

# 飞书妙记/会议纪要入口
python main.py meeting --help
python main.py feishu-meeting --help
```

旧版 Bilibili 分阶段命令 `login`、`crawl`、`asr`、`clean`、`model`、`generate`、`run` 也保留，便于已有脚本和工作流迁移；新项目优先使用 `source creator` 或 Dashboard。

## 扩展一个平台或输出

新增平台时，在 `src/platforms/` 实现 `PlatformAdapter` 并注册到 `PlatformRegistry`。适配器只负责平台边界：匹配、认证、解析、枚举、刷新和下载。

新增输出时，在 `src/outputs/` 实现 `OutputTarget` 并注册到 `OutputRegistry`。输出目标声明需要哪些规范化产物，然后消费单项产物或在 corpus 完成后统一 `finalize()`。

因此，未来接入小红书或 OCR 图文处理时，不需要修改 episodes/Skill/RAG 输出层；新增 Notion、Obsidian 等输出时，也不需要认识 `bvid`、`aweme_id` 等平台细节。详细的数据契约、恢复策略和扩展指南见 [DEVELOPMENT.md](./DEVELOPMENT.md)。

## 前端开发与验证

发布包已经包含构建后的 Dashboard 静态资源，普通使用者不需要 Node.js。修改前端时需要 Node.js **24.x**：

```bash
cd dashboard
npm ci
npm run build
npm test
npm run e2e
```

Python 测试在项目根目录运行：

```bash
python -m pytest -q
```

提交前至少执行与改动范围相符的测试，并检查 Markdown 与前端构建产物是否同步。完整开发规范、数据契约和架构细节请阅读：

- [DEVELOPMENT.md](./DEVELOPMENT.md)：长期维护文档、模块职责、数据格式与扩展点。
- [CLAUDE.md](./CLAUDE.md)：AI 编程协作约定与仓库反模式。
- [多平台设计](./docs/superpowers/specs/2026-07-21-multi-platform-distillation-design.md)：Source Adapter 与双输出设计。
- [Dashboard 设计](./docs/superpowers/specs/2026-07-21-local-dashboard-design.md)：本地 Dashboard 的接口、安全与交互设计。

## 使用边界

仅处理你有权访问、保存和再利用的公开内容，并遵守平台条款、版权规则和当地法律。登录信息仅应保存在你控制的本地设备上；不要在 issue、日志、截图或提交中泄露 Cookie、二维码、API Key 或个人数据。

## 许可证

[MIT License](./LICENSE)
