# 多平台创作者蒸馏与双输出架构设计

日期：2026-07-21

状态：已获口头设计批准，待书面规格复核

目标版本：v0.4

开发基线：`origin/main@5cda109`，功能分支 `codex/douyin-source-adapter`

## 1. 目标与范围

本功能把已验证的“抖音博主全部作品蒸馏”原型重写为 Distill-Anyone 的正式能力，同时把现有 Bilibili 能力纳入统一平台层。系统必须把两个变化轴彻底分开：

1. **内容从哪里来**：Bilibili、Douyin，未来可增加 Xiaohongshu 等平台。
2. **内容蒸馏成什么**：每个作品一份 Markdown、聚合成一个 `SKILL.md`，以及现有 RAG chunks。

核心组合关系为：

```text
DistillationRequest
  = PlatformAdapter
  + ContentProcessor
  + OutputTarget[]
```

平台适配器不得调用 ASR、LLM 或输出模板；输出目标不得知道抖音 `aweme_id`、Bilibili `bvid` 等平台实现细节。增加一个平台或一种输出时，不复制整条蒸馏流水线。

### 1.1 本版本包含

- `PlatformRegistry`、`PlatformManager` 和平台无关的 `SourceItem` 模型。
- 将现有 Bilibili 抓取能力包装为 `BilibiliAdapter`，保留旧 CLI 行为。
- 新增 `DouyinAdapter`：分享链接解析、持久登录会话、创作者解析、分页枚举、跨页去重和素材下载。
- 视频作品复用现有 FunASR、clean、knowledge、Skill 和 RAG 能力。
- 分阶段流水线，默认下载并发 3、ASR 并发 1、LLM 并发 3、最多 3 个活跃作品。
- 原子状态账本、断点续跑、单项重试、应用内 supervisor、Rich Live 进度和双 ETA。
- `EpisodeMarkdownTarget` 与 `SkillTarget` 可单独或同时启用。
- 图文作品在 v0.4 中完整枚举并明确标记为 `unsupported_note`；不得计为完成。OCR 通过后续 `ContentProcessor` 扩展加入，不阻塞首个可发布版本。
- Windows 正式支持；路径、状态、浏览器数据目录和运行逻辑保持 Linux/macOS 可移植。

### 1.2 本版本不包含

- 不迁移 Scout Agent 的 API、数据库、tenant、favorite、ingest_favorite 或私有会话目录。
- 不依赖 PowerShell、Node、`mcporter` 或硬编码用户路径。
- 不把真实 Cookie、浏览器 profile、媒体、模型或用户蒸馏结果提交到 Git。
- 不在 v0.4 实现小红书适配器、OCR、Notion/Obsidian 发布目标或第三方动态插件发现。
- 不重写与本功能无关的文档蒸馏和会议纪要能力。

## 2. 设计原则与方案选择

采用“双注册表 + 统一引擎”方案：

- `PlatformRegistry` 管理“能爬哪些平台”及其能力。
- `OutputRegistry` 管理“能生成哪些输出”。
- `DistillationEngine` 只编排规范化产物，不包含平台分支和输出模板。

没有采用以下方案：

- **按平台各写一套 episodes/skill 管线**：实现快，但平台数 × 输出数会形成重复代码。
- **在单个 runner 中不断增加平台和输出条件分支**：初期文件少，长期难以测试和维护。
- **立即采用 Python entry points 动态插件**：当前只有两个内置平台，引入包发现、版本兼容和插件安全模型超出必要范围。注册表接口保留未来演进空间，但 v0.4 采用显式内置注册。

## 3. 总体架构

```text
CLI
 │
 ▼
DistillationRequest ──► PlatformManager ──► PlatformAdapter
                              │                  │
                              │             SourceItem stream
                              │                  │
                              ▼                  ▼
                         JobStateStore ◄── DistillationEngine
                                               │
                ┌──────────────────────────────┼─────────────────────────────┐
                ▼                              ▼                             ▼
          download queue                  ASR queue                     LLM queue
            workers=3                     workers=1                    workers=3
                │                              │                             │
                └──────────────► ArtifactStore ◄────────────────────────────┘
                                               │
                                      OutputManager
                                       │        │
                                       ▼        ▼
                                 episodes/*.md  SKILL.md (+ RAG)
```

