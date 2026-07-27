from fastapi.testclient import TestClient

from src.application.queries import JobRepository
from src.application.service import DistillationService
from src.dashboard.app import create_dashboard_app
from src.platforms.models import AuthStatus, ItemType, PlatformDescriptor


class FakeAdapter:
    descriptor = PlatformDescriptor(
        name="douyin",
        url_patterns=("douyin.com",),
        item_types=frozenset({ItemType.VIDEO}),
        requires_browser=True,
        requires_auth=True,
    )

    def auth_status(self):
        return AuthStatus("missing", "Scan in external Chromium")

    def authenticate(self, *, headful):
        assert headful is True


class FakePlatforms:
    def __init__(self):
        self.adapter = FakeAdapter()

    def list_descriptors(self):
        return (self.adapter.descriptor,)

    def get(self, name):
        assert name == "douyin"
        return self.adapter


def test_platform_listing_and_login_response_never_expose_credentials(tmp_path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("dashboard", encoding="utf-8")
    service = DistillationService(
        repository=JobRepository(tmp_path / "jobs"), platform_manager=FakePlatforms()
    )
    client = TestClient(create_dashboard_app(service, static_dir, "test"))
    client.get("/api/v1/health")
    headers = {"Origin": "http://testserver", "X-Distill-CSRF": client.cookies["distill_csrf"]}

    listed = client.get("/api/v1/platforms")
    login = client.post("/api/v1/platforms/douyin/login", headers=headers)

    assert listed.json()[0]["auth_status"] == "missing"
    assert login.status_code == 200
    assert login.json()["status"] == "opening_browser"
    assert "cookie" not in login.text.lower()
    assert "credential" not in login.text.lower()
