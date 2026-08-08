from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import get_type_hints
from unittest.mock import ANY, Mock

import pytest

from src.platforms.bilibili.adapter import BilibiliAdapter, legacy_source_id
from src.distillation.progress import TransferProgress
from src.platforms.errors import PlatformDownloadError, TargetResolutionError
from src.platforms.models import ItemType, ResolvedTarget


def make_config():
    return SimpleNamespace(
        bilibili=SimpleNamespace(sessdata="session", bili_jct="csrf", buvid3="device"),
        credentials_cache=Path("credentials.json"),
    )


def make_adapter(**overrides):
    defaults = {
        "config": make_config(),
        "credential_provider": Mock(return_value=(SimpleNamespace(), "device")),
        "video_fetcher": Mock(return_value=[]),
        "download_fn": Mock(),
        "cookies_factory": Mock(),
    }
    defaults.update(overrides)
    return BilibiliAdapter(**defaults)


def test_bilibili_video_maps_to_source_item():
    adapter = make_adapter()

    item = adapter.map_video(
        {
            "bvid": "BV1abc",
            "title": "Test video",
            "duration": "01:30",
            "pubdate": 1_700_000_000,
            "description": "Description",
            "view_count": 12,
            "comment_count": 3,
            "aid": 99,
        },
        creator_id="42",
    )

    assert (item.platform, item.item_id, item.creator_id) == (
        "bilibili",
        "BV1abc",
        "42",
    )
    assert item.source_id == "bilibili_BV1abc"
    assert item.item_type is ItemType.VIDEO
    assert item.duration_seconds == 90
    assert item.statistics == {"views": 12, "comments": 3}
    assert item.raw_metadata["aid"] == 99


def test_legacy_source_id_qualifies_bvid():
    assert legacy_source_id("BV1abc") == "bilibili_BV1abc"
    assert legacy_source_id("bilibili_BV1abc") == "bilibili_BV1abc"


def test_bilibili_descriptor_declares_the_browser_backed_qr_login():
    assert BilibiliAdapter.descriptor.requires_browser is True


def test_resolve_accepts_space_url_and_rejects_video_url():
    adapter = make_adapter()

    target = adapter.resolve("https://space.bilibili.com/42")

    assert target == ResolvedTarget(
        platform="bilibili",
        creator_id="42",
        canonical_url="https://space.bilibili.com/42",
        original_target="https://space.bilibili.com/42",
    )
    with pytest.raises(TargetResolutionError):
        adapter.resolve("https://www.bilibili.com/video/BV1abc")


def test_iter_items_maps_fetcher_results_to_complete_page():
    fetcher = Mock(
        return_value=[
            {"bvid": "BV1", "title": "One", "duration": "00:10"},
            {"bvid": "BV2", "title": "Two", "duration": "00:20"},
        ]
    )
    adapter = make_adapter(video_fetcher=fetcher)
    creator = adapter.get_creator(
        ResolvedTarget("bilibili", "42", "https://space.bilibili.com/42", "input")
    )

    pages = list(adapter.iter_items(creator, checkpoint=None))

    assert len(pages) == 1
    assert [item.item_id for item in pages[0].items] == ["BV1", "BV2"]
    assert pages[0].checkpoint.complete is True
    assert pages[0].has_more is False
    fetcher.assert_called_once()


def test_download_assets_delegates_to_existing_audio_download(tmp_path):
    output = tmp_path / "BV1abc.wav"
    output.write_bytes(b"audio")
    download = Mock(return_value=output)
    cookies = Mock(return_value=tmp_path / "cookies.txt")
    progress = Mock()
    adapter = make_adapter(download_fn=download, cookies_factory=cookies)
    item = adapter.map_video(
        {"bvid": "BV1abc", "title": "Test", "duration": "00:01"},
        creator_id="42",
    )

    result = adapter.download_assets(item, tmp_path, progress=progress)

    assert result.audio_path == output
    download.assert_called_once_with(
        "BV1abc",
        tmp_path,
        audio_format="wav",
        cookies_file=cookies.return_value,
        progress_callback=ANY,
    )
    transfer = progress.call_args.args[0]
    assert isinstance(transfer, TransferProgress)
    assert (transfer.completed_bytes, transfer.total_bytes) == (5, 5)


def test_download_assets_progress_callback_accepts_transfer_progress():
    annotation = get_type_hints(BilibiliAdapter.download_assets)["progress"]
    assert annotation == Callable[[TransferProgress], None]


def test_download_assets_forwards_live_transfer_progress(tmp_path):
    output = tmp_path / "BV1abc.wav"
    output.write_bytes(b"audio")
    progress = Mock()

    def download(*args, progress_callback, **kwargs):
        progress_callback(3, 5, 1.5)
        return output

    adapter = make_adapter(
        download_fn=download,
        cookies_factory=Mock(return_value=tmp_path / "cookies.txt"),
    )
    item = adapter.map_video(
        {"bvid": "BV1abc", "title": "Test", "duration": "00:01"},
        creator_id="42",
    )

    adapter.download_assets(item, tmp_path, progress=progress)

    transfer = progress.call_args_list[0].args[0]
    assert isinstance(transfer, TransferProgress)
    assert transfer.source_id == item.source_id
    assert (transfer.completed_bytes, transfer.total_bytes) == (3, 5)
    assert transfer.bytes_per_second == 1.5


def test_download_failure_is_explicit(tmp_path):
    adapter = make_adapter(download_fn=Mock(return_value=None))
    item = adapter.map_video(
        {"bvid": "BV1abc", "title": "Test", "duration": "00:01"},
        creator_id="42",
    )

    with pytest.raises(PlatformDownloadError, match="BV1abc"):
        adapter.download_assets(item, tmp_path, progress=Mock())


def test_authenticate_persists_qr_credentials(tmp_path):
    credential = SimpleNamespace()
    login = Mock(return_value=(credential, "device-id"))
    saver = Mock()
    config = make_config()
    config.credentials_cache = tmp_path / "credentials.json"
    adapter = make_adapter(config=config, login_fn=login, credential_saver=saver)

    adapter.authenticate(headful=True)

    saver.assert_called_once_with(credential, "device-id", config.credentials_cache)


def test_auth_status_rejects_an_empty_credential_cache(tmp_path):
    config = make_config()
    config.bilibili = SimpleNamespace(sessdata="", bili_jct="", buvid3="")
    config.credentials_cache = tmp_path / "credentials.json"
    config.credentials_cache.write_text(
        '{"sessdata": "", "bili_jct": "", "buvid3": "device"}', encoding="utf-8"
    )

    assert make_adapter(config=config).auth_status().status == "missing"