现有五阶段 `crawl → asr → clean → model → generate` 保持为领域能力。新引擎负责把它们组合成可恢复的多作品流水线，而不是重新实现文本清洗、知识提取或 Skill 生成。

## 4. 平台管理层

### 4.1 目录与职责

```text
src/platforms/
  __init__.py
  base.py             # PlatformAdapter Protocol
  models.py           # SourceItem、Creator、Asset、能力描述
  errors.py           # 可操作、可重试、认证、限流等错误类型
  registry.py         # 显式注册和查找
  manager.py          # auto detect、认证状态和调用边界
  bilibili/
    adapter.py        # 包装 src/crawl 现有能力
  douyin/
    adapter.py        # 高层组合
    session.py        # profile、锁、登录与过期检测
    resolver.py       # 分享链接和主页解析
    enumerator.py     # /aweme/post/ 拦截、分页、终止与去重
    downloader.py     # 素材 URL 刷新和下载
```

`PlatformManager` 是 CLI 和引擎唯一接触的平台入口。它负责：

- 根据显式 `--platform` 或 URL 匹配结果选择适配器。
- 在零个或多个适配器匹配时返回明确错误，不猜测。
- 暴露平台列表、能力、依赖与登录状态。
- 把平台异常转换为统一错误分类。
- 不负责下载后的内容处理，不调用 LLM。

### 4.2 公共模型

```python
class ItemType(str, Enum):
    VIDEO = "video"
    GALLERY = "gallery"
    ARTICLE = "article"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class SourceAsset:
    kind: str                 # video | audio | image | cover
    url: str
    index: int = 0
    expected_bytes: int | None = None

@dataclass(frozen=True)
class SourceCreator:
    platform: str
    creator_id: str
    display_name: str
    canonical_url: str
    avatar_url: str | None = None

@dataclass(frozen=True)
class SourceItem:
    platform: str
    item_id: str
    creator_id: str
    item_type: ItemType
    title: str
    description: str
    canonical_url: str
    published_at: datetime | None
    duration_seconds: float | None
    statistics: Mapping[str, int]
    cover_url: str | None
    tags: tuple[str, ...]
    assets: tuple[SourceAsset, ...]
    raw_metadata: Mapping[str, Any]

    @property
    def source_id(self) -> str:
        return f"{self.platform}_{self.item_id}"
```

规则：

- `source_id` 是跨平台唯一、稳定的内部主键；文件名使用 `item_id`，目录已按 creator 隔离。
- `bvid`、`sec_uid`、`aweme_id` 只在各自适配器或 `raw_metadata` 中出现。
- `raw_metadata` 用于诊断和未来字段迁移，不得成为下游必需接口。
- 对动态媒体 URL，枚举阶段保存可用快照，下载前由 `refresh_item()` 刷新。

### 4.3 适配器协议

```python
class PlatformAdapter(Protocol):
    descriptor: PlatformDescriptor

    def matches(self, target: str) -> bool: ...
    def auth_status(self) -> AuthStatus: ...
    def authenticate(self, *, headful: bool) -> None: ...
    def resolve(self, target: str) -> ResolvedTarget: ...
    def get_creator(self, target: ResolvedTarget) -> SourceCreator: ...
    def iter_items(
        self,
        creator: SourceCreator,
        *,
        checkpoint: EnumerationCheckpoint | None,
    ) -> Iterator[EnumerationPage]: ...
    def refresh_item(self, item: SourceItem) -> SourceItem: ...
    def download_assets(
        self,
        item: SourceItem,
        destination: Path,
        *,
        progress: Callable[[int, int | None], None],
    ) -> DownloadedAssets: ...
```

`PlatformDescriptor` 至少声明：`name`、URL patterns、支持的 item types、是否需要浏览器、是否需要登录、可用命令和缺失依赖提示。

### 4.4 Registry 与平台选择

`PlatformRegistry` 提供 `register()`、`get()`、`detect()`、`list_descriptors()`。注册同名平台必须失败，避免导入顺序静默覆盖。

