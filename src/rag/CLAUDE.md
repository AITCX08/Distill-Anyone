[← 返回 Distill-Anyone](../../CLAUDE.md) > **src/rag**

# src/rag -- RAG 知识块输出

## 模块职责

- 将 `data/cleaned/{source_id}.json` 与对应 `data/knowledge/{source_id}.json` 转换为 `data/rag_chunks/{source_id}.json`
- 输出稳定的 chunk schema，供后续 embedding / 检索系统直接消费
- 当前不负责向量化，也不依赖数据库

## 入口

| 入口 | 用途 |
|---|---|
| `build_chunks(cleaned_doc, knowledge, target_size=1000, overlap=100)` | 构建标准 chunks dict |

## 约束

- 优先按 `cleaned.topics` 切块
- topic 超长时按字符数二次切分
- `summary` 优先复用 `knowledge.summary`
- `keywords` 优先复用 `knowledge.key_concepts`
- `char_range` 尽量从 `full_text` 精确定位，失败时标记 `range_inferred=true`
