# Distill-Anyone

> B站知识区UP主视频内容 → 结构化知识 → SKILL.md

将B站UP主的视频内容，通过自动化流水线转化为可供AI助手使用的结构化知识文件（SKILL.md）。

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  ① 爬取   │───→│  ② ASR   │───→│  ③ 清洗   │───→│  ④ 建模   │───→│  ⑤ 生成   │───→│ SKILL.md │
│ 视频+音频  │    │ 语音转文字│    │ 文本处理  │    │ 知识提取  │    │ 模板渲染  │    │  知识文件 │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
 bilibili-api      FunASR        规则+LLM         LLM API          Jinja2
   yt-dlp        paraformer-zh
```

## 功能特性

- **全自动流水线**: 从视频爬取到SKILL.md生成，一条命令完成
- **断点续传**: 每个阶段自动检测文件完整性，已处理的跳过，损坏的重新处理
- **音频完整性检查**: 自动检测付费视频未完整下载的情况，开通会员后重新运行自动补全
- **FunASR中文识别**: 使用阿里达摩院 paraformer-zh 模型，GPU自动加速，OOM自动降级重试
- **nuwa-skill方法论**: 提取思维框架、判断准则、表达DNA、价值观、反模式等深层知识
- **多LLM支持**: Claude / OpenAI / Qwen / DeepSeek / Ollama（本地免费）五选一
- **RAG兼容格式**: 所有中间数据采用JSON格式存储，可直接接入RAG系统

## 环境要求

- Python 3.11+
- ffmpeg（yt-dlp 音频转换依赖）
- GPU（可选，FunASR支持CPU运行，GPU约快5-10倍）

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/CJWang-bilibili/Distill-Anyone.git
cd Distill-Anyone
```

### 2. 安装依赖

```bash
# 创建 conda 虚拟环境（推荐）
conda create -n Distill-Anyone python=3.11
conda activate Distill-Anyone

# 安装 PyTorch（CUDA版，按实际CUDA版本选择）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 安装项目依赖
pip install -r requirements.txt

# 安装 ffmpeg
# Windows:
winget install ffmpeg
# Ubuntu/Debian:
sudo apt install ffmpeg
# Mac:
brew install ffmpeg
```

### 3. 配置环境变量

```bash
cp config.example.env .env
```

编辑 `.env` 文件，填写以下配置：

#### B站Cookie获取方法