内置注册顺序不影响检测结果：

```python
registry.register(BilibiliAdapter(...))
registry.register(DouyinAdapter(...))
```

选择规则：

1. `--platform douyin` 等显式参数优先，并验证 target 是否可接受。
2. `--platform auto` 要求恰好一个适配器匹配。
3. 裸 UID 只由兼容命令解释为 Bilibili；新 `source creator` 命令不根据纯数字猜平台。

### 4.5 Bilibili 迁移

`BilibiliAdapter` 包装 `src/crawl/auth.py`、`video_list.py`、`audio_download.py`，映射：

- `uid → creator_id`
- `bvid → item_id`
- 旧 `bvid` 产物 → `source_id=bilibili_<bvid>`

现有 `login`、`crawl`、`asr`、`clean`、`model`、`generate`、`run --uid` 保持可用。v0.4 中 `run --uid` 内部调用统一引擎的 Bilibili + Skill 路径，但默认仍只生成 Skill，以避免破坏旧脚本输出预期。

### 4.6 Douyin 行为

- 使用 `playwright~=1.59.0`（即 `>=1.59,<1.60`），并在文档要求 `playwright install chromium`。
- profile 位于 `<data_dir>/browser/douyin/`，由 `.gitignore` 覆盖。
- 同一 profile 使用跨平台排他锁；锁中记录 PID 和时间。进程已不存在时可恢复陈旧锁。
- 分享短链先跟随跳转得到最终 URL，再从主页/API 响应解析 `sec_uid`，不依赖页面展示昵称作为标识。
- 监听 `/aweme/post/` 响应，按 API cursor/`has_more` 分页；页面滚动只是触发器，API 数据是唯一枚举来源。
- 每页原子保存 cursor 和已见 item IDs。按 `item_id` 跨页、跨恢复去重。
- 正常终止条件是 `has_more=false`；若 API 未给出可靠标志，则只有达到已声明作品数或连续受限次数无新 ID 后才以“枚举不完整”结束，不能宣称全量完成。
- 中断恢复沿用未完成 cursor；一个已完成账号再次运行时从首页执行增量探测，以发现置顶在前的新作品。若主页作品总数可靠且未增加，连续两页都是已知 ID 后可停止；总数增加或统计不可靠时继续到第一个稳定的全已知边界，无法证明边界时继续到 `has_more=false`。只把新 ID 送入处理队列，已有有效作品不会重做。
- 下载优先使用作品 API 的直接素材 URL；失效时用同一登录会话刷新详情。不得调用 `mcporter`。

## 5. 内容处理与统一产物

```text
src/distillation/
  request.py          # DistillationRequest 和 CLI 参数校验
  artifacts.py        # ArtifactKind、路径和完整性签名
  store.py            # 原子读写与内容哈希
  processors.py       # 视频/图文处理器分派
  engine.py           # 队列和生命周期编排
  state.py            # 状态模型与迁移
  supervisor.py       # worker 失败恢复
  progress.py         # 只读快照和 Rich Live
  eta.py              # 阶段统计与双 ETA
```

视频标准产物顺序：

```text
SourceItem
  → DownloadedAssets
  → transcript JSON
  → cleaned JSON/text
  → item knowledge JSON
  → Episode Markdown（若启用）
  → creator profile / SKILL.md / RAG（按目标启用）
```

现有 FunASR 引擎在进程内只构造一次，由单个 ASR consumer 独占调用。Scout 的常驻子进程方案只作为“模型只加载一次”的设计证据；本项目已有可复用引擎，不增加无必要的嵌套 Python worker。

### 5.1 图文边界

v0.4 不声称已蒸馏图文：

- 仍下载并保存必要的元数据，但默认不下载全部图片。
- item 状态写为 `unsupported`，错误码为 `unsupported_note`，原因包含“当前版本未启用 OCR”。
- 未识别的作品类型同样写为 `unsupported`，错误码为 `unsupported_item_type`。
- 图文计入枚举总数和 coverage 分母，但不计入 `completed`。
- Skill 可由已完成视频生成，但 metadata 必须写 `partial=true`、支持/不支持数量和 coverage。
- 后续 `GalleryOcrProcessor` 可实现同一处理器接口，不需要修改平台适配器、引擎或输出目标。

