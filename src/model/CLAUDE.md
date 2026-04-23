[← 返回 Distill-Anyone](../../CLAUDE.md) > **src/model**

# src/model -- 阶段 4：知识建模与博主画像合成

## 变更记录 (Changelog)

| 日期 | 变更 |
|---|---|
| 2026-04-21 | 初始化模块级 CLAUDE.md（架构师扫描补齐） |
| 2026-04-21 | `_safe_json_loads` Round 5 扩展为同时支持 `}` / `]` 截断，供 `src/clean/text_processor.py::segment_by_topic` 复用；返回类型从 `dict` 放宽为 `Any`（对象或数组） |

---

## 模块职责

阶段 4 是全项目最"重"的一步：

- **单视频知识提取**：对每个 `cleaned/{bvid}.json` 调用 LLM，提取 `summary / core_views / key_concepts / topics / arguments / mental_model_hints / decision_examples / expression_samples`。
- **博主画像合成**：把所有单视频知识摘要喂给 LLM（截断到前 50 个），让它合成 UP 主的「认知操作系统」—— `BloggerProfile`（25+ 字段，覆盖身份卡、心智模型、决策启发式、表达 DNA、价值观、边界、时间线、典型问答、原话引用）。
- **JSON 容错**：`_safe_json_loads` 做 5 轮修复，应对 LLM 输出的常见格式问题（控制字符、裸换行、尾随逗号、`...` 占位、截断到 `}` 或 `]`）；同时被 `src/clean/text_processor.py::segment_by_topic` 复用，两个模块共用同一套抖动恢复逻辑。
- **降级路径**：LLM 失败时 `_fallback_profile` 用规则生成基础画像（不推荐但可跑通）。

上游：`data/cleaned/{bvid}.json`
下游：`data/knowledge/{bvid}.json`（单视频）+ `data/knowledge/blogger_profile.json`（画像）

---

## 入口与启动

| 入口 | 用途 |
|---|---|
| `KnowledgeExtractor(llm_client)` | 构造；llm_client 必须非 None |
| `extract_from_video(cleaned_doc) -> VideoKnowledge` | 单视频知识提取 |
| `merge_knowledge(all_knowledge, up_name="", up_uid=0) -> BloggerProfile` | 画像合成（核心方法） |
| `_fallback_profile(all_knowledge, up_name, up_uid)` | LLM 失败时的规则降级 |
| `save_video_knowledge(knowledge, output_dir) -> Path` | 序列化 |
| `save_blogger_profile(profile, output_path) -> Path` | 序列化 |
| `load_video_knowledge(input_path) -> VideoKnowledge` | 反序列化（过滤未知字段，向后兼容） |
| `load_blogger_profile(input_path) -> BloggerProfile` | 反序列化（过滤未知字段） |
| `check_knowledge_integrity(knowledge_path)` | 完整性校验 |
| `_safe_json_loads(json_str)` | 5 轮 JSON 修复工具函数 |

---

## 数据契约（下游消费点）

### `data/knowledge/{bvid}.json`（单视频）

由 `asdict(VideoKnowledge)` 产出，消费方：`merge_knowledge` 自身（读取并聚合为 summaries）。

```python
{
    "bvid": str,
    "title": str,
    "summary": str,
    "core_views": list[str],
    "key_concepts": list[str],
    "topics": list[str],
    "arguments": [{"claim": str, "evidence": str}, ...],
    "mental_model_hints": [{"hint": str, "context": str}, ...],
    "decision_examples": [{"scenario": str, "reasoning": str, "conclusion": str}, ...],
    "expression_samples": list[str],
}
```

### `data/knowledge/blogger_profile.json`（画像 -- 终极契约）

由 `asdict(BloggerProfile)` 产出，消费方：`src/generate/skill_generator.py::SkillGenerator.generate` 及 `templates/skill.md.j2`。

**⚠️ 这是全项目最敏感的 schema**。新增字段需要同步改 5 处（根级规范硬规则 #9）：

1. `BloggerProfile` dataclass（本文件）
2. `PROFILE_SYNTHESIS_PROMPT` 底部的 JSON schema 示例
3. `merge_knowledge()` 里 `data.get()` 读取块
4. `src/generate/skill_generator.py::generate()` 的 `template.render()` 传参
5. `templates/skill.md.j2` 模板引用（**必须用 `{% if %}` 守护**，否则老画像渲染报错）

当前字段分组（25+ 字段）：

