[← 返回 Distill-Anyone](../../CLAUDE.md) > **src/clean**

# src/clean -- 阶段 3：文本清洗 + LLM 客户端工厂

## 变更记录 (Changelog)

| 日期 | 变更 |
|---|---|
| 2026-04-21 | 初始化模块级 CLAUDE.md（架构师扫描补齐） |
| 2026-04-21 | `segment_by_topic` 复用 `_safe_json_loads` 5 轮修复；修复 LLM 输出裸换行/控制字符导致的 "Expecting ',' delimiter" 降级问题 |

---

## 模块职责

阶段 3 把 ASR 的原始转写加工成可供知识提取的结构化文档，同时**承担整个项目的 LLM 客户端工厂职责**：

- 规则清洗：正则去口语填充词（嗯/啊/那个…）、合并过短片段、压缩重复标点。
- LLM 主题切分：把 `full_text` 发给 LLM，让它按主题拆成若干段（降级为「每段落一节」的朴素切分）。
- **LLM 客户端抽象**：`LLMClient` Protocol + `ClaudeLLMClient` + `OpenAILLMClient`（后者复用于 OpenAI / Qwen / DeepSeek / Ollama 四家兼容协议的供应商）。
- `create_llm_client(provider, config)` 工厂函数是**全项目**构造 LLM 客户端的唯一入口，`src/model/` 和 `src/reader/` 都通过它拿 client。

上游：`data/transcripts/{bvid}.json`
下游：`data/cleaned/{bvid}.json`（被 `src/model/knowledge_extractor.py` 消费）

---

## 入口与启动

| 入口 | 用途 |
|---|---|
| `TextProcessor(llm_client=None)` | 处理器构造；`None` 则走纯规则清洗 |
| `TextProcessor.process_transcript(transcript_data) -> dict` | 主流程入口：去填充词 → 合并短段 → LLM 主题切分 → 组装 |
| `TextProcessor.remove_filler_words(text)` | 正则清洗 |
| `TextProcessor.merge_short_segments(segments, min_length=10)` | 合并 |
| `TextProcessor.segment_by_topic(full_text, video_title)` | 主题切分（LLM 或降级） |
| `create_llm_client(provider, config) -> Optional[LLMClient]` | **工厂：全项目唯一构造点** |
| `ClaudeLLMClient(api_key, model)` | Anthropic 原生 SDK |
| `OpenAILLMClient(api_key, model, base_url)` | OpenAI / Qwen / DeepSeek / Ollama 通用 |
| `save_cleaned(cleaned_doc, output_dir) -> Path` | 序列化落盘 |
| `load_cleaned(input_path) -> dict` | 读 JSON |
| `check_cleaned_integrity(cleaned_path)` | 完整性校验 |

---

## 对外接口（下游消费点）

`data/cleaned/{bvid}.json` 的 schema（来自 `process_transcript`）：

```python
{
    "bvid": str,
    "title": str,
    "source": str,             # 透传自 transcript
    "full_text": str,          # 去填充词后的全文
    "topics": [                # LLM 主题切分结果
        {
            "id": f"{bvid}_topic_000",
            "title": str,
            "content": str,
            "tags": list[str],
        },
        ...
    ],
    "segments": [              # 清洗后的片段（保留时间戳）
        {"id": ..., "text": ..., "start": ..., "end": ..., "confidence": ...},
        ...
    ],
    "metadata": dict,          # 透传自 transcript
}
```

**消费方**：
- `model/knowledge_extractor.py::extract_from_video` 主要读 `bvid / title / full_text`（截断到前 10000 字）。
- `reader/document_reader.py` 产出的 cleaned JSON 与此 schema 完全一致（复用同一下游）。

---

## LLM 客户端协议

```python
class LLMClient(Protocol):
    def chat(self, prompt: str, max_tokens: int = 4096) -> str: ...
```

`create_llm_client` 的供应商映射（**新增 OpenAI 兼容供应商时只改这里**）：

```python
provider_map = {
    "openai":   (config.openai.api_key,   config.openai.base_url,   config.openai.model,   "OPENAI_API_KEY"),
    "qwen":     (config.qwen.api_key,     config.qwen.base_url,     config.qwen.model,     "QWEN_API_KEY"),
    "deepseek": (config.deepseek.api_key, config.deepseek.base_url, config.deepseek.model, "DEEPSEEK_API_KEY"),
    "ollama":   ("ollama",                config.ollama.base_url,   config.ollama.model,   None),  # 无需 key
}
# 默认 "claude" 走 ClaudeLLMClient
```

---

## 关键依赖与配置

- `anthropic`（仅 Claude 路径）、`openai`（其他四家都用）
- 均为**函数内延迟导入**（根级硬规则 #4）
- 配置字段：`config.anthropic / openai / qwen / deepseek / ollama`，见 `src/config.py`

---

## Prompt 位置（硬规则）

- **唯一实际使用的 Prompt**：`TOPIC_SEGMENT_PROMPT` 在 `text_processor.py` 底部（行 332+）。
- `prompts/topic_segment.txt` 只是只读参考，**修改它不会改变运行时行为**。
- 改 Prompt 时 JSON schema 注释必须保留（LLM 很敏感，删掉 schema 示例会让输出格式漂移）。

---

## 常见修改模式

### 新增一个 OpenAI 兼容的 LLM 供应商（例如 Moonshot / ZhipuAI）