## 6. 输出管理层

### 6.1 目录与接口

```text
src/outputs/
  __init__.py
  base.py             # OutputTarget Protocol
  registry.py         # 显式输出注册
  manager.py          # 依赖检查和 finalize 顺序
  episodes.py         # 每作品 Markdown
  skill.py            # 现有 merge + SkillGenerator 包装
  rag.py              # 现有 chunker 包装
```

```python
class OutputTarget(Protocol):
    name: str

    def required_artifacts(self) -> frozenset[ArtifactKind]: ...
    def consume_item(self, context: ItemOutputContext) -> OutputReceipt: ...
    def finalize(self, context: CorpusOutputContext) -> OutputReceipt: ...
```

`OutputManager` 汇总所有目标的 `required_artifacts()`，确保 ASR、clean、knowledge 每个作品最多执行一次。目标失败独立记录，不反向把已经验证的 transcript 判为失效。

### 6.2 Episodes 输出

`EpisodeMarkdownTarget` 在单项知识产物完成后立即原子写入：

```text
output/<safe-creator-name>-<platform>-<creator-id>/episodes/<item-id>.md
```

文件名不使用作品标题。Markdown 至少包含：标题、博主、平台、作品 ID、原始链接、发布时间、作品类型、时长、原始描述、标签、转写正文、清洗正文、摘要/知识点、处理时间、状态和 schema version。

重复运行时，输入 artifact hashes 未改变则跳过；改变则原子覆盖同一稳定路径，不产生重复 episode。

### 6.3 Skill 输出

`SkillTarget` 复用 `merge_knowledge()` 和 `SkillGenerator`：

- 单项完成只更新 corpus index，不反复生成全局 Skill。
- 本轮所有可处理项进入终态后执行一次 `finalize()`。
- corpus fingerprint 为排序后的 `(source_id, knowledge_sha256)` 序列哈希。
- fingerprint 未变化则跳过合并与生成。
- 输出 metadata 记录使用的 source IDs、总枚举数、完成数、不支持数、失败数、coverage 和 `partial`。

### 6.4 RAG 输出

RAG 是独立输出目标，可和 episodes/skill 组合。它复用现有 `src/rag/chunker.py`，对每项 knowledge/cleaned artifact 增量生成 chunks。`--emit both` 指 episodes + skill；RAG 继续由 `--rag-chunks/--no-rag-chunks` 控制，保持现有行为。

### 6.5 CLI 输出语义

新命令：

```text
python main.py source platforms
python main.py source status douyin
python main.py source login douyin
python main.py source creator <target> --platform auto --emit both
```

`source creator` 默认 `--emit both`；允许 `episodes`、`skill`、`both`。兼容 `run --uid` 默认只生成 Skill。其他关键参数：

```text
--output PATH
--download-workers 3
--asr-workers 1
--llm-workers 3
--max-active-items 3
--resume/--no-resume
--retry-failed
--max-attempts 3
--keep-media
--headful
--dry-run
--rag-chunks/--no-rag-chunks
```

约束：默认只允许 `asr-workers=1`。用户显式设置大于 1 时显示显存风险警告；每个 ASR worker 独立模型实例，不能让多个 worker 隐式共享非线程安全引擎。

`--dry-run` 只执行依赖/认证检查、target 解析和作品枚举，打印预计处理/跳过/unsupported 数，不下载素材、不调用 ASR/LLM、不写 job 或输出产物。退出码约定为：0=全部请求目标成功，1=存在最终 failed/unsupported 的 partial 结果，2=参数、依赖、认证、状态损坏等作业级错误。

## 7. 状态、完整性与恢复

状态文件位置：

```text
data/jobs/<platform>/<creator-id>/job_state.json
```

顶层包含 `schema_version`、request、creator、enumeration checkpoint、item map、output map、metrics、created/updated timestamps。每个 item 分开记录处理状态和输出状态：

