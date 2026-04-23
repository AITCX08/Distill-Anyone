"""
audio_download.py 单元测试

覆盖：generate_cookies_file 函数
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.crawl.audio_download import generate_cookies_file


def make_credential(sessdata="test_sessdata", bili_jct="test_bili_jct"):
    cred = MagicMock()
    cred.sessdata = sessdata
    cred.bili_jct = bili_jct
    return cred


class TestGenerateCookiesFile:
    def test_generates_netscape_header(self, tmp_path):
        out = tmp_path / "cookies.txt"
        result = generate_cookies_file(make_credential(), output_path=out)
        content = result.read_text(encoding="utf-8")
        assert content.startswith("# Netscape HTTP Cookie File")

    def test_contains_sessdata_and_bili_jct(self, tmp_path):
        out = tmp_path / "cookies.txt"
        generate_cookies_file(make_credential(sessdata="AAA", bili_jct="BBB"), output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "SESSDATA\tAAA" in content
        assert "bili_jct\tBBB" in content

    def test_includes_buvid3_when_provided(self, tmp_path):
        out = tmp_path / "cookies.txt"
        generate_cookies_file(make_credential(), buvid3="my_buvid3", output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "buvid3\tmy_buvid3" in content

    def test_excludes_buvid3_when_empty(self, tmp_path):
        out = tmp_path / "cookies.txt"
        generate_cookies_file(make_credential(), buvid3="", output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "buvid3" not in content

    def test_returns_output_path(self, tmp_path):
        out = tmp_path / "cookies.txt"
        result = generate_cookies_file(make_credential(), output_path=out)
        assert result == out

    def test_uses_temp_file_when_no_path(self):
        cred = make_credential()
        result = generate_cookies_file(cred)
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "SESSDATA" in content
        # cleanup
        result.unlink(missing_ok=True)

    def test_cookie_format_has_correct_columns(self, tmp_path):
        """Each cookie line should have 7 tab-separated fields."""
        out = tmp_path / "cookies.txt"
        generate_cookies_file(make_credential(), buvid3="b", output_path=out)
        lines = out.read_text(encoding="utf-8").strip().split("\n")
        cookie_lines = [l for l in lines if not l.startswith("#")]
        for line in cookie_lines:
            fields = line.split("\t")
            assert len(fields) == 7, f"Expected 7 fields, got {len(fields)}: {line}"

    def test_domain_is_bilibili(self, tmp_path):
        out = tmp_path / "cookies.txt"
        generate_cookies_file(make_credential(), output_path=out)
        lines = out.read_text(encoding="utf-8").strip().split("\n")
        cookie_lines = [l for l in lines if not l.startswith("#")]
        for line in cookie_lines:
            assert line.startswith(".bilibili.com")
