"""
rag.chunker 测试。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.model.knowledge_extractor import VideoKnowledge
from src.rag.chunker import build_chunks


class TestBuildChunks:
    def test_builds_one_chunk_per_topic_by_default(self):
        cleaned_doc = {
            "bvid": "BOOK_demo_123456_ch01",
            "title": "测试书 - 第一章",
            "full_text": "主题一内容。主题二内容。",
            "topics": [
                {"id": "t1", "title": "主题一", "content": "主题一内容。", "tags": ["框架"]},
                {"id": "t2", "title": "主题二", "content": "主题二内容。", "tags": ["案例"]},
            ],
            "metadata": {
                "source_type": "book_chapter",
                "chapter_index": 1,
                "chapter_title": "第一章",
                "parent_book_id": "BOOK_demo_123456",
                "file_path": "/tmp/demo.txt",
            },
        }
        knowledge = VideoKnowledge(
            bvid="BOOK_demo_123456_ch01",
            title="测试书 - 第一章",
            summary="章节摘要",
            key_concepts=["概念A", "概念B"],
        )

        chunk_doc = build_chunks(cleaned_doc, knowledge)
        assert chunk_doc["source_type"] == "book_chapter"
        assert chunk_doc["parent_id"] == "BOOK_demo_123456"
        assert len(chunk_doc["chunks"]) == 2
        assert chunk_doc["chunks"][0]["summary"] == "章节摘要"
        assert chunk_doc["chunks"][0]["keywords"] == ["概念A", "概念B"]

    def test_splits_long_topic_and_falls_back_without_knowledge(self):
        long_text = "A" * 2200
        cleaned_doc = {
            "bvid": "BV1demo",
            "title": "测试视频",
            "full_text": long_text,
            "topics": [
                {"id": "topic_0", "title": "全文", "content": long_text, "tags": ["长文"]},
            ],
            "metadata": {},
        }

        chunk_doc = build_chunks(cleaned_doc, knowledge=None, target_size=1000, overlap=100)
        assert chunk_doc["source_type"] == "video"
        assert len(chunk_doc["chunks"]) == 3
        assert chunk_doc["chunks"][0]["keywords"] == ["长文"]
        assert chunk_doc["chunks"][0]["char_range"][0] == 0
        assert chunk_doc["chunks"][1]["char_range"][0] == 900
