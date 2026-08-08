import time

from src.dashboard.bilibili_login import BilibiliLoginCoordinator


class FakeEvents:
    DONE = "done"
    SCAN = "scan"
    CONF = "confirm"
    TIMEOUT = "timeout"


class FakePicture:
    content = b"fake-png"


class SuccessfulQrLogin:
    async def generate_qrcode(self):
        return None

    def get_qrcode_picture(self):
        return FakePicture()

    async def check_state(self):
        return FakeEvents.DONE

    def get_credential(self):
        return "credential"


async def fake_buvid():
    return "buvid3"


def test_bilibili_login_coordinator_persists_only_after_qr_login_is_done():
    saved = []
    coordinator = BilibiliLoginCoordinator(
        qr_login_factory=lambda: (SuccessfulQrLogin(), FakeEvents),
        buvid_fetcher=fake_buvid,
        poll_seconds=0.001,
    )

    started = coordinator.start(lambda credential, buvid3: saved.append((credential, buvid3)))
    deadline = time.monotonic() + 1
    while coordinator.get(started.operation_id).status != "succeeded" and time.monotonic() < deadline:
        time.sleep(0.01)

    completed = coordinator.get(started.operation_id)
    assert completed.status == "succeeded"
    assert coordinator.qr_png(started.operation_id) == b"fake-png"
    assert saved == [("credential", "buvid3")]
