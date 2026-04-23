# Distill-Anyone

> 视频/文档内容 → 结构化知识 → SKILL.md / RAG 知识块

将B站UP主的视频内容或书籍/文档（PDF/DOCX/TXT），通过自动化流水线转化为可供AI助手使用的结构化知识文件（SKILL.md），并同时产出 RAG 友好的标准化知识块。

> **v0.3 新能力**（2026-04）：
> - 📚 **书籍章节模块化**：`distill` 默认按章节独立处理，每章一份 cleaned + knowledge
> - 🔀 **视频 + 书籍融合**：新增 `fuse` 命令，对等合成统一的 SKILL.md
> - 🧠 **RAG 知识块输出**：自动产出 `data/rag_chunks/` 标准 chunks，可直接接入向量库
> - 🛠 **新增 CLI**：`fuse` / `chunks` 两条命令；`distill` 加 `--by-chapter` / `--rag-chunks` 开关

**🎯 用本工具产出的开源 Skill 示例**：[戎震.skill](https://github.com/CJWang-bilibili/RongZheng-skill) — 基于 100 个 B 站视频 + 书籍《戎震避坑》72 章融合蒸馏的 Claude Code Skill。

```
视频路径（B站 UP 主）：
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  ① 爬取   │───→│  ② ASR   │───→│  ③ 清洗   │───→│  ④ 建模   │───→│  ⑤ 生成   │───→│ SKILL.md │
│ 视频+音频  │    │ 语音转文字│    │ 文本处理  │    │ 知识提取  │    │ 模板渲染  │    │  知识文件 │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
 bilibili-api      FunASR        规则+LLM         LLM API          Jinja2
   yt-dlp        paraformer-zh

文档路径（PDF / DOCX / TXT 书籍或文章）：
┌─────────────┐    ┌────────────┐    ┌──────────┐    ┌──────────┐
│ distill      │───→│ 章节切分    │───→│  ④ 建模  │───→│  ⑤ 生成   │───→ SKILL.md
│ 文档读取     │    │ 每章独立     │    │ 知识提取 │    │ 模板渲染  │
└─────────────┘    └────────────┘    └──────────┘    └──────────┘
                                                              └────→ data/rag_chunks/ （供 RAG Agent 检索）

融合蒸馏（视频 + 书籍章节 对等喂给画像合成）：
cleaned/{BV*}.json  ┐
                    ├──→ fuse ──→ blogger_profile.json ──→ 统一 SKILL.md
cleaned/{BOOK_*_chNN}.json ┘
```

## 功能特性

- **全自动流水线**: 从视频爬取到 SKILL.md 生成，一条命令完成
- **文档蒸馏（章节模块化）**: PDF/DOCX/TXT 书籍按章节独立蒸馏，每章一份 cleaned + knowledge，便于检索与迭代
- **视频 + 书籍融合**: `fuse` 命令将同一人物的视频集与书籍章节对等合成统一 SKILL.md，书提供深度框架、视频提供表达 DNA
- **RAG 友好知识块**: 自动产出 `data/rag_chunks/` 标准化 chunks JSON（含 source_type / chapter / char_range / keywords 元数据），可直接喂入向量库
- **断点续传**: 每个阶段自动检测文件完整性,已处理的跳过,损坏的重新处理
- **音频完整性检查**: 自动检测付费视频未完整下载的情况,开通会员后重新运行自动补全
- **FunASR 中文识别**: 使用阿里达摩院 paraformer-zh 模型,自动选择 CUDA / Apple Silicon (MPS) / CPU,OOM 自动降级重试
- **女娲 / 张雪峰.skill 风格对齐**: 生成的 SKILL.md 完全对齐 [女娲.skill](https://github.com/alchaincyf/nuwa-skill) / [张雪峰.skill](https://github.com/alchaincyf/zhangxuefeng-skill) 格式——角色扮演规则、Agentic Protocol、身份卡、心智模型(带证据/应用/局限三段)、决策启发式(带场景/案例)、7 维度表达 DNA、人物时间线、价值观三层(追求/拒绝/内在张力)、智识谱系、关键引用等
- **多 LLM 支持**: Claude / OpenAI / Qwen / DeepSeek / Ollama(本地免费)五选一

## 环境要求

- **Python** 3.9+(推荐 3.11+;macOS 系统自带 3.9 也可)
- **ffmpeg**(yt-dlp 音频提取 + FunASR 音频解码依赖)
- **加速硬件**(可选):
  - NVIDIA GPU(CUDA)——Windows / Linux,最快
  - Apple Silicon (M1/M2/M3/M4) MPS——macOS,自动启用
  - CPU 也能跑,只是慢 5-10 倍

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/CJWang-bilibili/Distill-Anyone.git
cd Distill-Anyone
```

### 2. 安装依赖

**方案 A:conda(推荐 Windows / Linux + NVIDIA)**

```bash
conda create -n Distill-Anyone python=3.11
conda activate Distill-Anyone

# 安装 PyTorch(CUDA 版,按实际 CUDA 版本选择)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 安装项目依赖
pip install -r requirements.txt
```

**方案 B:venv(推荐 macOS / 无 GPU)**

```bash
# 创建虚拟环境
python3 -m venv Distill-Anyone
source Distill-Anyone/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# funasr 未在 requirements 中把 torch 列为硬依赖,需要手动补装
pip install torch torchaudio
```

**安装 ffmpeg**(系统级依赖,不在虚拟环境内):

```bash
# Windows
winget install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# macOS(需要先装 Homebrew: https://brew.sh)
brew install ffmpeg
```

### 3. 配置环境变量

```bash
cp config.example.env .env
```

编辑 `.env` 文件，填写以下配置：

#### B站登录（二选一）

**方式一（推荐）: 扫码登录**
```bash
python main.py login
```
自动弹出二维码，用B站App扫码即可。凭据自动缓存，过期自动刷新。

**方式二: 手动填写 Cookie**

在 `.env` 中填入 `BILIBILI_SESSDATA`、`BILIBILI_BILI_JCT`、`BILIBILI_BUVID3`（从浏览器 F12 → Application → Cookies 获取）。

> **注意**: 手动 Cookie 有效期数天到数周。推荐使用扫码登录，省去手动操作。

#### LLM API 配置（五选一）

项目支持 5 种 LLM 后端，只需配置其中一个：

| 提供商 | `LLM_PROVIDER` 值 | API Key 变量 | 推荐模型 | 费用 |
|--------|------------------|--------------|---------|------|
| Claude | `claude` | `ANTHROPIC_API_KEY` | claude-sonnet-4-6 | 付费 |
| OpenAI | `openai` | `OPENAI_API_KEY` | gpt-4o | 付费 |
| 通义千问 | `qwen` | `QWEN_API_KEY` | qwen3-235b-a22b | 有免费额度 |
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | deepseek-chat | 极低价 |
| Ollama | `ollama` | 无需 | qwen2.5:3b | **免费本地** |

**推荐**: DeepSeek `deepseek-chat`（V3），中文能力强，价格极低（100个视频约1-2元人民币）。

**本地免费方案（Ollama）**:
```bash
# 1. 安装 Ollama: https://ollama.com
# 2. 下载模型（4GB显存推荐3b）
ollama pull qwen2.5:3b
# 3. .env 配置
# LLM_PROVIDER=ollama
# OLLAMA_MODEL=qwen2.5:3b
```

#### UP主UID获取

打开目标UP主的B站主页，URL中的数字即为UID：
`space.bilibili.com/`**`12345678`** → UID 为 `12345678`

### 4. 运行

```bash
# 一键运行完整流水线（获取全部视频）
python main.py run --uid 12345678

# 限制只获取前 20 个视频
python main.py run --uid 12345678 --max-videos 20

# 指定 LLM
python main.py run --uid 12345678 --llm deepseek

# 只运行部分阶段（已有结果的阶段自动跳过已处理文件）
python main.py run --stages 3-5 --llm deepseek   # 只跑阶段3到5
python main.py run --uid 12345678 --stages 1,3-5  # 跑阶段1和3-5

# 分步运行
python main.py crawl --uid 12345678 --max-videos 20  # 阶段1: 爬取+下载
python main.py asr                                    # 阶段2: 语音识别
python main.py clean --llm deepseek                  # 阶段3: 文本清洗
python main.py model --llm deepseek                  # 阶段4: 知识建模
python main.py generate                               # 阶段5: 生成SKILL.md

# 文档蒸馏（PDF/DOCX/TXT → SKILL.md，无需B站账号）
# 默认按章节模块化处理 + 自动产出 RAG chunks
python main.py distill --file 书籍.pdf --llm deepseek --name "作者名"

# 关闭章节化（旧行为：整书一份 cleaned/knowledge）
python main.py distill --file 书籍.pdf --no-by-chapter

# 关闭 RAG chunks 输出
python main.py distill --file 书籍.pdf --no-rag-chunks

# 视频 + 书籍 融合蒸馏（对等合成统一 SKILL.md）
python main.py fuse --name "戎震" --llm deepseek \
  --sources "BV*" --sources "BOOK_戎震避坑_*"

# 独立重建 RAG chunks（修改 chunker 参数后用）
python main.py chunks --source-id "BOOK_戎震避坑_*"
```

## CLI 参数说明

### `distill` — 文档蒸馏（书籍/文章 → SKILL.md）

```
python main.py distill --file <路径> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--file` | 文档文件路径（支持 .txt .docx .pdf） | **必填** |
| `--llm` | LLM 提供商 | `.env` 中配置 |
| `--name` | 作者/人物名称，用于输出文件名和画像 | 文件名 |
| `--by-chapter / --no-by-chapter` | 按章节独立处理（每章产出独立的 cleaned + knowledge） | `--by-chapter` |
| `--rag-chunks / --no-rag-chunks` | 同时产出 RAG 友好 chunks JSON 到 `data/rag_chunks/` | `--rag-chunks` |

**默认（章节模式）一条命令完成**：章节切分 → 每章 cleaned → 每章知识提取 → RAG chunks → 画像合成 → SKILL.md。

**章节切分策略**：
1. 优先正则识别中文章节标题（"第 X 章" / "1." / "一、"），命中 ≥ 3 个按章节切
2. 否则按 5000-8000 字硬切，标题统一 `第 N 部分`
3. 重跑同一本书时会自动清理同 `BOOK_{stem}_{md5}_ch*` 前缀的旧 cleaned/knowledge/rag_chunks（防 stale 章节污染）

**输出 ID 规范**：
- 书 ID：`BOOK_{stem}_{md5_6}`
- 章节 ID（=cleaned/knowledge 文件名）：`BOOK_{stem}_{md5_6}_ch{NN}`
- 兼容旧路径：`--no-by-chapter` 仍走原 `DOC_{stem}_{md5_6}` 单文件方案

### `fuse` — 视频 + 书籍 融合蒸馏

```
python main.py fuse --name <人物名> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--name` | 人物名称，用于 SKILL.md 文件名和画像 | **必填** |
| `--llm` | LLM 提供商 | `.env` 中配置 |
| `--sources` | 要融合的素材 glob（可多次指定），如 `"BV*"`、`"BOOK_戎震避坑_*"` | **必填** |

**行为**：
- 按 glob 从 `data/cleaned/` 收集匹配的 cleaned JSON
- 自动加载或补提 `data/knowledge/` 中对应的知识文件
- 视频和书章节作为对等的素材单元喂给同一个画像合成 Prompt
- 合成 `data/knowledge/blogger_profile.json` + `output/{name}-{YYYYMMDD-HHMMSS}.skill.md`（每次新增带时间戳，不覆盖历史）

**source_type 自动识别**：`BV*` → video，`BOOK_*_chNN` → book_chapter，`DOC_*` → document。

**安全设计**：仅按显式 `--sources` glob 收集，不做隐式全量扫描，避免误纳入历史素材。

### `chunks` — RAG 知识块重建

```
python main.py chunks --source-id <glob> [...]
```

| 参数 | 说明 |
|------|------|
| `--source-id` | 要重建 chunks 的 cleaned 文件 glob（可多次指定） |

**行为**：从已有 `data/cleaned/` + `data/knowledge/` 重新生成 `data/rag_chunks/{source_id}.json`，幂等覆盖。

**适用场景**：调整 chunker 切片参数、补出旧素材的 chunks、在已有视频/章节基础上单独构建 RAG 检索源。

**chunk 切分策略**（`src/rag/chunker.py`）：
- 优先按 cleaned.topics 出 chunk（每个 topic 一个 chunk）
- topic 超长（> 1000 字）时按 `target_size=1000` + `overlap=100` 二次切
- chunk.summary 优先复用 knowledge.summary，缺失时退首句
- chunk.keywords 优先 knowledge.key_concepts[:8]，缺失时退 topic.tags
- char_range 在 full_text 中精确定位，失败时标 `metadata.range_inferred=true`

### `crawl` — 阶段1: 数据采集

```
python main.py crawl [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--uid` | UP主UID，覆盖 `.env` 中的 `UP_UID` | `.env` 中配置 |
| `--max-videos` | 本地总共保留多少个视频，`0` 表示全部 | `0` |

**断点续传逻辑**:
- 本地已有且**完整**的音频 → 直接跳过，不计入 `--max-videos` 数量
- 本地已有但**不完整**的音频（如开通会员前下载的付费视频）→ 自动重新下载替换
- 完整性判断：比较实际音频时长与视频元信息中的时长，误差超过30秒视为不完整
- 无法下载的视频（地区限制、已删除等）→ 跳过不计数

> **付费视频补全**: 开通充电/大会员后，只需重新运行 `python main.py crawl`，工具会自动检测哪些视频时长不足并重新下载，已完整的文件不会重复处理。

### `asr` — 阶段2: 语音识别

```
python main.py asr [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--delete-audio / --keep-audio` | 转写并校验通过后删除音频以释放磁盘 | `--delete-audio` |
| `--watch` | 持续监听 audio 目录，新音频出现就转写（适合大量视频边下边转写） | 关闭 |
| `--watch-interval` | watch 模式两次扫描的间隔秒数 | `60` |

- 自动设备检测:**CUDA → MPS (Apple Silicon) → CPU** 三级回退
- 已有**完整**转写结果的视频自动跳过
- 对已有结果做完整性校验(JSON是否损坏、full_text是否为空、时长是否匹配),不完整则重新转写
- CUDA / MPS OOM 时自动清理缓存并以更小批次(batch_size_s=60)重试
- **转写完成后立即删除音频**（双保险：先 save_transcript 再做完整性校验，校验通过才 unlink；失败则保留音频供下次重试）

#### 🚀 推荐：边下载边转写（避免大批量视频撑爆磁盘）

1266 个视频 × ~30MB WAV ≈ 40GB，磁盘可能扛不住。打开两个终端并行跑即可，磁盘占用始终很小：

```bash
# 终端 1: 持续下载（已转写的 BV 即使音频被删，crawl 也不会重复下载）
python main.py crawl --uid 12345678

# 终端 2: 持续监听并转写，转写完立刻删音频
python main.py asr --watch --watch-interval 60
```

**工作原理**：
- `crawl` 启动时把 `data/transcripts/{bvid}.json` 完整的 BV 也算入「已处理」集合，跳过重复下载
- `asr --watch` 每 60 秒扫一次 `data/audio/`，新出现的就转写、转写完立刻 `unlink` 释放磁盘
- 两个进程通过 `data/transcripts/` 这个共享目录隐式协调，无需锁

任意一端 Ctrl+C 退出，断点续传保证状态一致，重启后从中断处继续。

### `clean` — 阶段3: 文本清洗

```
python main.py clean [--llm PROVIDER]
```

| 参数 | 说明 |
|------|------|
| `--llm` | LLM提供商，覆盖 `.env` 配置 |

- 去除口语填充词（嗯、啊、那个、就是说等）
- LLM按主题切分，生成带 tags 的结构化段落
- 已有**完整**清洗结果的视频自动跳过；清洗结果比原文短10%以上时重新处理

### `model` — 阶段4: 知识建模

```
python main.py model [--llm PROVIDER]
```

- 已有**完整**单视频知识结果的自动跳过（检查 summary、core_views 是否为空）
- 加载所有单视频知识后，重新合成博主总画像（`blogger_profile.json`）
- 提取 nuwa-skill 风格的深层知识：思维框架、判断准则、表达DNA、价值观、反模式、知识边界

### `generate` — 阶段5: 生成SKILL.md

```
python main.py generate
```

- 读取 `blogger_profile.json`，用 Jinja2 模板渲染为 SKILL.md
- 每次重新生成（速度极快，约1秒）

### `run` — 一键运行

```
python main.py run [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--uid` | UP主UID | `.env` 中配置 |
| `--max-videos` | 本地总共保留视频数，`0` 表示全部 | `0` |
| `--llm` | LLM提供商 | `.env` 中 `LLM_PROVIDER` |
| `--stages` | 执行的阶段，支持 `all`/`1,2,3`/`3-5`/`1,3-5` | `all` |

## 项目架构

```
Distill-Anyone/
├── main.py                         # CLI入口（10 个子命令：login/crawl/asr/clean/model/generate/distill/fuse/chunks/run）
├── requirements.txt
├── config.example.env              # 环境变量模板
├── src/
│   ├── config.py                   # 配置管理（.env加载+Pydantic校验）
│   ├── crawl/                      # 阶段1：数据采集
│   │   ├── auth.py                 #   B站扫码登录 + 凭证缓存（三级策略）
│   │   ├── video_list.py           #   获取UP主视频列表（增量、412重试）
│   │   ├── audio_download.py       #   yt-dlp下载音频+完整性检查+重下载
│   │   └── subtitle.py             #   获取B站官方字幕（备用）
│   ├── asr/                        # 阶段2：语音识别
│   │   └── funasr_engine.py        #   FunASR引擎（GPU检测+OOM重试+完整性校验）
│   ├── clean/                      # 阶段3：文本清洗 + LLM 客户端工厂
│   │   └── text_processor.py       #   去口语化+LLM主题切分+create_llm_client()
│   ├── model/                      # 阶段4：知识建模
│   │   └── knowledge_extractor.py  #   nuwa-skill知识提取+画像合成+JSON容错+sources字段
│   ├── generate/                   # 阶段5：Skill生成
│   │   └── skill_generator.py      #   Jinja2模板渲染
│   ├── reader/                     # 文档蒸馏入口（PDF/DOCX/TXT）
│   │   └── document_reader.py      #   章节切分 + 章节级 cleaned 产出
│   └── rag/                        # RAG 知识块输出
│       └── chunker.py              #   topic 优先切块 + 元数据标注
├── templates/
│   └── skill.md.j2                 # SKILL.md Jinja2模板（nuwa-skill风格）
├── tests/                          # pytest 单元测试
├── examples/
│   └── sample.skill.md             # 示例输出
├── data/                           # 运行时数据（自动创建，已gitignore）
│   ├── audio/                      #   下载的音频文件（WAV）
│   ├── transcripts/                #   ASR转写结果（JSON，含句级时间戳）
│   ├── cleaned/                    #   清洗后结构化文本（视频 BV* 与书章节 BOOK_*_chNN 共存）
│   ├── knowledge/                  #   单素材知识 + blogger_profile.json
│   ├── rag_chunks/                 #   RAG 友好的 chunks JSON（schema_version 1.0）
│   └── .cache/modelscope/          #   FunASR模型缓存（本地化，不写入系统目录）
└── output/                         # 最终输出（已gitignore）
    └── {name}-{YYYYMMDD-HHMMSS}.skill.md   # 每次跑都新增带时间戳的版本，不覆盖
```

## 技术实现细节

### 阶段1：数据采集

- **视频列表**: 使用 `bilibili-api-python` 分页拉取UP主投稿列表，支持增量拉取（传入已有bvid集合跳过）
- **反爬处理**: 遇到 HTTP 412 时指数退避（10s/20s 重试），页间随机延迟 3-6s
- **音频下载**: `yt-dlp` 下载最佳音质，ffmpeg 转 WAV 格式
- **完整性检查**: Python `wave` 模块读取实际时长，与视频元数据时长对比（30s容差）
- **配额计算**: `--max-videos` 表示本地总文件数目标，已有完整文件计入总数，不完整/新增的才消耗配额

### 阶段2：语音识别

- **模型**: FunASR `paraformer-zh`(达摩院) + `fsmn-vad`(端点检测) + `ct-punc`(标点恢复)
- **设备自动检测**: `torch.cuda.is_available()` → `torch.backends.mps.is_available()` → CPU;CUDA 时设置 `expandable_segments` 减少显存碎片
- **句级时间戳**: `sentence_timestamp=True`,解析 `sentence_info` 得到每句的起止时间(毫秒级)
- **OOM 处理**: `batch_size_s=300` → OOM 时 `torch.cuda.empty_cache()` 或 `torch.mps.empty_cache()` → `batch_size_s=60` 重试
- **完整性校验**: 检查 JSON 有效性 + full_text 非空 + 转写结束时间与音频实际时长差值 < 60s

### 阶段3：文本清洗

- **规则清洗**: 正则匹配中文语气词/填充词（嗯、啊、那个、就是说等），合并过短片段（< 10字）
- **LLM主题切分**: 按视频主题将全文切分为带 title/content/tags 的结构化段落，输出 RAG 兼容格式
- **统一LLM接口**: `LLMClient` Protocol，`ClaudeLLMClient`（Anthropic SDK）和 `OpenAILLMClient`（OpenAI兼容）两种实现，DeepSeek/Qwen/Ollama 复用后者
- **重处理判断**: 文件不存在 / JSON损坏 / full_text为空 / 清洗后文本比原始短10%以上 → 重处理

### 阶段4：知识建模（nuwa-skill方法论）

**单视频提取** (`VIDEO_KNOWLEDGE_PROMPT`) 提取：
- `summary`、`core_views`、`key_concepts`、`topics`、`arguments`（原有）
- `mental_model_hints` — 博主用于分析问题的框架线索
- `decision_examples` — 具体决策情境 + 推理过程 + 结论
- `expression_samples` — 能体现表达风格的原话片段

**博主画像合成** (`PROFILE_SYNTHESIS_PROMPT`) 生成：
- `self_intro` — 第一人称自我介绍
- `mental_models` — 归纳的思维框架（name / description / trigger）
- `decision_heuristics` — 判断准则（rule / source / application）
- `expression_dna` — 表达DNA（开场/逻辑连接词/强调/收尾）
- `values` / `anti_patterns` / `honest_boundaries`
- `typical_qa_pairs` — 完全按博主风格的示例问答

**JSON容错解析** (`_safe_json_loads`) 5轮修复：
1. 直接解析
2. 清理控制字符 + 转义字符串内裸换行
3. 移除尾随逗号
4. 替换 `...` 省略占位符
5. 截断到最后合法的 `}` 处（处理输出截断）

### 阶段5：SKILL.md生成

- **模板风格**: 参考 [nuwa-skill](https://github.com/hotcoffeeshake/tong-jincheng-skill) 风格，包含效果示例、心智模型表格、表达DNA、诚实边界等章节
- **Jinja2渲染**: 所有 `BloggerProfile` 字段注入模板，空字段自动跳过不渲染

### 文档蒸馏 + RAG 输出

**文档读取** (`src/reader/document_reader.py`)：
- 三种格式延迟导入：`.txt`（utf-8）、`.docx`（python-docx）、`.pdf`（PyMuPDF）
- 章节切分：正则识别 ≥ 3 个中文章节标题按章节切；否则按 5000-8000 字硬切并标 `第 N 部分`
- 每章产出独立 `cleaned/{BOOK_*_chNN}.json`，与视频路径完全同 schema（章节专属字段在 `metadata` 内）

**章节 metadata 扩展字段**：`source_type` / `chapter_index` / `chapter_title` / `parent_book_id` / `total_chapters` / `char_range`

**RAG chunks** (`src/rag/chunker.py`)：
- 优先按 `cleaned.topics` 出 chunk（每 topic 一个）
- topic 超长时按 `target_size=1000` + `overlap=100` 字符二次切
- chunk.summary 优先复用 `knowledge.summary`，缺失退首句
- chunk.keywords 优先复用 `knowledge.key_concepts[:8]`，缺失退 topic.tags
- chunk.char_range 在 full_text 中精确定位，定位失败时标 `metadata.range_inferred=true`
- 输出 schema：`{schema_version, source_id, source_type, source_title, parent_id, chunks: [...]}`，详见 `DEVELOPMENT.md` §2

### 视频 + 书籍 融合蒸馏

- **对等融合**：`fuse` 命令把视频集和书章节作为对等的素材单元喂给 `PROFILE_SYNTHESIS_PROMPT`
- **summaries 标注**：合成时按 `[视频]` / `[书章节]` / `[文档]` 区分来源，让 LLM 区别对待（书提供深度框架、视频提供表达 DNA）
- **BloggerProfile.sources**：新版字段记录所有素材来源（含 `source_type`），保留 `video_sources` 兼容旧 JSON
- **glob 收集**：`fuse --sources "BV*" --sources "BOOK_*_ch*"` 仅按显式 glob 拉取，避免误纳入旧 `DOC_*` 单文档蒸馏产物

## 配置参考

| 环境变量 | 说明 | 必填 |
|---------|------|------|
| `BILIBILI_SESSDATA` | B站Cookie SESSDATA | 是（爬取阶段） |
| `BILIBILI_BILI_JCT` | B站Cookie bili_jct | 是（爬取阶段） |
| `BILIBILI_BUVID3` | B站Cookie buvid3 | 是（爬取阶段） |
| `UP_UID` | 目标UP主的UID | 是 |
| `LLM_PROVIDER` | LLM提供商 (`claude`/`openai`/`qwen`/`deepseek`/`ollama`) | 否（默认`claude`） |
| `ANTHROPIC_API_KEY` | Claude API Key | `LLM_PROVIDER=claude` 时 |
| `ANTHROPIC_MODEL` | Claude模型 | 否（默认`claude-sonnet-4-20250514`） |
| `OPENAI_API_KEY` | OpenAI API Key | `LLM_PROVIDER=openai` 时 |
| `OPENAI_BASE_URL` | OpenAI兼容接口地址 | 否（默认官方地址） |
| `OPENAI_MODEL` | OpenAI模型 | 否（默认`gpt-4o`） |
| `QWEN_API_KEY` | 阿里云 DashScope API Key | `LLM_PROVIDER=qwen` 时 |
| `QWEN_MODEL` | Qwen模型 | 否（默认`qwen3-235b-a22b`） |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | `LLM_PROVIDER=deepseek` 时 |
| `DEEPSEEK_MODEL` | DeepSeek模型 | 否（默认`deepseek-reasoner`；长文本提取推荐改为 `deepseek-chat` 更省钱） |
| `OLLAMA_BASE_URL` | Ollama服务地址 | 否（默认`http://localhost:11434/v1`） |
| `OLLAMA_MODEL` | Ollama本地模型 | 否（默认`qwen2.5:3b`） |
| `FUNASR_MODEL` | FunASR模型 | 否（默认`paraformer-zh`） |
| `FUNASR_VAD_MODEL` | VAD模型 | 否（默认`fsmn-vad`） |
| `FUNASR_PUNC_MODEL` | 标点恢复模型 | 否（默认`ct-punc`） |
| `DATA_DIR` | 数据存储目录 | 否（默认`./data`） |
| `OUTPUT_DIR` | 输出目录 | 否（默认`./output`） |

## 常见问题

**付费视频之前没下完整，开通会员后怎么补全？**

直接重新运行 `python main.py crawl --uid 你的UID`，工具会自动对比每个已下载音频的实际时长与视频元信息，检测到时长不足的音频会自动重新下载替换，完整的文件不会重复处理。

**没有 GPU 可以运行吗？**

可以。FunASR 支持 CPU 运行,速度较慢(约慢 5-10 倍)。程序自动按 CUDA → MPS → CPU 顺序选择,无需手动配置。

**Mac(Apple Silicon)怎么加速?**

M1/M2/M3/M4 芯片上会自动使用 PyTorch 的 MPS 后端,显示 `检测到 Apple Silicon,使用 MPS 加速`。若希望强制 CPU 运行可临时设置环境变量 `PYTORCH_ENABLE_MPS_FALLBACK=1` 或在代码里显式传 `device="cpu"`。

**FunASR模型存在哪里？**

首次运行时自动从ModelScope下载，缓存在项目目录 `data/.cache/modelscope/` 下，不会占用系统全局目录。

**转写时出现 CUDA / MPS out of memory?**

程序会自动清理显存缓存后以更小批次(`batch_size_s=60`)重试。4GB 显存运行超长视频(>2 小时)时偶发,重试后通常能成功。仍失败可在 `.env` 或运行时显式指定 `device="cpu"`。

**模型提取时 JSON 解析失败？**

内置5轮容错修复逻辑，能处理控制字符、裸换行、尾随逗号、`...`占位符、输出截断等常见LLM输出问题。如仍失败，降级使用规则生成基础画像。

**书籍章节切分识别不出来怎么办？**

正则当前主要适配中文书籍目录（"第 X 章 / 1. / 一、"）。如果是英文书或异常排版 PDF，会自动落到 5000-8000 字硬切兜底，标题统一 `第 N 部分`。功能不会失败，只是章节边界粗一些。如需更精细，可以预先把 PDF 用 OCR 后转成 markdown 并手动加章节标题。

**重新跑同一本书会污染旧章节文件吗？**

不会。`distill --by-chapter` 启动时会自动清理同 `BOOK_{stem}_{md5}_ch*` 前缀的旧 cleaned/knowledge/rag_chunks，确保 PDF 改版（章节数变化）时不留 stale 文件。如果你不希望自动清理，目前需要先备份旧产物。

**RAG chunks 怎么接入向量库？**

`data/rag_chunks/{source_id}.json` 是中立的标准格式，每个 chunk 含 `text` / `summary` / `keywords` / `char_range` / `metadata`。直接读取该 JSON，把 `text` 字段送到任意 embedding 模型（bge-m3 / OpenAI text-embedding-3 等），向量与原 chunk 一起存入向量库（Chroma / Qdrant / Milvus 均可）即可检索。

## 开发者文档

如果你想深入定制、二次开发,或使用 AI 辅助编程对本项目进行修改,请阅读:

- **[DEVELOPMENT.md](./DEVELOPMENT.md)** — 详尽的架构设计、数据契约、模块职责、关键算法、扩展点说明,长期维护文档
- **[CLAUDE.md](./CLAUDE.md)** — 给 AI 编程助手(Claude Code / Cursor / Copilot)的硬性约定和反模式清单

## 授权说明

使用本工具蒸馏 UP 主内容前,请确保已获得 UP 主本人的授权。

## 许可证

MIT License