1. `src/config.py` 加 `MoonshotConfig`（api_key / base_url / model）。
2. `src/config.py::LLM_PROVIDERS` tuple 里追加 `"moonshot"`。
3. `src/config.py::load_config()` 里从 `.env` 读 `MOONSHOT_*`。
4. `create_llm_client` 的 `provider_map` 里加一行。**不要**新写 `MoonshotLLMClient`，复用 `OpenAILLMClient`（根级硬规则 #5）。
5. `config.example.env` 追加示例变量。

### 调整规则清洗（例如保留某些"啊"字）

1. 改 `FILLER_WORDS_PATTERN` 的正则。
2. 注意前后 lookaround：保证只在中文之间匹配，避免误伤 "啊哈" 这种完整词。
3. 跑小样本 `python main.py clean --llm ollama` 验证。

### 替换主题切分为向量聚类（不依赖 LLM）

1. 新加一个 `segment_by_embedding(full_text)` 方法。
2. `process_transcript` 里加分支：`if self.llm_client: LLM else: embedding`。
3. 确保返回 list[dict]，keys 仍是 `title / content / tags`（下游模板依赖）。

### LLM 返回非 JSON 或带 markdown 围栏

`segment_by_topic` 先用 `re.search(r"\[.*\]", content, re.DOTALL)` 提取数组，再交给 `src/model/knowledge_extractor.py::_safe_json_loads` 做 5 轮修复（控制字符 / 裸换行 / 尾随逗号 / `...` 占位 / 尾部截断到 `}` 或 `]`）。解析结果非 `list` 时走降级并打印类型信息。

若未来出现前 5 轮都覆盖不了的新抖动模式（例如 LLM 自造未转义 Unicode 转义序列），在 `_safe_json_loads` 里加第 6 轮，两个模块自动受益 —— 不要在 `segment_by_topic` 本地复制修复逻辑。

---

## 反模式（不要做）

- **不要**在模块顶部 `import anthropic` 或 `from openai import OpenAI`（根级硬规则 #4）。
- **不要**为新 LLM 供应商写新 Client 类，**除非**它不兼容 OpenAI Chat Completions 协议（根级硬规则 #5）。
- **不要**修改 `TOPIC_SEGMENT_PROMPT` 的 JSON schema 示例而不同步改 `segment_by_topic` 的解析逻辑（根级反模式）。
- **不要**在 `remove_filler_words` 里直接 `text.replace("嗯", "")`，中文词中间的"嗯"会被误删；保持现有正则的 lookaround 边界。
- **不要**把 `full_text[:8000]` 的截断去掉；长文本会触发 LLM context 溢出。若确实需要更长输入，分块后聚合而不是去截断。
- **不要**在 `create_llm_client` 抛异常；返回 `None` 让调用方降级到规则处理（参考 `main.py::clean`）。

---

## 测试与质量

- **已覆盖**（`tests/test_text_processor.py`）：`segment_by_topic` 的 LLM JSON 5 轮容错（含 E647 bug 回归：裸换行 / 尾随逗号 / 尾部垃圾 / 非数组返回 / 完全无法解析降级）+ `remove_filler_words` 基础行为。
- **未覆盖**：`check_cleaned_integrity` 各失败分支（DEVELOPMENT.md TODO）、`merge_short_segments` 边界合并逻辑、`process_transcript` 端到端。

---

## FAQ

**Q1：`provider="claude"` 但 `ANTHROPIC_API_KEY` 未设置，会怎样？**
A：`create_llm_client` 返回 `None`，`TextProcessor` 走纯规则清洗（每段落一节 topic）。下游 `model` 阶段会因缺 LLM 报错退出（知识提取必须有 LLM）。

**Q2：Qwen 和 DeepSeek 都用 `OpenAILLMClient`，它们的响应格式真一致吗？**
A：是的，都是 OpenAI Chat Completions 协议。唯一差异是 `max_tokens` 的最大值：DeepSeek-Reasoner 上限 8192，OpenAI 4o 上限 16384，Qwen3 上限 8192。代码里设的 4096（clean 阶段）和 12288（model 画像合成阶段）对所有供应商都安全。

**Q3：Ollama 本地模型的 `api_key` 传什么？**
A：传任意字符串（代码里写死 `"ollama"`）；Ollama 不校验 key，只要 `base_url` 正确即可。

**Q4：主题切分结果只有一个 `"title": "全文"` 的兜底段？**
A：说明 LLM 解析失败或返回了非数组结构。查 console 日志：
  - `主题切分失败，使用简单分段: <err>` —— 5 轮修复都救不回来，通常是 LLM 完全没输出合法 JSON 数组（输出纯自然语言、markdown 表格、或中文全角括号冒充 `[]`）。
  - `主题切分返回非数组（<type>），使用简单分段` —— LLM 把 schema 弄反了，返回对象而非数组。
  - 自 2026-04-21 起，控制字符 / 裸换行 / 尾随逗号 / `...` 占位 / 尾部截断等常见抖动**都会被自动修复**，无需换模型。仍然失败时才换更稳健的 LLM（Claude / DeepSeek）重跑。

---

## 相关文件清单

| 文件 | 用途 |
|---|---|
| `src/clean/__init__.py` | 模块标记 |
| `src/clean/text_processor.py` | 处理器 + LLM 客户端 + 工厂 + Prompt |
| `prompts/topic_segment.txt` | **只读参考**（非运行时 Prompt） |
| `prompts/clean_transcript.txt` | **只读参考**（早期规划，当前未被调用） |
| `main.py::clean()` | CLI 命令调用处 |
