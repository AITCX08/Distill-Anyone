# Distill-Anyone

> B站知识区UP主视频内容 → 结构化知识 → SKILL.md

将B站UP主的视频内容，通过自动化流水线转化为可供AI助手使用的结构化知识文件（SKILL.md）。

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  ① 爬取   │───→│  ② ASR   │───→│  ③ 清洗   │───→│  ④ 建模   │───→│  ⑤ 生成   │───→│ SKILL.md │
│ 视频+音频  │    │ 语音转文字│    │ 文本处理  │    │ 知识提取  │    │ 模板渲染  │    │  知识文件 │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
 bilibili-api      FunASR        规则+LLM       Claude API       Jinja2
   yt-dlp        paraformer-zh
```

## 功能特性

- **全自动流水线**: 从视频爬取到SKILL.md生成，一条命令完成
- **分步可控**: 每个阶段可独立运行，支持断点续传
- **FunASR中文识别**: 使用阿里达摩院 paraformer-zh 模型，中文识别效果优秀
- **智能知识提取**: 通过 Claude API 进行主题切分、知识建模和博主画像生成
- **RAG兼容格式**: 所有中间数据采用JSON格式存储，可直接接入RAG系统
- **开箱即用**: 完善的配置模板和中文文档

## 环境要求

- Python 3.11+
- ffmpeg（yt-dlp 音频转换依赖）
- GPU（可选，FunASR支持CPU运行，GPU更快）

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/CJWang-bilibili/Distill-Anyone.git
cd Distill-Anyone
```

### 2. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 安装 ffmpeg（如未安装）
# Ubuntu/Debian:
sudo apt install ffmpeg
# Mac:
brew install ffmpeg
```

### 3. 配置环境变量

```bash
cp config.example.env .env
```

编辑 `.env` 文件，填写以下必要配置：

#### B站Cookie获取方法

1. 用浏览器登录 [bilibili.com](https://www.bilibili.com)
2. 按 `F12` 打开开发者工具
3. 切换到 `Application`（应用）标签页
4. 在左侧找到 `Cookies` → `https://www.bilibili.com`
5. 复制以下三个值：
   - `SESSDATA` → 填入 `BILIBILI_SESSDATA`
   - `bili_jct` → 填入 `BILIBILI_BILI_JCT`
   - `buvid3` → 填入 `BILIBILI_BUVID3`

#### LLM API 配置（Claude 或 OpenAI 二选一）

**方式一：Claude API（默认）**