| 分组 | 字段 |
|---|---|
| 基础身份 | `name / uid / domain / self_intro / signature_quote / core_philosophy` |
| 身份卡 | `identity_who / identity_origin / identity_now` |
| 心智模型 | `mental_models: [{name, one_liner, evidence[3+], application, limitation}]` |
| 决策启发式 | `decision_heuristics: [{rule, scenario, case}]` |
| 表达 | `style / signature_phrases / expression_dna (7 维度)` |
| 价值观 | `values_pursued / values_rejected / inner_tensions` |
| 边界 | `anti_patterns / honest_boundaries / knowledge_boundary: {strong, weak}` |
| 时间线 | `timeline: [{time, event, impact}] / influenced_by / influenced_who` |
| 示例溯源 | `typical_qa_pairs / video_sources / key_quotes / research_date` |
| 旧兼容 | `core_views / values`（保留但不再是主渲染字段） |

---

## Prompt 位置（硬规则）

两个实际运行时使用的 Prompt 都在 `knowledge_extractor.py` 底部（行 436+）：

- `VIDEO_KNOWLEDGE_PROMPT`（行 436+）：单视频知识提取。
- `PROFILE_SYNTHESIS_PROMPT`（行 467+）：画像合成（硬性要求：每个心智模型 ≥3 条 evidence，≥2 条 inner_tensions，3 个 typical_qa_pairs）。

`prompts/extract_knowledge.txt` 只是只读参考，**修改它不影响运行时**。

---

## 关键依赖与配置

- `src/clean/text_processor.py::LLMClient` Protocol（通过 TYPE_CHECKING 引入）
- `_safe_json_loads` 依赖 `json + re`，无外部依赖
- 画像合成 `max_tokens=12288`（字段多，防止截断）；单视频提取 `max_tokens=4096`
- 输入截断：单视频 `full_text[:10000]`；画像合成 `summaries[:50]` 个视频（根级反模式：不要一股脑塞所有视频）

---

## _safe_json_loads 的 5 轮修复策略

调用顺序（每轮失败才进入下一轮）：

1. 直接 `json.loads`。
2. 修复控制字符（`\x00-\x1f`）+ 字符串值内的裸换行转义。
3. 移除尾随逗号（`,}` / `,]`）。
4. 把 `...` 占位符替换为合法值（`": ..."` → `": ""`、`, ...` → 空、`[...]` → `[]`）。
5. 截断到最后一个合法 `}` 或 `]` 处（应对 LLM 输出被 `max_tokens` 截断的情况，同时支持顶层对象和数组）。

若仍失败则抛出原始错误。

---

## 常见修改模式

### 新增 BloggerProfile 字段（例如 `podcast_recommendations: list[str]`）

1. `BloggerProfile` dataclass 加字段（带 `field(default_factory=list)` 之类的默认值）。
2. `PROFILE_SYNTHESIS_PROMPT` 的 JSON schema 示例里加 `"podcast_recommendations": [...]`。
3. `merge_knowledge` 里 `podcast_recommendations=data.get("podcast_recommendations", [])`。
4. `src/generate/skill_generator.py::generate` 的 `template.render(..., podcast_recommendations=profile.podcast_recommendations)`。
5. `templates/skill.md.j2` 加 `{% if podcast_recommendations %}...{% endif %}` 节块。

**检查清单**：跑一次 `python main.py generate`（若已有 `blogger_profile.json`），确认老画像不会因新字段缺失而报错。

### 调整 `evidence` 最少数量

Prompt 硬性要求当前是 `≥3 条`。改动时：
- 改 `PROFILE_SYNTHESIS_PROMPT` 的「硬性要求」第 1 条。
- 改 `templates/skill.md.j2` 里 `{% if m.evidence %}` 下的展示逻辑（当前直接 for loop，无数量断言）。
- 不要在 `merge_knowledge` 的 Python 侧强校验 evidence 数量（让 LLM 自己遵守，Python 保持宽容）。

### 加速单视频知识提取（串行 → 并发）

当前 `main.py::model_cmd` 串行循环 `extract_from_video`。改并发：

1. 用 `concurrent.futures.ThreadPoolExecutor`（LLM 调用是 IO-bound）。
2. 限制并发数（Claude/DeepSeek 都有 RPM 限制，建议 max_workers=3-5）。
3. 保留单个失败不中断整批的逻辑（根级硬规则 #8）。
4. 注意 `rich.console` 的线程安全：使用 `console.print` 本身安全，但别多个线程同时创建 `Progress`。

