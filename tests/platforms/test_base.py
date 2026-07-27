from collections.abc import Callable
from typing import get_type_hints

from src.distillation.progress import TransferProgress
from src.platforms.base import PlatformAdapter


def test_platform_adapter_download_assets_progress_accepts_transfer_progress():
    annotation = get_type_hints(PlatformAdapter.download_assets)["progress"]

    assert annotation == Callable[[TransferProgress], None]