1. 访问 [console.anthropic.com](https://console.anthropic.com/)
2. 注册/登录后创建 API Key
3. 将 Key 填入 `ANTHROPIC_API_KEY`
4. 设置 `LLM_PROVIDER=claude`

**方式二：OpenAI API**

1. 访问 [platform.openai.com](https://platform.openai.com/)
2. 注册/登录后创建 API Key
3. 将 Key 填入 `OPENAI_API_KEY`
4. 设置 `LLM_PROVIDER=openai`
5. 如果使用兼容接口（如第三方代理），修改 `OPENAI_BASE_URL`

#### UP主UID获取

1. 打开目标UP主的B站主页
2. URL中的数字即为UID，例如 `space.bilibili.com/12345678` 中的 `12345678`
3. 填入 `UP_UID`

### 4. 运行

```bash
# 一键运行完整流水线（使用.env中配置的LLM）
python main.py run --uid 12345678

# 指定使用 OpenAI 运行
python main.py run --uid 12345678 --llm openai

# 或分步运行
python main.py crawl --uid 12345678    # 爬取+下载
python main.py asr                      # 语音识别
python main.py clean                    # 文本清洗（默认用.env配置的LLM）
python main.py clean --llm openai       # 文本清洗（指定用OpenAI）
python main.py model                    # 知识建模
python main.py generate                 # 生成SKILL.md
```

## 项目架构

```
Distill-Anyone/
├── main.py                      # CLI入口（click子命令）
├── src/
│   ├── config.py                # 配置管理（.env加载+Pydantic校验）
│   ├── crawl/                   # 阶段1：数据采集
│   │   ├── video_list.py        #   获取UP主视频列表
│   │   ├── audio_download.py    #   yt-dlp下载音频
│   │   └── subtitle.py          #   获取B站官方字幕
│   ├── asr/                     # 阶段2：语音识别
│   │   └── funasr_engine.py     #   FunASR引擎封装
│   ├── clean/                   # 阶段3：文本清洗
│   │   └── text_processor.py    #   去口语化+主题切分
│   ├── model/                   # 阶段4：知识建模
│   │   └── knowledge_extractor.py  # Claude API知识提取
│   └── generate/                # 阶段5：Skill生成
│       └── skill_generator.py   #   Jinja2模板渲染
├── templates/
│   └── skill.md.j2              # SKILL.md Jinja2模板
├── prompts/                     # LLM提示词模板
│   ├── clean_transcript.txt     #   文本清洗提示词
│   ├── extract_knowledge.txt    #   知识提取提示词
│   └── topic_segment.txt        #   主题分段提示词
├── data/                        # 运行时数据（自动创建，已gitignore）
│   ├── audio/                   #   下载的音频文件
│   ├── transcripts/             #   ASR转写结果（JSON）
│   ├── cleaned/                 #   清洗后文本（JSON）
│   └── knowledge/               #   知识模型（JSON）
├── examples/
│   └── sample.skill.md          # 示例输出
└── output/                      # 最终输出（已gitignore）
```

## 流水线详解

### 阶段1：数据采集 (`crawl`)

- 使用 `bilibili-api-python` 分页获取UP主的所有视频BV号和元信息
- 使用 `yt-dlp` 下载音频流（wav格式，FunASR最佳输入）
- 尝试获取B站官方CC字幕（如有，可跳过ASR阶段）
- 自动跳过已下载的文件（断点续传）

### 阶段2：语音识别 (`asr`)

- 使用 FunASR 的 `paraformer-zh` 模型
- 配合 `fsmn-vad`（语音活动检测）和 `ct-punc`（标点恢复）
- 输出带时间戳的转写结果
- 支持CPU和GPU运行

### 阶段3：文本清洗 (`clean`)

- **规则清洗**: 去除语气词（嗯、啊、那个、就是说...）、合并短片段
- **LLM辅助**: 使用Claude API进行主题切分和语义分段
- 输出结构化的主题文档

### 阶段4：知识建模 (`model`)

- 使用Claude API从每个视频提取：核心观点、关键概念、论点论据
- 跨视频综合分析生成UP主画像：领域专长、表达风格、口头禅等
- 输出结构化的 `BloggerProfile` JSON

### 阶段5：生成SKILL.md (`generate`)

- 使用Jinja2模板将知识画像渲染为SKILL.md
- 包含：核心观点、表达风格、标志性用语、擅长领域、典型问答等
- 可直接用于AI助手的Skill系统

## 数据存储格式（RAG兼容）

所有中间产物采用JSON格式，每条记录包含完整元信息，可直接用于RAG检索系统。

### 转写结果格式

```json
{
    "bvid": "BV1xxxxx",
    "title": "视频标题",
    "source": "funasr",
    "model": "paraformer-zh",
    "full_text": "完整转写文本...",
    "segments": [
        {
            "id": "BV1xxxxx_seg_0001",
            "text": "片段文本",
            "start": 0.0,
            "end": 15.3,
            "confidence": 0.95
        }
    ],
    "metadata": {
        "pubdate": 1704067200,
        "duration": "10:30",
        "view_count": 50000
    }
}
```

### 清洗结果格式

```json
{
    "bvid": "BV1xxxxx",
    "title": "视频标题",
    "full_text": "清洗后文本...",
    "topics": [
        {
            "id": "BV1xxxxx_topic_001",
            "title": "主题名称",
            "content": "主题内容...",
            "tags": ["标签1", "标签2"]
        }
    ]
}
```

## 配置说明

| 环境变量 | 说明 | 必填 |
|---------|------|------|
| `BILIBILI_SESSDATA` | B站Cookie SESSDATA | 是（爬取阶段） |
| `BILIBILI_BILI_JCT` | B站Cookie bili_jct | 是（爬取阶段） |
| `BILIBILI_BUVID3` | B站Cookie buvid3 | 是（爬取阶段） |
| `UP_UID` | 目标UP主的UID | 是 |
| `LLM_PROVIDER` | LLM提供商 (claude/openai) | 否（默认claude） |
| `ANTHROPIC_API_KEY` | Claude API Key | 当 LLM_PROVIDER=claude 时必填 |
| `ANTHROPIC_MODEL` | Claude模型名称 | 否（默认claude-sonnet-4-20250514） |
| `OPENAI_API_KEY` | OpenAI API Key | 当 LLM_PROVIDER=openai 时必填 |
| `OPENAI_BASE_URL` | OpenAI API Base URL | 否（默认官方地址，支持兼容接口） |
| `OPENAI_MODEL` | OpenAI模型名称 | 否（默认gpt-4o） |
| `FUNASR_MODEL` | FunASR模型 | 否（默认paraformer-zh） |
| `FUNASR_VAD_MODEL` | VAD模型 | 否（默认fsmn-vad） |
| `FUNASR_PUNC_MODEL` | 标点恢复模型 | 否（默认ct-punc） |
| `DATA_DIR` | 数据存储目录 | 否（默认./data） |
| `OUTPUT_DIR` | 输出目录 | 否（默认./output） |

## 常见问题

### Q: FunASR模型下载很慢怎么办？

FunASR首次运行会自动从ModelScope下载模型。国内用户一般下载速度正常。如遇问题，可设置ModelScope镜像：

```bash
export MODELSCOPE_CACHE=~/.cache/modelscope
```

### Q: 没有GPU可以运行吗？

可以。FunASR支持CPU运行，只是速度较慢。长视频（>30分钟）建议使用GPU。

### Q: B站Cookie会过期吗？

会。SESSDATA的有效期通常为数天到数周。如果遇到认证错误，请重新获取Cookie。

### Q: 可以处理多少个视频？

理论上无限制。流水线支持断点续传，中断后重新运行会自动跳过已完成的步骤。

### Q: Claude API费用大约多少？

取决于视频数量和文本长度。以50个10分钟视频为例，大约消耗几美元的API费用（主要在文本清洗和知识建模阶段）。

## 授权说明

使用本工具蒸馏UP主内容前，请确保已获得UP主本人的授权。建议使用以下授权模板：

```
本人 [UP主名称]（UID: [UID]）授权 [使用者] 使用 Distill-Anyone 工具
对我在B站发布的视频内容进行知识蒸馏，用于 [用途说明]。

授权日期：[日期]
```

## 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的改动 (`git commit -m '添加某个特性'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

MIT License