### 改 `_safe_json_loads` 的修复策略

新增一轮修复时，放在现有 5 轮之间时要考虑：
- 修复操作要幂等（多次应用结果相同）。
- 失败时不 raise，只 `pass` 进入下一轮。
- 最后兜底仍是 `return json.loads(json_str)` 抛原始错。

---

## 反模式（不要做）

- **不要**把 `summaries[:50]` 的截断去掉；全量喂进去会直接 token 爆炸（根级反模式）。
- **不要**改 `mental_models` schema 但忘了同步 `PROFILE_SYNTHESIS_PROMPT` 里的 JSON 样例（根级反模式）。
- **不要**在 `merge_knowledge` 里对 LLM 输出做严格 Python 侧校验；LLM 本来就不稳定，宽容读取（`data.get("field", default)`）才是对的。
- **不要**移除 `_safe_json_loads` 的任一轮修复 —— 每轮都是真实踩过的坑。
- **不要**把 `VideoKnowledge.expression_samples` 改为 `list[dict]` 而不同步 `merge_knowledge` 中的 `expr_sample = f"...{k.expression_samples[0][:80]}"`（会 TypeError）。
- **不要**在 `save_blogger_profile` 写入前过滤字段 —— `asdict(profile)` 的完整输出是契约，缺字段会让 `load_blogger_profile` 在老 JSON 上炸。

---

## 测试与质量

- **已覆盖**（`tests/test_knowledge_extractor.py`，50 用例）：
  - `_safe_json_loads` 5 轮修复 + 数组顶层路径 + 混合错误 + Unicode/emoji/大输入边界 + 失败兜底
  - `VideoKnowledge / BloggerProfile` 完整 schema 保真 roundtrip
  - 老 JSON 缺字段自动填默认、未知字段自动剥离、`expression_dna` 部分子 dict 不会被 merge 等兼容陷阱
  - `check_knowledge_integrity` 各失败分支（含 `UnicodeDecodeError`）
  - `extract_from_video` / `merge_knowledge` 的 LLM JSON → dataclass 完整字段映射（mock LLM）
  - `_fallback_profile` 空输入 + top-N 截断边界（core_views=10 / topics=5 / concepts=10）
- **未覆盖**：单视频 `extract_from_video` 的失败路径重试、`save/load` 的跨平台路径隔离。

---

## FAQ

**Q1：`save_blogger_profile` 后 `blogger_profile.json` 里 `mental_models` 是空数组？**
A：LLM 没遵守 schema。查 console 是否有 `知识画像生成失败: ...`。常见原因：
  - `max_tokens=12288` 还是被截断（字段太多）→ 手动增大，或减少 `typical_qa_pairs` 要求。
  - LLM 输出了 ````json` 代码块但内容格式错误 → 看下 `_safe_json_loads` 是否走到第 5 轮都失败。
  - 换更强的 LLM（Claude Sonnet / DeepSeek-Reasoner）。

**Q2：改 Prompt 后老的 `data/knowledge/{bvid}.json` 要重跑吗？**
A：改 `VIDEO_KNOWLEDGE_PROMPT` → 是，删 `data/knowledge/` 后重跑 `model` 阶段；改 `PROFILE_SYNTHESIS_PROMPT` → 只需重跑画像合成部分（`main.py::model_cmd` 每次都会重新合成画像）。

**Q3：为什么 `load_blogger_profile` 要过滤 `valid_keys`？**
A：防止老 JSON 含已删除字段时 `BloggerProfile(**data)` 报 `unexpected keyword`。加字段不用改，删字段自动兼容。

**Q4：`_fallback_profile` 什么时候触发？**
A：LLM chat 抛异常（网络、rate limit、auth）或返回无法解析的 JSON。fallback 画像只有 `domain / core_views / knowledge_boundary.strong / video_sources`，质量很差，建议修好 LLM 重跑。

---

## 相关文件清单

| 文件 | 用途 |
|---|---|
| `src/model/__init__.py` | 模块标记 |
| `src/model/knowledge_extractor.py` | 所有 dataclass、提取器、Prompt、JSON 容错 |
| `prompts/extract_knowledge.txt` | **只读参考**（非运行时 Prompt） |
| `templates/skill.md.j2` | 消费 `BloggerProfile` 的模板（契约对端） |
| `main.py::model_cmd()` | CLI 命令调用处 |
