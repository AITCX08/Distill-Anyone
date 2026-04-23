[← 返回 Distill-Anyone](../../CLAUDE.md) > **src/crawl**

# src/crawl -- 阶段 1：数据采集

## 变更记录 (Changelog)

| 日期 | 变更 |
|---|---|
| 2026-04-21 | 初始化模块级 CLAUDE.md（架构师扫描补齐） |

---

## 模块职责

阶段 1 负责把一个 UP 主的视频元信息和对应音频从 B 站搬到本地：

- **认证**：三级策略获取 `Credential`（.env → 缓存 → 扫码登录），并生成 yt-dlp 使用的 `cookies.txt`。
- **视频列表**：分页、带 412 风控重试地抓取 UP 主的视频列表，与本地已有列表做 diff 合并。
- **音频下载**：调用 `yt-dlp` 提取音频流，落盘为 WAV，支持断点续传和完整性校验。
- **字幕获取（备用）**：`subtitle.py` 能从 B 站官方 CC 字幕获取转写结果，**但主流程目前未调用**。

上游：无（流水线起点）
下游：`data/video_list.json`、`data/audio/{bvid}.wav`、`data/.credentials.json`

---

## 入口与启动

| 入口 | 所在文件 | 用途 |
|---|---|---|
| `get_credential(config) -> (Credential, buvid3)` | `auth.py` | **唯一凭据入口**，三级策略自动回退 |
| `run_qrcode_login() -> (Credential, buvid3)` | `auth.py` | `python main.py login` 背后的扫码函数 |
| `save_credential(credential, buvid3, cache_path)` | `auth.py` | 写入 `data/.credentials.json`（权限 `0o600`） |
| `run_crawl(uid, credential, output_path, ...) -> list[dict]` | `video_list.py` | `python main.py crawl` 阶段 1-a 的同步入口 |
| `fetch_user_videos(uid, credential, existing_bvids, max_candidates)` | `video_list.py` | 异步获取分页视频列表 |
| `download_audio(bvid, output_dir, ...) -> Optional[Path]` | `audio_download.py` | 单视频音频下载（yt-dlp subprocess） |
| `batch_download(videos, output_dir, ...) -> list[Path]` | `audio_download.py` | 批量下载（主流程里已被 `main.py::crawl` 的 inline 循环替代） |
| `check_audio_completeness(audio_path, expected_duration_str)` | `audio_download.py` | 断点续传的健康检查函数 |
| `generate_cookies_file(credential, buvid3, output_path)` | `audio_download.py` | 生成 Netscape 格式 cookies.txt 供 yt-dlp 使用 |
| `fetch_subtitle(bvid, credential)` | `subtitle.py` | **备用**：从 B 站抓官方 CC 字幕（主流程未使用） |

---

## 对外接口（下游消费点）

| 产出物 | 路径 | 消费方 |
|---|---|---|
| 凭据缓存 JSON | `data/.credentials.json` | `auth.py::load_cached_credential` |
| Cookies 文件（临时） | `/tmp/bilibili_cookies_*.txt` | `yt-dlp` subprocess |
| 视频列表 JSON | `data/video_list.json` | `main.py::crawl/asr`、`asr/funasr_engine.py::save_transcript`（读 metadata） |
| 音频 WAV | `data/audio/{bvid}.wav` | `asr/funasr_engine.py::FunASREngine.transcribe` |

`data/video_list.json` 的 schema（来自 `fetch_user_videos`）：

```python
{
    "bvid": str,
    "title": str,
    "duration": str,      # "MM:SS" 或 "HH:MM:SS"
    "pubdate": int,       # Unix 时间戳
    "description": str,
    "view_count": int,
    "comment_count": int,
    "aid": int,
}
```

`data/.credentials.json` 的 schema（来自 `save_credential`）：

```python
{
    "sessdata": str, "bili_jct": str,
    "dedeuserid": str, "buvid3": str, "ac_time_value": str,
    "saved_at": str,  # ISO-8601
}
```

修改任一字段前，先查：谁在读？（参考根级 CLAUDE.md 的「关键数据契约」表）

---

## 关键依赖与配置

- `bilibili-api-python`：`user.User.get_videos`、`login_v2.QrCodeLogin`、`Credential`
- `yt-dlp`：通过 `subprocess.run` 调用，**不是 Python 导入**（需 PATH 中可执行）
- `aiohttp`：仅 `subtitle.py` 用（下载字幕文件）
- 所有 `bilibili_api` 导入均为**函数内延迟导入**，根级规范硬规则 #4

配置相关字段（`src/config.py::BilibiliConfig`）：`sessdata` / `bili_jct` / `buvid3`，均通过 `.env` 中 `BILIBILI_*` 注入。

---

## 数据模型

本模块不定义 dataclass，所有交换都是 `dict` / `tuple`。`fetch_user_videos` 返回的 dict 结构即为 `data/video_list.json` 的 schema。

---

## 常见修改模式

### 增加视频元信息字段（例如 UP 主粉丝数）

