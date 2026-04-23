[← 返回 Distill-Anyone](../../CLAUDE.md) > **src/asr**

# src/asr -- 阶段 2：语音识别

## 变更记录 (Changelog)

| 日期 | 变更 |
|---|---|
| 2026-04-21 | 初始化模块级 CLAUDE.md（架构师扫描补齐） |
| 2026-04-23 | `main.py::asr` 新增 `--delete-audio/--keep-audio`（默认删）+ `--watch` 长跑模式 + `--watch-interval`；转写完整性校验通过后自动 `unlink` 音频释放磁盘；`crawl` 阶段把 `transcripts/` 完整的 BV 也算入「已处理」集合避免重复下载 |

---

## 模块职责

阶段 2 把阶段 1 下载的音频文件转写成带时间戳的中文文本：

- 封装 FunASR 的 `paraformer-zh`（ASR）+ `fsmn-vad`（VAD）+ `ct-punc`（标点恢复）三模型组合。
- **设备三级回退**：CUDA > MPS > CPU，自动探测；指定 `device=` 参数可强制。
- **CUDA/MPS OOM 重试**：推理失败先 `empty_cache`，再用 `batch_size_s=60` 缩小重试一次。
- 输出带句子级时间戳的 `TranscriptResult`，序列化为 `data/transcripts/{bvid}.json`。

上游：`data/audio/{bvid}.wav`
下游：`data/transcripts/{bvid}.json`（被 `src/clean/text_processor.py` 消费）

---

## 入口与启动

| 入口 | 用途 |
|---|---|
| `FunASREngine(model_name, vad_model, punc_model, device=None, model_dir=None)` | 引擎初始化；`device=None` 自动探测 |
| `FunASREngine.transcribe(audio_path, bvid) -> TranscriptResult` | 单文件转写（主流程使用） |
| `FunASREngine.transcribe_batch(audio_paths, bvids) -> list[TranscriptResult]` | 批量转写（带 rich 进度条） |
| `save_transcript(result, video_meta, output_dir) -> Path` | 合并视频元信息落盘 JSON |
| `load_transcript(input_path) -> dict` | 读 JSON（给下游 `clean` 用） |
| `check_transcript_integrity(transcript_path, audio_path=None, tolerance=60.0)` | 断点续传的健康检查 |

`main.py::asr` 的使用方式：遍历 `data/audio/BV*.*` → 对每个文件先 `check_transcript_integrity` → 不通过就调 `engine.transcribe()` → `save_transcript()`。

**边下边转写工作流**（v0.4 起，磁盘节省关键）：
- `main.py::_scan_pending_audios(config)` 抽出来给单次和 watch 模式共用
- `main.py::_process_pending_batch(..., delete_audio: bool)` 在 `save_transcript` 后**再做一次** `check_transcript_integrity`（双保险），通过才 `audio_file.unlink()`；失败保留音频供下次重试
- `asr --watch` 模式只加载一次 FunASR 引擎，循环 `_scan_pending_audios → _process_pending_batch → sleep(watch_interval)`，Ctrl+C 优雅退出
- 配套：`crawl` 启动时把 `data/transcripts/{bvid}.json` 完整的 BV 也算入「已处理」集合 `complete_bvids`，**避免被 ASR 删音频后又被重复下载**

---

## 对外接口（下游消费点）

`data/transcripts/{bvid}.json` 的 schema（来自 `save_transcript`）：

```python
{
    "bvid": str,
    "title": str,              # 来自 video_meta
    "source": "funasr",        # 或 "bilibili_cc_subtitle"（若走 subtitle.py）
    "model": str,              # 例如 "paraformer-zh"
    "full_text": str,          # 拼接好的完整文本
    "segments": [
        {
            "id": f"{bvid}_seg_0000",
            "text": str,
            "start": float,    # 秒
            "end": float,
            "confidence": float,
        },
        ...
    ],
    "metadata": {
        "pubdate": int, "duration": str, "view_count": int,
        "comment_count": int, "description": str,
    },
}
```

**消费方**：`clean/text_processor.py::TextProcessor.process_transcript` 读取 `bvid / title / source / segments / metadata`。

---

## 关键依赖与配置

- `funasr`（ModelScope 维护）+ `torch`
- 模型缓存：`data/.cache/modelscope/`（由 `AppConfig.model_cache_dir` 提供）
- 环境变量副作用：`MODELSCOPE_CACHE` / `MS_CACHE_HOME` / `PYTORCH_CUDA_ALLOC_CONF`

**延迟导入**：`torch` 和 `funasr` 只在 `FunASREngine.__init__` 内 import，首次调用前不会影响 CLI 启动速度。

配置字段（`src/config.py::FunASRConfig`）：
- `model` / `vad_model` / `punc_model`，对应 `.env` 中 `FUNASR_MODEL` / `FUNASR_VAD_MODEL` / `FUNASR_PUNC_MODEL`。

---

## 数据模型

