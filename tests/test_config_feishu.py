"""src/config.py 的飞书配置读取测试。"""


def test_load_config_reads_feishu_keys(monkeypatch, tmp_path):
    # 把数据/输出目录指到临时目录，避免 ensure_dirs() 污染项目 data/
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test123")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret_test456")

    from src.config import load_config
    config = load_config()

    assert config.feishu.app_id == "cli_test123"
    assert config.feishu.app_secret == "secret_test456"


def test_feishu_defaults_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)

    from src.config import load_config
    config = load_config()

    assert config.feishu.app_id == ""
    assert config.feishu.app_secret == ""
