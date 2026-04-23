"""RAG 知识块构建。"""

from dataclasses import asdict, is_dataclass
from typing import Any


def _knowledge_value(knowledge: Any, key: str, default):
    if knowledge is None:
        return default
    if is_dataclass(knowledge):
        return getattr(knowledge, key, default)
    if isinstance(knowledge, dict):
        return knowledge.get(key, default)
    return getattr(knowledge, key, default)


def _infer_source_type(source_id: str, metadata: dict) -> str:
    source_type = metadata.get("source_type")
    if source_type:
        return source_type
    if source_id.startswith("BV"):
        return "video"
    if source_id.startswith("BOOK_") and "_ch" in source_id:
        return "book_chapter"
    return "document"


def _fallback_summary(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    for sep in ("。", "！", "？", "\n"):
        idx = text.find(sep)
        if idx != -1:
            return text[:idx + 1].strip()
    return text[:120].strip()


def _split_text(text: str, target_size: int, overlap: int) -> list[tuple[str, int, int]]:
    if len(text) <= target_size:
        return [(text, 0, len(text))]

    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = min(start + target_size, text_length)
        chunks.append((text[start:end], start, end))
        if end >= text_length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_chunks(
    cleaned_doc: dict,
    knowledge,
    target_size: int = 1000,
    overlap: int = 100,
) -> dict:
    """按 topic 优先策略构建 RAG 友好知识块。"""
    source_id = cleaned_doc.get("bvid", "")
    metadata = cleaned_doc.get("metadata", {})
    full_text = cleaned_doc.get("full_text", "")
    topics = cleaned_doc.get("topics", []) or [{
        "id": f"{source_id}_topic_000",
        "title": cleaned_doc.get("title", ""),
        "content": full_text,
        "tags": [],
    }]

    knowledge_summary = _knowledge_value(knowledge, "summary", "")
    knowledge_keywords = _knowledge_value(knowledge, "key_concepts", [])
    source_type = _infer_source_type(source_id, metadata)
    chunk_doc = {
        "schema_version": "1.0",
        "source_id": source_id,
        "source_type": source_type,
        "source_title": cleaned_doc.get("title", ""),
        "parent_id": metadata.get("parent_book_id"),
        "chunks": [],
    }

    search_pos = 0
    chunk_index = 0
    for topic in topics:
        topic_text = topic.get("content", "").strip()
        if not topic_text:
            continue

        topic_id = topic.get("id")
        topic_title = topic.get("title", "")
        topic_tags = topic.get("tags", [])
        base_summary = knowledge_summary or _fallback_summary(topic_text)
        base_keywords = list(knowledge_keywords[:8] or topic_tags[:8])

        topic_start = full_text.find(topic_text, search_pos)
        inferred_range = False
        if topic_start == -1:
            topic_start = full_text.find(topic_text)
        if topic_start == -1:
            topic_start = search_pos
            inferred_range = True
        topic_end = topic_start + len(topic_text)
        search_pos = max(search_pos, topic_end)

        for piece, relative_start, relative_end in _split_text(topic_text, target_size, overlap):
            chunk_start = topic_start + relative_start
            chunk_end = topic_start + relative_end
            chunk_doc["chunks"].append({
                "chunk_id": f"{source_id}_chunk_{chunk_index:02d}",
                "text": piece,
                "summary": base_summary,
                "keywords": base_keywords,
                "char_range": [chunk_start, chunk_end],
                "topic_id": topic_id,
                "metadata": {
                    "chapter_index": metadata.get("chapter_index"),
                    "chapter_title": metadata.get("chapter_title"),
                    "parent_book_id": metadata.get("parent_book_id"),
                    "source_file": metadata.get("file_path"),
                    "topic_title": topic_title,
                    "chunk_index": chunk_index,
                    "overlap": overlap,
                    "range_inferred": inferred_range,
                },
            })
            chunk_index += 1

    if is_dataclass(knowledge):
        asdict(knowledge)

    return chunk_doc