```python
@dataclass
class TranscriptSegment:
    id: str = ""
    text: str = ""
    start: float = 0.0    # 秒
    end: float = 0.0
    confidence: float = 0.0

@dataclass
class TranscriptResult:
    bvid: str = ""
    audio_path: str = ""
    full_text: str = ""
    segments: list[TranscriptSegment] = []
    model_name: str = ""
    source: str = "funasr"
```

这两个 dataclass 只在进程内部流转；**真正的契约是 `save_transcript` 写出的 JSON schema**（见上）。改 dataclass 字段时不强制向外传播，但若影响 `save_transcript` 输出，必须同步下游消费者。

---

## 常见修改模式

### 换 ASR 模型（比如 Whisper / SenseVoice）

1. 新增 `src/asr/whisper_engine.py`，保持相同的 `.transcribe(audio_path, bvid) -> TranscriptResult` 接口。
2. 在 `config.py::FunASRConfig` 旁新增 `WhisperConfig`，`.env` 加 `ASR_BACKEND=whisper`。
3. `main.py::asr` 里加工厂选择逻辑；**不要**删 FunASREngine（Apple Silicon 用户默认跑它）。
4. 注意 `TranscriptResult.source` 必须标注来源，下游 `check_transcript_integrity` 的时长容差可能要调整。

### 调整 VAD 切片长度

位置：`FunASREngine.__init__` 里 `vad_kwargs={"max_single_segment_time": 60000}`（毫秒）。
- 调小会增加句子数但提升时间戳精度；
- 调大会减少句子数但单句可能过长，影响 `clean` 阶段的主题切分质量。

### 处理无 CUDA / MPS 环境的慢速问题

1. 不要改设备探测顺序（参见根级规范硬规则 #7）。
2. 可以通过环境变量 `ASR_DEVICE=cpu` 强制。
3. 若 CPU 太慢，降级方案是启用 `src/crawl/subtitle.py` 的官方 CC 字幕（跳过 ASR）。

### 增加转写结果字段（例如 speaker diarization）

1. 在 `TranscriptSegment` 加字段。
2. `transcribe()` 里写入。
3. `save_transcript()` 的 `asdict(seg)` 自动拾取，**但** `check_transcript_integrity` 需要明确加一条校验（否则旧 JSON 会误判）。
4. 更新 `clean/text_processor.py` 的消费逻辑（通常 `segments` 里新字段只要不破坏 `text/start/end` 就兼容）。

---

## 反模式（不要做）

- **不要**在模块顶部 `import torch` 或 `import funasr`（根级硬规则 #4）。
- **不要**在 `transcribe` 里吞掉 `RuntimeError` —— 只有 `out of memory` 才走 OOM 重试路径，其他错误应该让调用方决定（`main.py::asr` 已经 try/except 循环继续）。
- **不要**移除 `_free_gpu_cache` 调用；多视频连续转写时不释放会直接 OOM。
- **不要**改变设备探测的顺序（CUDA → MPS → CPU），其他模块和测试假设这个顺序。
- **不要**把 `sentence_timestamp=True` 关掉 —— 下游需要句子级时间戳做主题切分。
- **不要**用 `print` 输出进度（用 `rich.progress.Progress`，根级硬规则 #6）。

---

## 测试与质量

- **未覆盖**：本模块目前无单元测试。mock FunASR 成本较高（涉及模型加载和 torch 设备），建议用 integration 测试（小音频文件 + CPU）。
- **手动验证**：`python main.py asr` 跑 2-3 个视频，看 `data/transcripts/*.json` 里 `full_text` 是否完整、`segments` 末尾时间是否接近音频时长。

---

## FAQ

**Q1：MPS 设备报错 "MPSNDArray ... cannot be shared"？**
A：FunASR + PyTorch MPS 在某些 torch 版本下不稳定。解决：`ASR_DEVICE=cpu python main.py asr`。

**Q2：转写输出中英文混用时标点错乱？**
A：`ct-punc` 是中文标点恢复模型，对英文片段表现较差。短期接受；长期可以改 `punc_model` 换成多语言版本。

**Q3：音频明明 30 分钟，转写只有前 5 分钟？**
A：`check_transcript_integrity` 会检测这种情况并返回 `False`。确保调用侧没有无条件复用旧转写。若付费视频最初下载不完整、后补下载，需重跑 asr（主流程已自动处理）。

**Q4：`batch_size_s=300` 爆显存？**
A：`_generate_with_oom_retry` 会自动降到 60 重试。若仍然 OOM（例如 M1 8GB 显存），考虑 `ASR_DEVICE=cpu` 或减小 `vad_kwargs.max_single_segment_time`。

---

## 相关文件清单

| 文件 | 用途 |
|---|---|
| `src/asr/__init__.py` | 模块标记 |
| `src/asr/funasr_engine.py` | 引擎封装、dataclass、完整性校验 |
| `data/.cache/modelscope/` | 模型缓存（.gitignore） |
| `main.py::asr()` | CLI 命令调用处 |