```json
{
  "processing_status": "transcribing",
  "stage_progress": 0.42,
  "overall_progress": 0.31,
  "attempts": {"download": 1, "asr": 1, "llm": 0},
  "last_error": null,
  "artifacts": {
    "transcript": {"path": "...", "sha256": "...", "valid": true}
  },
  "outputs": {
    "episodes": {"status": "pending", "fingerprint": null}
  },
  "transcript_verified": true,
  "temporary_media_cleaned": false,
  "started_at": "...",
  "updated_at": "...",
  "completed_at": null
}
```

处理状态集合：

```text
pending → enumerated → downloading → downloaded → extracting_audio
→ transcribing → cleaning → summarizing → writing → completed
```

旁路终态/等待态为 `failed`、`retry_wait`、`unsupported`。中断时所有运行态根据最后一个完整 artifact 回退到最近安全阶段，不从头盲跑。

### 7.1 原子写入

状态和文本/JSON 产物统一使用：

1. 同目录临时文件。
2. 写入后 `flush()` 和 `os.fsync()`。
3. 对需要校验的产物重新打开并执行完整性检查。
4. `os.replace()` 原子替换目标。
5. 尽力 fsync 父目录；Windows 不支持目录 fsync 时安全跳过并保留文件级保证。

读端只读最终文件；损坏 JSON 返回明确 `StateCorruptionError`，不得把空状态当作新任务静默覆盖。
较低的已知 schema version 通过纯函数逐版迁移并在成功后原子保存；高于当前程序支持版本的状态必须拒绝读取并提示升级程序，不得降级覆盖。

### 7.2 恢复规则

- `completed` 且所需 artifact/输出 hash 和完整性都有效：跳过。
- 状态为 `completed` 但产物缺失或损坏：从最早失效阶段重做。
- `failed` 且对应阶段 attempts 小于上限：只重试该项。
- `unsupported_note`：保持 unsupported，除非处理能力版本变化。
- enumeration checkpoint 有效：从保存 cursor 继续；checkpoint 无效才重新枚举，并按 item ID 合并。
- `--retry-failed` 只重置失败项的可重试阶段，不影响已完成项。
- 单项失败不终止其他项；最终命令以 partial/failed 汇总决定退出码。

## 8. 并发、重试和 supervisor

引擎使用有界队列和固定消费者：

- 下载队列：3 个 I/O worker。
- ASR 队列：1 个 consumer，共用一次加载的 FunASR 模型。
- LLM 队列：3 个受限 worker；clean 与 knowledge 按单项顺序执行，但不同 item 可交错。
- 活跃作品 semaphore：默认 3，覆盖进入下载至所有单项目标完成的生命周期。

队列 `maxsize` 与 worker 数成比例，避免枚举数很大时内存无限增长。所有并发数来自 CLI/配置。

外部网络操作设置超时、指数退避、随机抖动和错误分类：认证/参数错误不重试；超时、5xx、限流、临时 URL 失效有限重试。日志不得打印 Cookie、Authorization、API key 或完整敏感请求头。

应用内 supervisor 监控 worker task：

- worker 因单项异常退出时先把正在处理项恢复为可重试状态，再在有限重启预算内重建 worker。
- ASR OOM 时清理缓存、降低可配置 batch 参数并只重试当前项；超过上限后标记失败，继续其他项。
- supervisor 自身、状态损坏或认证失效属于作业级失败，停止接收新项并安全落盘。

## 9. 进度与双 ETA

Rich Live 只消费不可变的 `ProgressSnapshot`，不直接修改作业状态。每个活跃 item 固定一行并原地更新，最多显示 3 行；阶段变化不新增行。

阶段权重以可测工作量为基础，初始默认：下载 15%、抽音频 5%、ASR 45%、clean 15%、knowledge 15%、单项输出 5%。具体阶段内进度优先使用字节数、媒体时长/已转写时长和已完成 LLM 子步骤；没有依据时显示阶段名和 `estimating`，不伪造精确百分比。

总进度分母包含全部枚举作品：

```text
total_progress = sum(item_weighted_progress) / enumerated_item_count
```

`unsupported` 只获得枚举元数据对应的有限进度，不提升到 100%。作业只有在所有枚举项均为 `completed` 时显示 100%；存在 unsupported/failed 时显示 partial coverage。

### 9.1 ETA 数据

