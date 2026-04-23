[← 返回 Distill-Anyone](../../CLAUDE.md) > **src/generate**

# src/generate -- 阶段 5：SKILL.md 渲染

## 变更记录 (Changelog)

| 日期 | 变更 |
|---|---|
| 2026-04-21 | 初始化模块级 CLAUDE.md（架构师扫描补齐） |

---

## 模块职责

阶段 5 把 `BloggerProfile` 通过 Jinja2 模板渲染成最终的 SKILL.md 文件：

- 读 `data/knowledge/blogger_profile.json`。
- 加载 `templates/skill.md.j2`（trim_blocks + lstrip_blocks）。
- 渲染为 `output/{name}.skill.md`（对齐 [女娲.skill](https://github.com/alchaincyf/nuwa-skill) / [张雪峰.skill](https://github.com/alchaincyf/zhangxuefeng-skill) 格式）。

本模块是流水线终点，不产生 JSON。

---

## 入口与启动

| 入口 | 用途 |
|---|---|
| `SkillGenerator(template_dir="templates")` | 构造 Jinja2 Environment |
| `SkillGenerator.generate(profile) -> str` | 渲染为字符串（不落盘） |
| `SkillGenerator.save(content, output_path) -> Path` | 写入文件 |
| `SkillGenerator.generate_and_save(profile, output_path) -> Path` | 一步完成（主流程使用） |

---

## 对外接口

**输入**：`BloggerProfile` 实例（来自 `src/model/knowledge_extractor.py::load_blogger_profile`）。

**输出**：`output/{profile.name}.skill.md` 或 `output/skill.md`（name 为空时）。

---

## Jinja2 模板字段映射

`skill_generator.py::generate()` 里 `template.render()` 传入所有 `BloggerProfile` 字段（不做筛选，全字段透传）。模板里每一节都用 `{% if %}` 守护，确保老 JSON（缺字段）能降级渲染。

模板主要节块（见 `templates/skill.md.j2`）：

| 节 | 触发条件（Jinja2 守卫） | 来源字段 |
|---|---|---|
| YAML frontmatter | 无条件 | `name / video_count / mental_models / decision_heuristics / domain` |
| 文首金句 | `signature_quote or signature_phrases` | `signature_quote` / `signature_phrases[0]` |
| 核心理念 | `core_philosophy` | `core_philosophy` |
| 角色扮演规则 | 无条件（硬编码） | `name` |
| 回答工作流 | 无条件（硬编码） | - |
| 身份卡 | `identity_who or identity_origin or identity_now` | `identity_who / origin / now` |
| 核心心智模型 | `mental_models` | `mental_models[*].{name, one_liner, evidence, application, limitation}` |
| 决策启发式 | `decision_heuristics` | `decision_heuristics[*].{rule, scenario, case}` |
| 表达 DNA | `expression_dna` | 7 维度 + 旧结构兼容（opening_patterns / reasoning_connectors / emphasis_patterns / closing_patterns） |
| 时间线 | `timeline` | `timeline[*].{time, event, impact}` |
| 价值观与反模式 | `values_pursued or values_rejected or inner_tensions` | 三组 list |
| 智识谱系 | `influenced_by or influenced_who` | 两组 list |
| 效果示例 | 无条件（有 typical_qa_pairs 则展示，否则提示重跑） | `typical_qa_pairs[:3]` |
| 诚实边界 | 无条件 | `honest_boundaries / knowledge_boundary.weak / research_date` |
| 调研来源 | `video_sources` | `video_sources[:20]` |
| 关键引用 | `key_quotes` | `key_quotes` |
| 关于 | 无条件 | `self_intro / domain / style / signature_phrases` |

**元字段**（非 BloggerProfile）：`video_count = len(profile.video_sources)`，`generation_date = datetime.now()`。

---

## 关键依赖与配置

- `jinja2`（唯一运行时依赖）
- `FileSystemLoader` 默认从 `templates/` 目录加载
- `trim_blocks=True, lstrip_blocks=True`：控制 `{% %}` 块的空白处理，避免模板里每个块产生多余空行

---

## 常见修改模式

### 新增节块（例如「常见误解澄清」）

1. 先在 `src/model/knowledge_extractor.py::BloggerProfile` 加字段（见 `src/model/CLAUDE.md` 的 5 处同步清单）。
2. 确认 `skill_generator.py::generate()` 的 `template.render(...)` 里把新字段传进去。
3. 在 `skill.md.j2` 加：

```jinja2
{% if misconceptions %}
## 常见误解澄清

{% for m in misconceptions %}
- **误解**：{{ m.claim }}
  - **真相**：{{ m.truth }}
{% endfor %}

{% endif %}
```

4. **必须**用 `{% if %}` 守护（根级硬规则 #10）。
5. 手动跑一次 `python main.py generate` 用老 `blogger_profile.json`，确认不报错。

### 调整 YAML frontmatter（例如加 `tags`）

模板开头的 frontmatter 是给 nuwa-skill 风格 AI 助手读的元信息。改动时：
- `name` 字段是 Claude Code Skill 的唯一标识，不要改格式（必须 `<name>-perspective`）。
- `description` 尾部的「当用户提到…使用」部分决定 skill 激活条件，关键词要覆盖常见说法。

### 改模板路径（例如支持多个模板版本）

`SkillGenerator(template_dir=...)` 接受自定义目录。可做法：
- 传 `template_dir="templates/v2"` 切到新版模板。
- 但 `main.py::generate` 目前硬编码 `"templates"`，要改那里。
- 更好的做法：在 `AppConfig` 加 `template_name` 字段，由 `.env` 注入。

### 渲染失败调试

Jinja2 报 `UndefinedError: 'x' is undefined`：
1. 检查 `skill.md.j2` 里变量是否在 `{% if x %}` 下使用。
2. 检查 `generate()` 是否把该字段传入 `template.render()`。
3. 若是 dict 字段（如 `expression_dna`），用 `{% if expression_dna.xxx %}` 而不是 `{% if xxx %}`（Jinja2 对嵌套路径宽容，None.xxx 不炸但展示为空）。

---

## 反模式（不要做）

- **不要**在模板里加新节而不用 `{% if %}` 守护（根级硬规则 #10 + 反模式）。
- **不要**在 `generate()` 里对 `profile` 的字段做类型转换或处理；保持"纯渲染"，业务逻辑放 `knowledge_extractor.py`。
- **不要**把 `FileSystemLoader(template_dir)` 改成绝对路径硬编码；用 `template_dir` 参数。
- **不要**删掉"角色扮演规则"或"回答工作流"硬编码部分；这些是 nuwa-skill 风格的核心契约，影响 AI 激活后的行为。
- **不要**让模板同时使用 `core_philosophy` 和 `core_views` 作为主渲染字段 —— `core_views` 是旧兼容字段（根级硬规则 #9 的 Changelog）。

---

## 测试与质量

- **未覆盖**：本模块无单元测试。
- **建议补充**：
  - `generate()` 用一个 minimal `BloggerProfile`（空字段）渲染不报错
  - `generate()` 用 full `BloggerProfile` 渲染，验证所有节块都出现
  - 快照测试：跑一次存 golden file，后续改模板对比

---

## FAQ

**Q1：输出的 SKILL.md 有一大堆空行？**
A：检查 Jinja2 环境是否开了 `trim_blocks` 和 `lstrip_blocks`（当前已开）。若节块用 `{{ }}` 而非 `{% %}`，也会留空行 —— 把 `{% if %}` 块紧贴节标题上方。

**Q2：老 `blogger_profile.json`（只有 `core_views`，没有 `mental_models`）渲染后是什么样？**
A：
- 核心心智模型节消失（`{% if mental_models %}` 不触发）
- YAML frontmatter 的 `description` 里 `mental_models | length` 不会崩（Jinja2 对 None 的 filter 容错）但显示不美观 → 模板已改为 `{% if mental_models %}提炼 {{ mental_models | length }} 个...{% endif %}`
- 建议重跑 `python main.py model` 生成新格式画像

**Q3：想在 SKILL.md 文件名加日期怎么办？**
A：改 `main.py::generate`：`output_path = config.output_dir / f"{profile.name}_{datetime.now():%Y%m%d}.skill.md"`。`SkillGenerator` 自身不感知命名规则。

**Q4：`typical_qa_pairs` 多于 3 个会展示吗？**
A：不会。模板里 `{% for qa in typical_qa_pairs[:3] %}` 硬切。这是主动限制，避免 SKILL.md 过长降低 AI 助手首次加载性能。

---

## 相关文件清单

| 文件 | 用途 |
|---|---|
| `src/generate/__init__.py` | 模块标记 |
| `src/generate/skill_generator.py` | Jinja2 渲染入口 |
| `templates/skill.md.j2` | 模板（**契约的另一端**） |
| `examples/sample.skill.md` | 参考样例 |
| `main.py::generate()` | CLI 命令调用处 |
