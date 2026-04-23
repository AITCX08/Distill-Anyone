"""
document_reader 章节级处理测试。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.reader.document_reader import book_to_chapter_cleaneds, split_into_chapters


class TestSplitIntoChapters:
    def test_uses_heading_matches_when_at_least_three(self):
        text = (
            "第一章 起点\n内容A\n\n"
            "第二章 方法\n内容B\n\n"
            "第三章 落地\n内容C"
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 3
        assert chapters[0]["chapter_title"] == "第一章"
        assert chapters[1]["chapter_title"] == "第二章"

    def test_falls_back_to_hard_split_when_headings_are_insufficient(self):
        text = "纯正文" * 4000
        chapters = split_into_chapters(text)
        assert len(chapters) >= 2
        assert chapters[0]["chapter_title"] == "第 1 部分"
        assert all(ch["text"] for ch in chapters)


class TestBookToChapterCleaneds:
    def test_builds_cleaned_docs_with_compatible_top_level_schema(self, tmp_path):
        file_path = tmp_path / "book.txt"
        file_path.write_text(
            "第一章 起点\n内容A\n\n第二章 方法\n内容B\n\n第三章 落地\n内容C",
            encoding="utf-8",
        )

        cleaned_docs = book_to_chapter_cleaneds(file_path, llm_client=None, doc_title="测试书")
        assert len(cleaned_docs) == 3

        first = cleaned_docs[0]
        assert set(first.keys()) == {
            "bvid", "title", "source", "full_text", "topics", "segments", "metadata",
        }
        assert first["bvid"].startswith("BOOK_book_")
        assert first["metadata"]["source_type"] == "book_chapter"
        assert first["metadata"]["chapter_index"] == 1
        assert first["metadata"]["chapter_title"] == "第一章"
        assert first["metadata"]["parent_book_id"].startswith("BOOK_book_")
        assert first["metadata"]["total_chapters"] == 3
        assert isinstance(first["metadata"]["char_range"], list)