1. 在 `video_list.py::fetch_user_videos` 的字典构造里追加 key。
2. 下游 `asr/funasr_engine.py::save_transcript` 若要写入 `metadata`，同步在那里 `video_meta.get("new_field", default)`。
3. 更新 DEVELOPMENT.md 第 2 节的 schema 表。

### 增加新的认证策略（如手机号登录）

1. 在 `auth.py` 新增 `run_password_login()`（保持 `tuple[Credential, buvid3]` 返回签名）。
2. 在 `get_credential()` 的三级回退末尾插入第 4 级，**不要**打破 `.env > 缓存 > 扫码` 的优先级。
3. 保持 `save_credential()` 的调用方，让所有策略都复用同一份缓存格式。

### 替换音频下载工具（例如从 yt-dlp 换成 bilili）

1. 改 `audio_download.py::download_audio` 的 `cmd` 构造。
2. **保持返回签名**：成功返回 `Path`，失败返回 `None`。
3. 确认新工具支持 `--cookies` 或等价认证方式，避免付费视频只拿到试看片段。
4. 跑 `check_audio_completeness` 验证时长偏差是否仍在 30 秒容差内。

### 启用 subtitle.py（跳过 ASR）

1. 在 `main.py::crawl` 或 `asr` 加入「先尝试 `fetch_subtitle`，失败降级到 yt-dlp 下载 + ASR」逻辑。
2. `save_subtitle` 产出的 JSON 格式已与 `asr/funasr_engine.py::save_transcript` 兼容（都写 `data/transcripts/{bvid}.json`，字段 `full_text` + `segments`）。
3. 注意 `source` 字段区分：`"bilibili_cc_subtitle"` vs `"funasr"`，下游 `clean/text_processor.py` 可据此走不同清洗分支。

---

## 反模式（不要做）

- **不要**在模块顶部 `import yt_dlp` / `from bilibili_api import ...` 作为业务逻辑的一部分；SDK 导入放函数内，模块顶部只 import `Credential` 等类型。
- **不要**把 `SESSDATA` 之类的 Cookie 硬编码进代码或日志。`auth.py` 已经显式 `chmod 0o600`，不要削弱。
- **不要**在 `fetch_user_videos` 里把 `existing_bvids` 的判断换成 O(n²) 列表查找，保持 `set`。
- **不要**直接 `subprocess.run(["yt-dlp", ...])` 而不传 `cookies_file`；B 站风控对匿名调用越来越严格。
- **不要**删除 412 重试的 `await asyncio.sleep(wait)`，B 站会升级到临时封禁。
- **不要**改 `check_audio_completeness` 的容差（30s）而不更新 DEVELOPMENT.md；它和 `check_transcript_integrity`（60s）是配套的。

---

## 测试与质量

- `tests/test_auth.py`：覆盖 `save_credential` / `load_cached_credential` / `get_credential` 三级策略（全部用 mock 隔离 `bilibili_api`）。
- `tests/test_audio_download.py`：覆盖 `generate_cookies_file`（Netscape 格式、7 列校验、tmpfile 行为）。
- **未覆盖**：`fetch_user_videos` 的 412 重试、`download_audio` 的 subprocess 分支、`check_audio_completeness` 边界。

跑测试：`pytest tests/test_auth.py tests/test_audio_download.py -v`

---

## FAQ

**Q1：扫码登录后 `buvid3` 拿不到怎么办？**
A：不影响 SESSDATA / bili_jct 的有效性，但部分视频（特别是 4K / 大会员内容）在下载时会走 web anonymous 流，容易触发清晰度降级。解决：浏览器登录 B 站，复制 `buvid3` Cookie 到 `.env` 的 `BILIBILI_BUVID3`。

**Q2：`check_audio_completeness` 说"时长不足"，但视频本身是对的？**
A：检查 `video_list.json` 中的 `duration` 字段是否是 "MM:SS" 或 "HH:MM:SS"。空字符串时会走"无法获取预期时长，跳过校验"分支，直接判为 complete。

**Q3：为什么 `batch_download` 有但 `main.py` 没用？**
A：`main.py::crawl` 实现了更复杂的下载循环（配额控制 + 失败不计入配额 + 强制重下不完整音频），`batch_download` 保留作为简化 API 给脚本或测试用。

**Q4：412 重试 3 次还失败？**
A：B 站风控升级时需要更长等待。手动 `python main.py login` 重新扫码刷新 Credential，或等 30 分钟再跑。短期内不要再改重试次数硬编码。

---

## 相关文件清单

| 文件 | 用途 |
|---|---|
| `src/crawl/__init__.py` | 模块标记 |
| `src/crawl/auth.py` | 认证（三级策略 + 扫码） |
| `src/crawl/video_list.py` | 视频列表抓取（async） |
| `src/crawl/audio_download.py` | 音频下载（yt-dlp subprocess） |
| `src/crawl/subtitle.py` | 官方 CC 字幕（备用，未入主流程） |
| `.claude/plan/bilibili-qrcode-auth.md` | 扫码登录功能的原始设计 |
| `tests/test_auth.py` | auth.py 单元测试 |
| `tests/test_audio_download.py` | audio_download.py 单元测试 |