为每个阶段维护滚动样本：

- download：秒/MB 和近期吞吐。
- extract：秒/媒体分钟。
- ASR：实时率 RTF（处理秒/音频秒）。
- LLM：clean、knowledge 各自耗时及可用 token throughput。
- output：单项及 corpus finalize 耗时。

样本采用最近 N=30 个完成阶段的中位数，并按平台/阶段分桶，减少异常值影响。少于 3 个样本时返回 `estimating`。

### 9.2 两种 ETA

- **ETA total**：估算所有未完成阶段的剩余工作量，分别除以各阶段有效并发，再取流水线关键路径近似，而不是简单按文件数线性外推。
- **ETA active slowest**：对当前活跃 item 分别计算剩余各阶段时间，显示最大值。

枚举尚未结束时，总 ETA 标记为 provisional；发现新作品后允许上调。

## 10. 配置、目录和隐私

`src/config.py` 增加 `DistillationConfig`、`DouyinConfig`，默认值与 CLI 一致。运行数据只写入 `data_dir` 和 `output_dir`：

```text
data/
  browser/douyin/       # profile，忽略
  jobs/                 # 状态，忽略
  media/                # 临时素材，忽略
  transcripts/
  cleaned/
  knowledge/
  rag_chunks/
output/
```

默认 `keep_media=false`。删除临时视频、音频或切片前必须同时满足：

1. transcript 已通过现有完整性检查并原子落盘。
2. 从最终路径重新读取后再次通过检查。

删除失败只记录清理失败，不破坏已完成文本；状态中的 `temporary_media_cleaned=false` 允许后续清理。浏览器 profile、Cookie、API key 永不进入状态、Markdown、日志或错误详情。

## 11. 文件变更规划

### 11.1 新增

- `src/platforms/`：公共模型、协议、注册表、manager、Bilibili 和 Douyin 适配器。
- `src/distillation/`：请求、artifact、状态、引擎、supervisor、进度和 ETA。
- `src/outputs/`：输出协议、注册表、episodes、skill 和 RAG 目标。
- `tests/platforms/`：注册、检测、Bilibili 映射、Douyin resolver/enumerator/session/downloader。
- `tests/distillation/`：状态、原子写、恢复、流水线并发、supervisor、progress、ETA、清理。
- `tests/outputs/`：episodes、skill fingerprint、组合输出和 partial metadata。

### 11.2 修改

- `main.py`：增加 `source` 命令组，兼容命令委托统一引擎。
- `src/config.py`、`config.example.env`：平台、浏览器、并发、重试和输出配置。
- `src/asr/funasr_engine.py`：只增加统一 artifact/进度需要的窄接口，不复制引擎。
- `src/model/knowledge_extractor.py`：把内部主键从隐含 bvid 推广为 source_id，保留旧格式读取。
- `src/generate/skill_generator.py`：支持 corpus metadata 和原子写入。
- `src/rag/chunker.py`：显式使用平台无关 source metadata。
- `.gitignore`：浏览器、作业状态、临时媒体、`input/` 和本地参考快照。
- `requirements.txt`：增加受限版本 Playwright；OCR 不作为 v0.4 必需依赖。
- `README.md`、`DEVELOPMENT.md`：安装、登录、CLI、隐私、恢复、清理、图文边界和排障。

## 12. 测试与验收

全部新增单元测试使用 fixture/mock，不访问真实抖音网络。开发采用测试先行，至少覆盖：

- 分享链接跳转和最终 URL/`sec_uid` 解析。
- `/aweme/post/` 分页、`has_more=false`、跨页去重和不完整枚举。
- registry 重名、auto detect 的零匹配/多匹配。
- Bilibili `bvid` 兼容映射。
- 原子状态写入、损坏状态拒绝覆盖、Windows 路径和 POSIX 路径。
- 中途中断后从最后有效 artifact 恢复。
- 单项失败/重试不阻断其他作品。
- 下载/ASR/LLM 槽位限制，FunASR 默认只初始化一次。
- transcript 双重完整性检查通过前不删除媒体。
- 图文为 unsupported，不能让总作业显示完成或 100%。
- 同一 item 始终映射为一条 Rich 进度行。
- 双 ETA、样本不足的 `estimating` 和枚举中 provisional。
- episodes 必需字段、稳定文件名和原子覆盖。
- Skill fingerprint 跳过、partial/coverage metadata。
- episodes + skill 同时启用时不重复 ASR/LLM。
- 无 Playwright、无 Chromium、无登录、登录过期时的可操作错误。