1. 用浏览器登录 [bilibili.com](https://www.bilibili.com)
2. 按 `F12` 打开开发者工具
3. 切换到 `Application`（应用）标签页
4. 在左侧找到 `Cookies` → `https://www.bilibili.com`
5. 复制以下三个值：
   - `SESSDATA` → 填入 `BILIBILI_SESSDATA`
   - `bili_jct` → 填入 `BILIBILI_BILI_JCT`
   - `buvid3` → 填入 `BILIBILI_BUVID3`

> **注意**: Cookie 有效期通常为数天到数周，过期后需要重新获取。如果账号开通了充电/大会员，Cookie 代表的是账号会话，会员权限自动生效，无需额外操作。

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
```

## CLI 参数说明

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
python main.py asr
```

- 自动检测 CUDA，有 GPU 则用 GPU，否则用 CPU
- 已有**完整**转写结果的视频自动跳过
- 对已有结果做完整性校验（JSON是否损坏、full_text是否为空、时长是否匹配），不完整则重新转写
- CUDA OOM 时自动清理缓存并以更小批次（batch_size_s=60）重试

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
├── main.py                         # CLI入口（click子命令）
├── requirements.txt
├── config.example.env              # 环境变量模板
├── src/
│   ├── config.py                   # 配置管理（.env加载+Pydantic校验）
│   ├── crawl/                      # 阶段1：数据采集
│   │   ├── video_list.py           #   获取UP主视频列表（增量、412重试）
│   │   ├── audio_download.py       #   yt-dlp下载音频+完整性检查+重下载
│   │   └── subtitle.py             #   获取B站官方字幕（备用）
│   ├── asr/                        # 阶段2：语音识别
│   │   └── funasr_engine.py        #   FunASR引擎（GPU检测+OOM重试+完整性校验）
│   ├── clean/                      # 阶段3：文本清洗
│   │   └── text_processor.py       #   去口语化+LLM主题切分+完整性检查
│   ├── model/                      # 阶段4：知识建模
│   │   └── knowledge_extractor.py  #   nuwa-skill知识提取+画像合成+JSON容错解析
│   └── generate/                   # 阶段5：Skill生成
│       └── skill_generator.py      #   Jinja2模板渲染
├── templates/
│   └── skill.md.j2                 # SKILL.md Jinja2模板（nuwa-skill风格）
├── examples/
│   └── sample.skill.md             # 示例输出
├── data/                           # 运行时数据（自动创建，已gitignore）
│   ├── audio/                      #   下载的音频文件（WAV）
│   ├── transcripts/                #   ASR转写结果（JSON，含句级时间戳）
│   ├── cleaned/                    #   清洗后结构化文本（JSON）
│   ├── knowledge/                  #   单视频知识+博主总画像（JSON）
│   └── .cache/modelscope/          #   FunASR模型缓存（本地化，不写入系统目录）
└── output/                         # 最终输出（已gitignore）
    └── {name}.skill.md
```

## 技术实现细节

### 阶段1：数据采集

- **视频列表**: 使用 `bilibili-api-python` 分页拉取UP主投稿列表，支持增量拉取（传入已有bvid集合跳过）
- **反爬处理**: 遇到 HTTP 412 时指数退避（10s/20s 重试），页间随机延迟 3-6s
- **音频下载**: `yt-dlp` 下载最佳音质，ffmpeg 转 WAV 格式
- **完整性检查**: Python `wave` 模块读取实际时长，与视频元数据时长对比（30s容差）
- **配额计算**: `--max-videos` 表示本地总文件数目标，已有完整文件计入总数，不完整/新增的才消耗配额

### 阶段2：语音识别

- **模型**: FunASR `paraformer-zh`（达摩院） + `fsmn-vad`（端点检测）+ `ct-punc`（标点恢复）
- **GPU自动检测**: `torch.cuda.is_available()`，`expandable_segments` 减少显存碎片
- **句级时间戳**: `sentence_timestamp=True`，解析 `sentence_info` 得到每句的起止时间（毫秒级）
- **OOM处理**: `batch_size_s=300` → OOM时 `torch.cuda.empty_cache()` → `batch_size_s=60` 重试
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

## 配置参考

| 环境变量 | 说明 | 必填 |
|---------|------|------|
| `BILIBILI_SESSDATA` | B站Cookie SESSDATA | 是（爬取阶段） |
| `BILIBILI_BILI_JCT` | B站Cookie bili_jct | 是（爬取阶段） |
| `BILIBILI_BUVID3` | B站Cookie buvid3 | 是（爬取阶段） |
| `UP_UID` | 目标UP主的UID | 是 |
| `LLM_PROVIDER` | LLM提供商 (`claude`/`openai`/`qwen`/`deepseek`/`ollama`) | 否（默认`claude`） |
| `ANTHROPIC_API_KEY` | Claude API Key | `LLM_PROVIDER=claude` 时 |
| `ANTHROPIC_MODEL` | Claude模型 | 否（默认`claude-sonnet-4-6`） |
| `OPENAI_API_KEY` | OpenAI API Key | `LLM_PROVIDER=openai` 时 |
| `OPENAI_BASE_URL` | OpenAI兼容接口地址 | 否（默认官方地址） |
| `OPENAI_MODEL` | OpenAI模型 | 否（默认`gpt-4o`） |
| `QWEN_API_KEY` | 阿里云 DashScope API Key | `LLM_PROVIDER=qwen` 时 |
| `QWEN_MODEL` | Qwen模型 | 否（默认`qwen3-235b-a22b`） |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | `LLM_PROVIDER=deepseek` 时 |
| `DEEPSEEK_MODEL` | DeepSeek模型 | 否（默认`deepseek-chat`） |
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

**没有GPU可以运行吗？**

可以。FunASR支持CPU运行，速度较慢（约慢5-10倍）。程序会自动检测GPU可用性，无GPU时自动切换到CPU。

**FunASR模型存在哪里？**

首次运行时自动从ModelScope下载，缓存在项目目录 `data/.cache/modelscope/` 下，不会占用系统全局目录。

**转写时出现 CUDA out of memory？**

程序会自动清理显存缓存后以更小批次重试。4GB显存运行超长视频（>2小时）时偶发，重试后通常能成功。

**模型提取时 JSON 解析失败？**

内置5轮容错修复逻辑，能处理控制字符、裸换行、尾随逗号、`...`占位符、输出截断等常见LLM输出问题。如仍失败，降级使用规则生成基础画像。

## 授权说明

使用本工具蒸馏UP主内容前，请确保已获得UP主本人的授权。

## 许可证

MIT License