仓库级测试命令为：

```text
python -m pytest -q
```

开发者应在已安装项目依赖的 Python 环境中运行；本机环境选择不写入仓库文档。

当前功能分支 `origin/main@5cda109` 的实测基线为 `110 passed, 1 failed`；本地 `main`（另含 26 个不进入本分支的提交）曾实测为 `182 passed, 1 failed`。两者唯一失败都是 Windows 对 POSIX `chmod 0600` 的断言。v0.4 会把该测试改为跨平台断言：POSIX 验证 `0600`，Windows 明确跳过仅适用于 POSIX mode bits 的断言，同时继续测试凭据内容和默认存储位置；不得将其误报为本功能回归。

发布前还要执行 CLI help、dry-run、最小真实账号冒烟测试、中断恢复、临时媒体清理、diff 审查和敏感信息扫描。真实账号测试只在本地凭据下运行，不进入自动测试或提交。

## 13. 实施阶段与提交边界

1. **公共契约**：Source models、PlatformRegistry、OutputRegistry 和兼容映射。
2. **Bilibili 迁移**：用统一接口跑通现有 Skill/RAG 路径，保证旧 CLI 不回归。
3. **输出目标**：episodes、Skill fingerprint、组合输出与 partial metadata。
4. **Douyin source**：session、resolver、enumerator、download 和错误分类。
5. **可恢复引擎**：artifact store、状态机、分阶段队列、重试、supervisor 和清理。
6. **可观测性**：Rich Live、阶段进度和双 ETA。
7. **发布准备**：跨平台测试修正、文档、依赖、CLI 帮助和本地冒烟检查。

每阶段独立测试和提交，不把 Scout 代码、用户数据或本地 `main` 的会议功能提交混入分支。

## 14. Scout 原型的取舍

可抽取设计思想并用项目接口重写：

- `session.py` 的单 profile、过期标记、排他锁和死 PID 恢复。
- `douyin_scan.py account` 的 API 响应拦截、滚动触发、分页、去重和作品类型映射。
- 常驻转写 worker 所证明的“模型只加载一次、ASR 串行化”约束。
- supervisor、固定行进度和 ETA 的用户体验目标。
- RapidOCR bridge 对未来 `GalleryOcrProcessor` 的输入/输出约定。

必须重写或舍弃：

- Scout API、数据库、tenant/favorite/ingest 依赖。
- PowerShell supervisor/monitor/ETA。
- `mcporter` 和 Node 运行时调用。
- 合并 clean + summary 的 Scout prompt；必须复用本项目独立 clean/model 阶段。
- 按输出 Markdown 数量判断整批完成。
- 硬编码 Windows 路径、私有 Python 环境、会话目录和任何敏感配置。

## 15. 完成定义

满足以下条件才可宣称本功能完成：

- Bilibili 和 Douyin 都通过同一平台注册与 manager 入口工作。
- 抖音分享链接可解析并全量/明确不完整地枚举可见作品，去重并可增量恢复。
- 默认三阶段并发为 3/1/3、活跃作品上限 3，ASR 模型只加载一次。
- 每个视频能独立生成 episode；启用 Skill 时可从同一批中间产物聚合生成。
- 单项失败不终止整批，重启不会重复有效阶段。
- 临时媒体只在 transcript 双重验证后删除。
- 图文明确 unsupported，coverage 和进度不伪装为全部完成。
- Rich Live 固定行显示真实进度、Active x/3、汇总计数和双 ETA。
- 新旧测试通过；已知 Windows 权限测试被正确跨平台化，无新增回归。
- README 足以让陌生用户安装浏览器、登录、运行、恢复和理解隐私/清理行为。
- 分支 diff 不包含 Cookie、profile、媒体、用户结果、模型、本机绝对路径或 Scout 私有代码。
