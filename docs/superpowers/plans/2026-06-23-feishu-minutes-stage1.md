# Feishu 妙记 Stage 1（输入端）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一个 `feishu-meeting` CLI 命令，输入一条飞书妙记分享链接/token，自动经飞书 API 下载录音，复用现有 `src/meeting/` 流水线本地转写（含 cam++ 说话人分离）并产出飞书风格智能纪要（MD + PDF）。

**Architecture:** 新建 `src/feishu/` 集成模块（`client.py` 换 token、`minutes.py` 提取 token + 下载媒体、`errors.py` 飞书错误码映射），用 **raw `requests`**（非 lark-oapi SDK，理由见下）完成 2 步下载（先调妙记 media 接口拿 1 天有效期的临时 `download_url`，再流式 GET 下载文件）。把 `meeting` 命令里「transcript → MD/PDF」那段抽到 `src/meeting/pipeline.py` 复用，新命令下载完音频后直接走 `audio_to_transcript` + 该管线。

**Tech Stack:** Python 3.11（venv 在 `./Distill-Anyone/`）、click（CLI）、requests（新增）、pydantic（配置）、复用 funasr/weasyprint/markdown/jinja2。

**为什么 raw requests 而非 lark-oapi SDK：** Stage 1 只有「换 token + 调 media 接口 + 下载文件」共 2~3 个 HTTP 调用。raw `requests` 更易单测（直接 mock）、依赖更轻，符合 YAGNI。官方 `lark-oapi` SDK 的真正价值在 Stage 3 的长连接事件订阅（`lark.ws.Client`），到那时再引入即可，本阶段的下载代码无需重写（token/接口契约不变）。

**已核实的飞书 API 事实（来自 open.feishu.cn 官方文档 + lark SDK 源码，2026-06）：**
- 换 token：`POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal`，body `{"app_id","app_secret"}` → 响应 `{"code":0,"tenant_access_token":"...","expire":7200}`（≤2h）。
- 妙记下载：`GET https://open.feishu.cn/open-apis/minutes/v1/minutes/{minute_token}/media`，头 `Authorization: Bearer <token>` → 响应 **JSON** `{"code":0,"data":{"download_url":"..."}}`（**不是**二进制流；`download_url` 有效期约 1 天，需二次 GET 下载真正文件）。频率 5 次/秒。
- minute_token：妙记链接 `https://xxx.feishu.cn/minutes/<token>` 里 `/minutes/` 之后的 **24 位** `[A-Za-z0-9]`（文档示例外面可能带 `==` 掩码）。
- 错误码：`2091001` 参数非法 / `2091002` 找不到 / `2091003` 未转写完成（需稍后重试）/ `2091004` 已删除 / `2091005` 无权限（应用对该妙记无读权限或缺 scope）/ `2091006` 服务内部错误。
- 所需权限 scope：至少 `minutes:minutes.media:export`（下载音视频）；可选 `minutes:minutes:readonly`（读妙记信息）。旧 scope `minutes:minute:download` 已停止开放，勿用。

**Stage 1 边界（本计划只做这些）：** 仅「妙记链接 → 本地 MD/PDF」。**不**做：发飞书机器人（Stage 2）、事件订阅自动触发（Stage 3）、lark-oapi SDK、多格式输出。

---

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `requirements.txt` | 加 `requests` | Modify |
| `src/config.py` | 加 `FeishuConfig`（app_id/app_secret）并在 `load_config()` 里从 `FEISHU_*` 环境变量读取 | Modify |
| `src/feishu/__init__.py` | 模块标记（空） | Create |
| `src/feishu/errors.py` | 飞书异常类 + `raise_for_feishu_code()` 错误码映射 | Create |
| `src/feishu/client.py` | `FeishuClient`：换取并缓存 `tenant_access_token`，给出带鉴权的请求头 | Create |
| `src/feishu/minutes.py` | `extract_minute_token` / `get_media_download_url` / `download_file` / `download_minute_media` | Create |
| `src/meeting/pipeline.py` | `meeting_output_paths` + `transcript_to_minutes_files`：把「transcript → MD/PDF」抽出来给两个命令复用 | Create |
| `main.py` | 把 `meeting()` 改为调用 `transcript_to_minutes_files`；删除已迁走的 `_meeting_output_paths`；新增 `feishu-meeting` 命令 | Modify |
| `config.example.env` | 追加 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 占位 | Modify |
| `src/feishu/CLAUDE.md` | 新模块文档 | Create |
| `CLAUDE.md`（根） | Changelog 追加一行 | Modify |
| `tests/test_config_feishu.py` | 配置读取测试 | Create |
| `tests/test_feishu_token.py` | `extract_minute_token` 测试 | Create |
| `tests/test_feishu_errors.py` | 错误码映射测试 | Create |
| `tests/test_feishu_client.py` | `FeishuClient` token 测试 | Create |
| `tests/test_feishu_minutes.py` | 下载链路测试 | Create |
| `tests/test_meeting_pipeline.py` | 管线复用测试 | Create |
| `tests/test_feishu_meeting_cmd.py` | `feishu-meeting` CLI 接线测试 | Create |

**约定（贯穿所有命令）：**
- venv python：`./Distill-Anyone/bin/python`；pip：`./Distill-Anyone/bin/python -m pip`；pytest：`./Distill-Anyone/bin/python -m pytest`
- 重依赖（torch/funasr/weasyprint/markdown/jinja2）只在函数体内 lazy import（根 CLAUDE.md 硬规则 #4）。requests 较轻、`src/feishu/` 用得到处都是，可在模块顶部正常 import。
- 日志用 `rich.console`，不用 `print`（硬规则 #6）。

---

## Task 1: 依赖 + 飞书配置

**Files:**
- Modify: `requirements.txt`
- Modify: `src/config.py`
- Create: `tests/test_config_feishu.py`

- [ ] **Step 1: 加依赖并安装**

在 `requirements.txt` 末尾追加一行：

```
requests>=2.31.0                 # 飞书 Open Platform REST 调用（妙记下载）
```

Run: `./Distill-Anyone/bin/python -m pip install -r requirements.txt`
Expected: 安装 `requests`（或显示 already satisfied）。

- [ ] **Step 2: 写失败测试**

Create `tests/test_config_feishu.py`:

```python
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
```

- [ ] **Step 3: 运行测试确认失败**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_config_feishu.py -v`
Expected: FAIL —— `AttributeError: 'AppConfig' object has no attribute 'feishu'`

- [ ] **Step 4: 实现 FeishuConfig**

在 `src/config.py` 的 `FunASRConfig` 类之后、`AppConfig` 类之前插入：

```python
class FeishuConfig(BaseModel):
    """飞书开放平台自建应用配置"""
    app_id: str = Field(default="", description="飞书自建应用 App ID")
    app_secret: str = Field(default="", description="飞书自建应用 App Secret")
```

在 `AppConfig` 里，`funasr: FunASRConfig = Field(default_factory=FunASRConfig)` 这一行之后追加：

```python
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
```

在 `load_config()` 里，`funasr=FunASRConfig(...)` 这一块之后（闭合的 `)` 之前）追加：

```python
        feishu=FeishuConfig(
            app_id=os.getenv("FEISHU_APP_ID", ""),
            app_secret=os.getenv("FEISHU_APP_SECRET", ""),
        ),
```

- [ ] **Step 5: 运行测试确认通过**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_config_feishu.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 提交**

```bash
git add requirements.txt src/config.py tests/test_config_feishu.py
git commit -m "feat(feishu): add FeishuConfig (app_id/app_secret) + requests dep"
```

---

## Task 2: 从妙记链接提取 minute_token

**Files:**
- Create: `src/feishu/__init__.py`
- Create: `src/feishu/minutes.py`（先只放 `extract_minute_token`）
- Create: `tests/test_feishu_token.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_feishu_token.py`:

```python
import pytest

from src.feishu.minutes import extract_minute_token


def test_extract_from_raw_token():
    tok = "obcnq3b9jl72l83w4f149w9c"  # 恰好 24 位
    assert extract_minute_token(tok) == tok


def test_extract_from_full_url():
    url = "https://sample.feishu.cn/minutes/obcnq3b9jl72l83w4f149w9c"
    assert extract_minute_token(url) == "obcnq3b9jl72l83w4f149w9c"


def test_extract_strips_equal_mask():
    url = "https://sample.feishu.cn/minutes/==obcnq3b9jl72l83w4f149w9c=="
    assert extract_minute_token(url) == "obcnq3b9jl72l83w4f149w9c"


def test_extract_ignores_query_and_anchor():
    url = "https://x.feishu.cn/minutes/obcnq3b9jl72l83w4f149w9c?from=share#top"
    assert extract_minute_token(url) == "obcnq3b9jl72l83w4f149w9c"


def test_extract_empty_raises():
    with pytest.raises(ValueError):
        extract_minute_token("   ")


def test_extract_no_token_raises():
    with pytest.raises(ValueError):
        extract_minute_token("https://x.feishu.cn/docs/short")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_feishu_token.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'src.feishu'`

- [ ] **Step 3: 创建模块 + 实现**

Create `src/feishu/__init__.py`（空文件，仅作包标记）：

```python
```

Create `src/feishu/minutes.py`:

```python
"""飞书妙记（Minutes）下载：链接 → minute_token → 临时 download_url → 本地文件。"""

from __future__ import annotations

import re

# 妙记 token：/minutes/ 之后的 24 位 [A-Za-z0-9]
_TOKEN_RE = re.compile(r"[A-Za-z0-9]{24}")


def extract_minute_token(url_or_token: str) -> str:
    """从妙记分享链接或原始 token 中提取 24 位 minute_token。

    支持：
      - 原始 token："obcnq3b9jl72l83w4f149w9c"
      - 完整链接："https://xxx.feishu.cn/minutes/<token>"
      - 带 == 掩码 / ?query / #anchor 的链接
    取不到 24 位 token 时抛 ValueError。
    """
    if not url_or_token or not url_or_token.strip():
        raise ValueError("妙记链接或 token 不能为空")
    text = url_or_token.strip()
    if "/minutes/" in text:
        text = text.split("/minutes/", 1)[1]
    text = text.split("?", 1)[0].split("#", 1)[0]
    m = _TOKEN_RE.search(text)
    if not m:
        raise ValueError(f"无法从输入中提取 24 位 minute_token：{url_or_token!r}")
    return m.group(0)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_feishu_token.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add src/feishu/__init__.py src/feishu/minutes.py tests/test_feishu_token.py
git commit -m "feat(feishu): extract_minute_token from share link/token"
```

---

## Task 3: 飞书错误码映射

**Files:**
- Create: `src/feishu/errors.py`
- Create: `tests/test_feishu_errors.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_feishu_errors.py`:

```python
import pytest

from src.feishu.errors import (
    FeishuError,
    MinuteNotReadyError,
    MinutePermissionError,
    MinuteNotFoundError,
    raise_for_feishu_code,
)


def test_code_zero_is_noop():
    # code==0 不抛
    raise_for_feishu_code(0, "ok")


def test_not_ready_2091003():
    with pytest.raises(MinuteNotReadyError) as ei:
        raise_for_feishu_code(2091003, "not ready")
    assert ei.value.code == 2091003


def test_permission_2091005():
    with pytest.raises(MinutePermissionError):
        raise_for_feishu_code(2091005, "permission deny")


def test_not_found_2091002_and_2091004():
    with pytest.raises(MinuteNotFoundError):
        raise_for_feishu_code(2091002, "not found")
    with pytest.raises(MinuteNotFoundError):
        raise_for_feishu_code(2091004, "deleted")


def test_unknown_code_falls_back_to_base():
    with pytest.raises(FeishuError) as ei:
        raise_for_feishu_code(99999, "weird")
    assert ei.value.code == 99999
    # 子类不应命中
    assert not isinstance(ei.value, (MinuteNotReadyError, MinutePermissionError, MinuteNotFoundError))


def test_log_id_passthrough():
    with pytest.raises(FeishuError) as ei:
        raise_for_feishu_code(2091006, "internal", log_id="lg-123")
    assert ei.value.log_id == "lg-123"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_feishu_errors.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'src.feishu.errors'`

- [ ] **Step 3: 实现**

Create `src/feishu/errors.py`:

```python
"""飞书 API 异常 + 妙记错误码映射。

错误码来自 open.feishu.cn 妙记 media 接口文档：
2091001 参数非法 / 2091002 找不到 / 2091003 未转写完成 /
2091004 已删除 / 2091005 无权限 / 2091006 服务内部错误。
"""

from __future__ import annotations

from typing import Optional


class FeishuError(Exception):
    """飞书 API 调用异常基类。"""

    def __init__(self, message: str, code: Optional[int] = None, log_id: Optional[str] = None):
        self.code = code
        self.log_id = log_id
        super().__init__(message)


class MinuteNotReadyError(FeishuError):
    """妙记尚未转写完成（2091003），可稍后重试。"""


class MinutePermissionError(FeishuError):
    """应用对该妙记无读权限 / scope 未授予（2091005）。"""


class MinuteNotFoundError(FeishuError):
    """妙记不存在或已删除（2091002 / 2091004）。"""


# code -> (中文提示, 异常类)
_CODE_MAP = {
    2091001: ("参数非法，请检查 minute_token 是否为 24 位", FeishuError),
    2091002: ("妙记不存在，请检查链接 / token 是否正确", MinuteNotFoundError),
    2091003: ("妙记尚未转写完成，请稍后再试", MinuteNotReadyError),
    2091004: ("妙记已被删除", MinuteNotFoundError),
    2091005: (
        "应用对该妙记无读权限：请确认已授予 minutes:minutes.media:export 权限，"
        "且应用可访问该篇妙记",
        MinutePermissionError,
    ),
    2091006: ("飞书服务内部错误，请稍后重试", FeishuError),
}


def raise_for_feishu_code(code: int, msg: str = "", log_id: Optional[str] = None) -> None:
    """根据飞书返回码抛出对应异常；code==0 时不抛。"""
    if code == 0:
        return
    text, exc_cls = _CODE_MAP.get(code, (f"飞书 API 调用失败：code={code} msg={msg}", FeishuError))
    raise exc_cls(text, code=code, log_id=log_id)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_feishu_errors.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add src/feishu/errors.py tests/test_feishu_errors.py
git commit -m "feat(feishu): error classes + minute error-code mapping"
```

---

## Task 4: FeishuClient（换取 tenant_access_token）

**Files:**
- Create: `src/feishu/client.py`
- Create: `tests/test_feishu_client.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_feishu_client.py`:

```python
import pytest

from src.feishu.client import FeishuClient
from src.feishu.errors import FeishuError


class _FakeResp:
    def __init__(self, json_data, status_ok=True):
        self._json = json_data
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("http error")

    def json(self):
        return self._json


def test_empty_credentials_raises():
    with pytest.raises(FeishuError):
        FeishuClient("", "")
    with pytest.raises(FeishuError):
        FeishuClient("cli_x", "")


def test_get_token_success_and_cached(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        assert url.endswith("/auth/v3/tenant_access_token/internal")
        assert json == {"app_id": "cli_x", "app_secret": "sec_y"}
        return _FakeResp({"code": 0, "tenant_access_token": "t-abc", "expire": 7200})

    monkeypatch.setattr("src.feishu.client.requests.post", fake_post)

    client = FeishuClient("cli_x", "sec_y")
    assert client.get_tenant_access_token() == "t-abc"
    # 第二次走缓存，不再 POST
    assert client.get_tenant_access_token() == "t-abc"
    assert calls["n"] == 1


def test_get_token_force_refresh(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        return _FakeResp({"code": 0, "tenant_access_token": f"t-{calls['n']}", "expire": 7200})

    monkeypatch.setattr("src.feishu.client.requests.post", fake_post)
    client = FeishuClient("cli_x", "sec_y")
    assert client.get_tenant_access_token() == "t-1"
    assert client.get_tenant_access_token(force_refresh=True) == "t-2"
    assert calls["n"] == 2


def test_get_token_api_error_raises(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        return _FakeResp({"code": 99991663, "msg": "app not found"})

    monkeypatch.setattr("src.feishu.client.requests.post", fake_post)
    client = FeishuClient("cli_x", "sec_y")
    with pytest.raises(FeishuError):
        client.get_tenant_access_token()


def test_auth_headers(monkeypatch):
    monkeypatch.setattr(
        "src.feishu.client.requests.post",
        lambda url, json=None, timeout=None: _FakeResp(
            {"code": 0, "tenant_access_token": "t-xyz", "expire": 7200}
        ),
    )
    client = FeishuClient("cli_x", "sec_y")
    assert client.auth_headers() == {"Authorization": "Bearer t-xyz"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_feishu_client.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'src.feishu.client'`

- [ ] **Step 3: 实现**

Create `src/feishu/client.py`:

```python
"""飞书自建应用 REST 客户端（raw HTTP）：换取并缓存 tenant_access_token。"""

from __future__ import annotations

from typing import Optional

import requests

from src.feishu.errors import FeishuError

FEISHU_BASE = "https://open.feishu.cn/open-apis"


class FeishuClient:
    """飞书自建应用客户端。

    负责用 app_id/app_secret 换取 tenant_access_token（自建应用），并提供带鉴权的
    请求头。单次 CLI 运行内缓存 token（一次命令只下载一篇妙记，几秒内完成，无需做
    30 分钟续期逻辑——那是 Stage 3 长连接场景才需要的）。
    """

    def __init__(self, app_id: str, app_secret: str, base_url: str = FEISHU_BASE, timeout: int = 15):
        if not app_id or not app_secret:
            raise FeishuError(
                "缺少飞书应用凭证：请在 .env 设置 FEISHU_APP_ID / FEISHU_APP_SECRET"
            )
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token: Optional[str] = None

    def get_tenant_access_token(self, force_refresh: bool = False) -> str:
        """换取 tenant_access_token；进程内缓存，force_refresh 强制重换。"""
        if self._token and not force_refresh:
            return self._token
        resp = requests.post(
            f"{self.base_url}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", -1) != 0:
            raise FeishuError(
                f"获取 tenant_access_token 失败：code={data.get('code')} msg={data.get('msg')}",
                code=data.get("code"),
            )
        self._token = data["tenant_access_token"]
        return self._token

    def auth_headers(self) -> dict:
        """带 tenant_access_token 的鉴权请求头。"""
        return {"Authorization": f"Bearer {self.get_tenant_access_token()}"}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_feishu_client.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add src/feishu/client.py tests/test_feishu_client.py
git commit -m "feat(feishu): FeishuClient tenant_access_token auth (raw HTTP)"
```

---

## Task 5: 妙记媒体下载链路

**Files:**
- Modify: `src/feishu/minutes.py`（追加 3 个函数）
- Create: `tests/test_feishu_minutes.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_feishu_minutes.py`:

```python
import pytest

from src.feishu import minutes as M
from src.feishu.errors import MinuteNotReadyError, MinutePermissionError


class _Client:
    """get_media_download_url 只用到 base_url / timeout / auth_headers()。"""
    base_url = "https://open.feishu.cn/open-apis"
    timeout = 15

    def auth_headers(self):
        return {"Authorization": "Bearer t-test"}


class _MediaResp:
    def __init__(self, json_data):
        self._json = json_data
        self.headers = {"X-Tt-Logid": "lg-1"}

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_get_media_download_url_success(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _MediaResp({"code": 0, "data": {"download_url": "https://dl.example/abc"}})

    monkeypatch.setattr("src.feishu.minutes.requests.get", fake_get)
    url = M.get_media_download_url(_Client(), "obcnq3b9jl72l83w4f149w9c")
    assert url == "https://dl.example/abc"
    assert captured["url"].endswith("/minutes/v1/minutes/obcnq3b9jl72l83w4f149w9c/media")
    assert captured["headers"] == {"Authorization": "Bearer t-test"}


def test_get_media_download_url_not_ready(monkeypatch):
    monkeypatch.setattr(
        "src.feishu.minutes.requests.get",
        lambda url, headers=None, timeout=None: _MediaResp({"code": 2091003, "msg": "not ready"}),
    )
    with pytest.raises(MinuteNotReadyError):
        M.get_media_download_url(_Client(), "obcnq3b9jl72l83w4f149w9c")


def test_get_media_download_url_permission(monkeypatch):
    monkeypatch.setattr(
        "src.feishu.minutes.requests.get",
        lambda url, headers=None, timeout=None: _MediaResp({"code": 2091005, "msg": "deny"}),
    )
    with pytest.raises(MinutePermissionError):
        M.get_media_download_url(_Client(), "obcnq3b9jl72l83w4f149w9c")


class _StreamResp:
    def __init__(self, chunks):
        self._chunks = chunks
        self.closed = False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=8192):
        for c in self._chunks:
            yield c

    def close(self):
        self.closed = True


def test_download_file_writes_bytes(monkeypatch, tmp_path):
    resp = _StreamResp([b"hello ", b"world"])
    monkeypatch.setattr(
        "src.feishu.minutes.requests.get",
        lambda url, stream=False, timeout=None: resp,
    )
    dest = tmp_path / "sub" / "out.media"
    result = M.download_file("https://dl.example/abc", dest)
    assert result == dest
    assert dest.exists()
    assert dest.read_bytes() == b"hello world"
    assert resp.closed is True  # 确保连接关闭


def test_download_minute_media_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setattr(M, "get_media_download_url", lambda client, token: "https://dl/x")
    monkeypatch.setattr(
        "src.feishu.minutes.requests.get",
        lambda url, stream=False, timeout=None: _StreamResp([b"AUDIO"]),
    )
    dest = tmp_path / "feishu-tok.media"
    out = M.download_minute_media(object(), "obcnq3b9jl72l83w4f149w9c", dest)
    assert out == dest
    assert dest.read_bytes() == b"AUDIO"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_feishu_minutes.py -v`
Expected: FAIL —— `AttributeError: module 'src.feishu.minutes' has no attribute 'get_media_download_url'`

- [ ] **Step 3: 实现（追加到 `src/feishu/minutes.py`）**

在 `src/feishu/minutes.py` 顶部 import 区追加：

```python
from pathlib import Path

import requests

from src.feishu.errors import raise_for_feishu_code
```

在文件末尾（`extract_minute_token` 之后）追加：

```python
def get_media_download_url(client, minute_token: str) -> str:
    """调妙记 media 接口，返回临时下载地址 download_url（有效期约 1 天）。

    注意：该接口返回 JSON（含 download_url），不是二进制流。失败按飞书错误码抛
    对应异常（见 src/feishu/errors.py）。client 需提供 base_url / timeout / auth_headers()。
    """
    resp = requests.get(
        f"{client.base_url}/minutes/v1/minutes/{minute_token}/media",
        headers=client.auth_headers(),
        timeout=client.timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    log_id = resp.headers.get("X-Tt-Logid") if getattr(resp, "headers", None) else None
    raise_for_feishu_code(data.get("code", -1), data.get("msg", ""), log_id=log_id)
    return data["data"]["download_url"]


def download_file(url: str, dest_path, timeout: int = 60, chunk_size: int = 8192) -> Path:
    """流式下载 url 到 dest_path（自动建父目录）。返回 dest_path。"""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True, timeout=timeout)
    try:
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
    finally:
        resp.close()
    return dest_path


def download_minute_media(client, minute_token: str, dest_path) -> Path:
    """端到端：取 download_url → 下载到本地文件。返回 dest_path。

    minute_token 须为已提取的 24 位 token（调用方先用 extract_minute_token 提取）。
    """
    download_url = get_media_download_url(client, minute_token)
    return download_file(download_url, dest_path)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_feishu_minutes.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add src/feishu/minutes.py tests/test_feishu_minutes.py
git commit -m "feat(feishu): minutes media download (get_url -> stream to file)"
```

---

## Task 6: 抽出会议管线复用层 + 重构 meeting()

> 目标：把 `meeting()` 里「transcript → MD/PDF」那段抽到 `src/meeting/pipeline.py`，让 `meeting` 和新 `feishu-meeting` 共用，避免重复。**行为保持不变**（现有 `tests/test_meeting_*.py` 必须仍全绿）。

**Files:**
- Create: `src/meeting/pipeline.py`
- Modify: `main.py`（重构 `meeting()`，删除迁走的 `_meeting_output_paths`）
- Create: `tests/test_meeting_pipeline.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_meeting_pipeline.py`:

```python
from src.meeting.models import MeetingTranscript, TranscriptLine
from src.meeting.pipeline import meeting_output_paths, transcript_to_minutes_files


class _FakeLLM:
    """MeetingMinutesGenerator 内部会调 llm_client.chat(prompt, max_tokens) -> str。
    返回一段最小可解析的 JSON，让 generate() 走正常路径产出 MeetingMinutes。"""

    def chat(self, prompt, max_tokens=4096):
        return (
            '{"summary_intro": "这是一次测试会议。", '
            '"outline": [{"title": "议题A", "children": []}], '
            '"todos": [{"task": "跟进X", "assignee": "说话人 1"}], '
            '"keywords": ["测试"]}'
        )


def _transcript():
    return MeetingTranscript(
        title="管线测试",
        lines=[TranscriptLine("说话人 1", "00:03", "大家好，开始开会。")],
        speakers=["说话人 1"],
    )


def test_meeting_output_paths_format(tmp_path):
    md, pdf = meeting_output_paths(tmp_path, "周会")
    assert md.parent == tmp_path
    assert md.name.startswith("周会-纪要-") and md.suffix == ".md"
    assert pdf.name.startswith("周会-纪要-") and pdf.suffix == ".pdf"
    # 同一次调用 md / pdf 共享时间戳 stem
    assert md.stem == pdf.stem


def test_transcript_to_minutes_files_no_pdf_writes_md(tmp_path):
    md_path, pdf_path = transcript_to_minutes_files(
        _transcript(), _FakeLLM(), tmp_path, no_pdf=True
    )
    assert md_path.exists()
    assert pdf_path is None
    text = md_path.read_text(encoding="utf-8")
    assert text.startswith("# 智能纪要：管线测试")
    assert "# 文字记录" in text


def test_transcript_to_minutes_files_pdf_failure_degrades(tmp_path, monkeypatch):
    # 模拟 render_pdf 抛错（如缺 pango），应降级：MD 仍在，pdf_path 返回 None，不抛
    def boom(md_text, output_path, template_dir="templates"):
        raise RuntimeError("weasyprint missing pango")

    monkeypatch.setattr("src.meeting.pipeline.render_pdf", boom)
    md_path, pdf_path = transcript_to_minutes_files(
        _transcript(), _FakeLLM(), tmp_path, no_pdf=False
    )
    assert md_path.exists()
    assert pdf_path is None
```

> 注：`_FakeLLM.chat` 的返回 JSON 字段需与 `MeetingMinutesGenerator.generate` 期望一致。若该测试在 Step 4 后仍因 JSON 字段不匹配失败，运行 `./Distill-Anyone/bin/python -m pytest tests/test_meeting_minutes.py -v` 看现有测试如何构造 fake LLM 返回，照其 schema 对齐本测试的 JSON。

- [ ] **Step 2: 运行测试确认失败**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_meeting_pipeline.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'src.meeting.pipeline'`

- [ ] **Step 3: 创建 pipeline.py**

Create `src/meeting/pipeline.py`:

```python
"""会议纪要管线复用层：MeetingTranscript → 智能纪要 MD(+PDF)。

meeting（本地 txt / 音频）与 feishu-meeting（妙记录音）两个命令共用「转写之后」的
逻辑，避免在 main.py 里重复 LLM 生成 + 渲染 + PDF 降级。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console

from src.meeting.minutes_generator import MeetingMinutesGenerator
from src.meeting.models import MeetingTranscript
from src.meeting.renderer import render_markdown, render_pdf

console = Console()


def meeting_output_paths(output_dir: Path, name: str) -> Tuple[Path, Path]:
    """生成带时间戳的会议纪要 MD / PDF 路径，每次新增不覆盖。

    格式：{output_dir}/{name}-纪要-{YYYYMMDD-HHMMSS}.{md,pdf}
    """
    safe_name = (name or "meeting").strip() or "meeting"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"{safe_name}-纪要-{timestamp}"
    return output_dir / f"{stem}.md", output_dir / f"{stem}.pdf"


def transcript_to_minutes_files(
    transcript: MeetingTranscript,
    llm_client,
    output_dir: Path,
    no_pdf: bool = False,
) -> Tuple[Path, Optional[Path]]:
    """从 MeetingTranscript 生成智能纪要并渲染 MD(+PDF)。

    返回 (md_path, pdf_path|None)。先落 MD 保证有产物；PDF 失败降级为 None 不抛。
    llm_client 由调用方用 create_llm_client(provider, config) 构造好传入（本函数不碰
    LLM 工厂，便于单测注入 fake）。
    """
    console.print("[blue]生成智能纪要中...")
    minutes = MeetingMinutesGenerator(llm_client).generate(transcript)

    md_path, pdf_path = meeting_output_paths(output_dir, transcript.title)
    md_text = render_markdown(minutes, transcript)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_text, encoding="utf-8")
    console.print(f"[green]Markdown 已生成: {md_path}")

    if no_pdf:
        return md_path, None

    try:
        render_pdf(md_text, pdf_path)
        return md_path, pdf_path
    except Exception as e:
        console.print(f"[yellow]PDF 生成失败（Markdown 已生成）: {e}")
        console.print(
            "[dim]提示: weasyprint 需系统库，执行 `brew install pango`；或加 --no-pdf 只出 Markdown"
        )
        return md_path, None
```

- [ ] **Step 4: 运行新测试确认通过**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_meeting_pipeline.py -v`
Expected: PASS（3 passed）。若因 `_FakeLLM` JSON schema 不符失败，按 Step 1 的注释对齐后再跑。

- [ ] **Step 5: 重构 main.py::meeting() 调用管线**

在 `main.py` 的 `meeting()` 函数里：

(a) 把函数内的 import 块（第 759-764 行附近）从：

```python
    from src.config import load_config
    from src.reader.document_reader import read_document
    from src.clean.text_processor import create_llm_client
    from src.meeting.transcript_parser import parse_feishu_txt
    from src.meeting.minutes_generator import MeetingMinutesGenerator
    from src.meeting.renderer import render_markdown, render_pdf
```

改为（删掉 generator/renderer，加 pipeline）：

```python
    from src.config import load_config
    from src.reader.document_reader import read_document
    from src.clean.text_processor import create_llm_client
    from src.meeting.transcript_parser import parse_feishu_txt
    from src.meeting.pipeline import transcript_to_minutes_files
```

(b) 把「# 2. LLM 生成智能纪要」到函数末尾（原第 788-812 行）整段替换为：

```python
    # 2. LLM 生成智能纪要 + 渲染 MD/PDF（复用 meeting 管线）
    llm_client = create_llm_client(provider, config)
    if not llm_client:
        console.print("[red]错误: 生成智能纪要需要可用的 LLM（请在 .env 配置对应 API Key）")
        sys.exit(1)
    transcript_to_minutes_files(transcript, llm_client, config.output_dir, no_pdf)

    console.print("[bold green]会议纪要完成!")
```

- [ ] **Step 6: 删除已迁走的 `_meeting_output_paths`**

确认它已无其它引用，再删除 `main.py` 中 `def _meeting_output_paths(...)`（原第 45-53 行）整个函数。

Run: `grep -rn "_meeting_output_paths" main.py tests/`
Expected: 无输出（已无引用）。若 `tests/` 里有引用，改为 import `from src.meeting.pipeline import meeting_output_paths` 并改用新名。

- [ ] **Step 7: 跑全部 meeting 相关测试 + 冒烟 CLI，确认行为不变**

```bash
./Distill-Anyone/bin/python -m pytest tests/test_meeting_pipeline.py tests/test_meeting_parser.py tests/test_meeting_minutes.py tests/test_meeting_renderer.py tests/test_meeting_audio.py -v
./Distill-Anyone/bin/python main.py meeting --help
```
Expected: 全部 PASS；`meeting --help` 正常打印（命令仍注册、未破坏）。

- [ ] **Step 8: 提交**

```bash
git add src/meeting/pipeline.py main.py tests/test_meeting_pipeline.py
git commit -m "refactor(meeting): extract transcript->minutes pipeline for reuse"
```

---

## Task 7: feishu-meeting CLI 命令

**Files:**
- Modify: `main.py`（新增 `feishu_meeting` 命令）
- Create: `tests/test_feishu_meeting_cmd.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_feishu_meeting_cmd.py`:

```python
from click.testing import CliRunner

import main as main_mod
from src.meeting.models import MeetingTranscript, TranscriptLine


def test_feishu_meeting_wires_download_transcribe_pipeline(monkeypatch, tmp_path):
    calls = {}

    # 1) 配置：给足凭证 + 输出到 tmp
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec_y")

    # 2) mock 下载：假装写出媒体文件
    def fake_download(client, minute_token, dest_path):
        from pathlib import Path
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"FAKEAUDIO")
        calls["download_token"] = minute_token
        calls["download_dest"] = dest_path
        return dest_path

    monkeypatch.setattr("src.feishu.minutes.download_minute_media", fake_download)

    # 3) mock 本地转写：返回一个最小 transcript
    def fake_transcribe(audio_path, config):
        calls["transcribe_path"] = audio_path
        return MeetingTranscript(
            title="", lines=[TranscriptLine("说话人 1", "00:01", "你好")], speakers=["说话人 1"]
        )

    monkeypatch.setattr("src.meeting.audio_transcriber.audio_to_transcript", fake_transcribe)

    # 4) mock LLM 工厂 + 管线（不真跑 LLM / 渲染）
    monkeypatch.setattr("src.clean.text_processor.create_llm_client", lambda provider, config: object())

    def fake_pipeline(transcript, llm_client, output_dir, no_pdf=False):
        calls["pipeline_title"] = transcript.title
        calls["pipeline_no_pdf"] = no_pdf
        return (tmp_path / "x.md", None)

    monkeypatch.setattr("src.meeting.pipeline.transcript_to_minutes_files", fake_pipeline)

    runner = CliRunner()
    result = runner.invoke(
        main_mod.cli,
        ["feishu-meeting", "--url",
         "https://x.feishu.cn/minutes/obcnq3b9jl72l83w4f149w9c", "--no-pdf"],
    )

    assert result.exit_code == 0, result.output
    assert calls["download_token"] == "obcnq3b9jl72l83w4f149w9c"
    # transcript.title 缺省回落到 minute_token
    assert calls["pipeline_title"] == "obcnq3b9jl72l83w4f149w9c"
    assert calls["pipeline_no_pdf"] is True


def test_feishu_meeting_download_error_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "sec_y")

    def boom(client, minute_token, dest_path):
        from src.feishu.errors import MinuteNotReadyError
        raise MinuteNotReadyError("妙记尚未转写完成，请稍后再试", code=2091003)

    monkeypatch.setattr("src.feishu.minutes.download_minute_media", boom)

    runner = CliRunner()
    result = runner.invoke(
        main_mod.cli,
        ["feishu-meeting", "--url", "obcnq3b9jl72l83w4f149w9c"],
    )
    assert result.exit_code != 0
    assert "妙记尚未转写完成" in result.output
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_feishu_meeting_cmd.py -v`
Expected: FAIL —— `No such command 'feishu-meeting'.`

- [ ] **Step 3: 实现命令**

在 `main.py` 中，紧接 `meeting()` 命令之后（`fuse` 命令之前）新增：

```python
@cli.command("feishu-meeting")
@click.option("--url", "minute_url", type=str, required=True,
              help="飞书妙记分享链接或 24 位 minute_token")
@click.option("--llm", "llm_provider", type=LLM_CHOICES,
              default=None, help="LLM提供商")
@click.option("--title", "meeting_title", type=str, default=None,
              help="会议主题（默认用 minute_token）")
@click.option("--no-pdf", is_flag=True, default=False,
              help="只生成 Markdown，不生成 PDF")
def feishu_meeting(minute_url, llm_provider, meeting_title, no_pdf):
    """飞书妙记录音 → 自动下载 → 本地转写(说话人分离) → 智能纪要（MD + PDF）"""
    from src.config import load_config
    from src.clean.text_processor import create_llm_client
    from src.feishu.client import FeishuClient
    from src.feishu.errors import FeishuError
    from src.feishu.minutes import extract_minute_token, download_minute_media
    from src.meeting.audio_transcriber import audio_to_transcript
    from src.meeting.pipeline import transcript_to_minutes_files

    config = load_config()
    provider = llm_provider or config.llm_provider

    try:
        minute_token = extract_minute_token(minute_url)
    except ValueError as e:
        console.print(f"[red]链接/ token 无法解析: {e}")
        sys.exit(1)

    console.print(Panel(
        f"[bold]飞书妙记纪要[/bold]\nminute_token: {minute_token}\nLLM: {provider}",
        title="Distill-Anyone",
    ))

    # 1. 从飞书下载妙记录音到本地（config.audio_dir 已由 ensure_dirs 建好）
    try:
        client = FeishuClient(config.feishu.app_id, config.feishu.app_secret)
        media_path = config.audio_dir / f"feishu-{minute_token}.media"
        console.print("[blue]下载妙记录音中...")
        download_minute_media(client, minute_token, media_path)
    except FeishuError as e:
        console.print(f"[red]下载妙记录音失败: {e}")
        sys.exit(1)
    console.print(f"[green]录音已下载: {media_path}")

    # 2. 本地转写（ffmpeg + FunASR cam++ 说话人分离）
    console.print("[blue]本地转写中（首次会下载 cam++ 模型）...")
    transcript = audio_to_transcript(media_path, config)
    transcript.title = meeting_title or minute_token
    console.print(
        f"[blue]转写完成: {len(transcript.lines)} 段发言, {len(transcript.speakers)} 位说话人"
    )

    # 3. LLM 生成纪要 + 渲染 MD/PDF（复用 meeting 管线）
    llm_client = create_llm_client(provider, config)
    if not llm_client:
        console.print("[red]错误: 生成智能纪要需要可用的 LLM（请在 .env 配置对应 API Key）")
        sys.exit(1)
    transcript_to_minutes_files(transcript, llm_client, config.output_dir, no_pdf)

    console.print("[bold green]飞书妙记纪要完成!")
```

> 接线说明：命令体内用 `from ... import`（lazy import，符合硬规则 #4 且让单测可在调用时 monkeypatch 到对应模块属性）。下载目标用 `.media` 后缀——ffmpeg `-i` 按内容嗅探格式，扩展名无所谓（妙记可能下来 mp4/m4a）。

- [ ] **Step 4: 运行测试确认通过**

Run: `./Distill-Anyone/bin/python -m pytest tests/test_feishu_meeting_cmd.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 冒烟确认命令注册**

Run: `./Distill-Anyone/bin/python main.py feishu-meeting --help`
Expected: 打印 `--url / --llm / --title / --no-pdf` 选项说明，无报错。

- [ ] **Step 6: 提交**

```bash
git add main.py tests/test_feishu_meeting_cmd.py
git commit -m "feat(feishu): feishu-meeting command (link -> download -> transcribe -> minutes)"
```

---

## Task 8: 文档 + 全量验证 + 手动冒烟

**Files:**
- Create: `src/feishu/CLAUDE.md`
- Modify: `CLAUDE.md`（根 Changelog）
- Modify: `config.example.env`

- [ ] **Step 1: 写模块文档**

Create `src/feishu/CLAUDE.md`:

```markdown
[← 返回 Distill-Anyone](../../CLAUDE.md) > **src/feishu**

# src/feishu — 飞书开放平台集成

## 模块职责

封装飞书自建应用对接。**Stage 1（已实现）**：下载飞书妙记录音。
（Stage 2 发机器人私信、Stage 3 事件订阅长连接待后续。）

## 文件

| 文件 | 职责 | 关键符号 |
|---|---|---|
| `client.py` | 换取并缓存 tenant_access_token | `FeishuClient.get_tenant_access_token` / `auth_headers` |
| `minutes.py` | 妙记链接解析 + 媒体下载 | `extract_minute_token` / `get_media_download_url` / `download_file` / `download_minute_media` |
| `errors.py` | 飞书异常 + 错误码映射 | `FeishuError` / `MinuteNotReadyError` / `MinutePermissionError` / `MinuteNotFoundError` / `raise_for_feishu_code` |

## 下载契约（已核实，2026-06）

- 换 token：`POST /open-apis/auth/v3/tenant_access_token/internal`（body app_id/app_secret）。
- 妙记媒体：`GET /open-apis/minutes/v1/minutes/{minute_token}/media` → JSON `data.download_url`
  （**临时链接，约 1 天有效**，需二次 GET 下载真正文件）。频率 5 次/秒。
- 错误码：2091003 未转写完成（重试）/ 2091005 无权限（缺 scope 或应用无权读该妙记）。
- 所需 scope：`minutes:minutes.media:export`（必），`minutes:minutes:readonly`（选）。
  旧 scope `minutes:minute:download` 已停开放，勿用。

## 入口（调用方）

`main.py::feishu_meeting()` → `extract_minute_token` → `FeishuClient` →
`download_minute_media` → `audio_to_transcript` → `src.meeting.pipeline.transcript_to_minutes_files`。

## 前置条件 / 坑

1. 需在飞书开放平台建**自建应用**，开通 `minutes:minutes.media:export`，正式租户多半需提交版本审核。
2. **应用必须对目标妙记有读权限**，否则 2091005；这是最常见的阻塞点。
3. 妙记**未转写完成**时下载报 2091003，需待转写完成再试。
4. raw `requests` 实现；lark-oapi SDK 留到 Stage 3 长连接事件订阅再引入。

## 反模式

- 不要在 `src/feishu/` 顶部 import lark-oapi（本阶段不依赖它）。
- 不要把 `download_url` 当二进制流——它是 JSON 字段，要二次 GET。
- 不要把 app_secret 写进代码 / 提交 git——只走 `.env` 的 `FEISHU_APP_SECRET`。
```

- [ ] **Step 2: 根 Changelog + 模块索引**

在 `CLAUDE.md`（根）的「变更记录」表末尾追加一行：

```markdown
| 2026-06-23 | 飞书妙记 Stage 1：新增 `src/feishu/`（client/minutes/errors，raw requests 下载妙记录音）+ `feishu-meeting` CLI 命令（链接→下载→本地转写→MD/PDF）；抽出 `src/meeting/pipeline.py` 供 meeting/feishu-meeting 复用 |
```

在根 `CLAUDE.md` 的「模块索引」表里追加一行：

```markdown
| `src/feishu/` | 飞书开放平台集成（Stage 1：妙记录音下载） | `FeishuClient`, `download_minute_media`, `extract_minute_token` | [CLAUDE.md](./src/feishu/CLAUDE.md) |
```

- [ ] **Step 3: 配置样例**

在 `config.example.env` 末尾追加：

```bash

# ===== 飞书开放平台（妙记下载，Stage 1）=====
# 自建应用 App ID / Secret（开放平台后台获取；需开通 minutes:minutes.media:export 权限）
FEISHU_APP_ID=
FEISHU_APP_SECRET=
```

- [ ] **Step 4: 全量测试 + 命令树冒烟**

```bash
./Distill-Anyone/bin/python -m pytest tests/ -v
./Distill-Anyone/bin/python main.py --help
./Distill-Anyone/bin/python main.py feishu-meeting --help
```
Expected: 全部测试 PASS（新增 + 既有 meeting 套件均绿）；`--help` 列出含 `feishu-meeting` 的命令树。

- [ ] **Step 5: 提交文档**

```bash
git add src/feishu/CLAUDE.md CLAUDE.md config.example.env
git commit -m "docs(feishu): module CLAUDE.md + root changelog + config.example.env"
```

- [ ] **Step 6: 手动端到端冒烟（需真实凭证，由用户执行）**

> 自动化测试全程用 mock（无网络/无凭证）。真正的「妙记 → MD/PDF」端到端只能用**真实飞书应用 + 一篇应用有读权限、且已转写完成的妙记**验证。请按下列步骤手动跑一次，并把结果贴回：

```bash
# 1. 配好凭证（编辑 .env）
#    FEISHU_APP_ID=cli_xxx
#    FEISHU_APP_SECRET=xxx
#    （飞书后台：该应用已开通 minutes:minutes.media:export，且对目标妙记有读权限）

# 2. 跑命令（换成你的妙记分享链接）
./Distill-Anyone/bin/python main.py feishu-meeting \
    --url "https://<你的子域>.feishu.cn/minutes/<minute_token>" \
    --llm deepseek

# 3. 期望：
#    - "录音已下载: data/audio/feishu-<token>.media"（文件大小 > 0）
#    - "转写完成: N 段发言, M 位说话人"
#    - "Markdown 已生成: output/<token>-纪要-<时间戳>.md"
#    - PDF 生成（若装了 pango）或降级提示
```

记录：启动命令 + 关键 stdout（截断 ≤30 行）+ 产物路径/大小。失败也照实贴（如 2091005 无权限 / 2091003 未转写完成），便于定位是凭证/权限/转写状态问题。

---

## Self-Review（计划自检结论）

**1. Spec 覆盖** —— 对照需求阶段一验收：
- 「API 把音频下载到本地（文件存在、大小>0）」→ Task 5 `download_minute_media` + Task 8 手动冒烟。
- 「下载音频跑完本地流水线，产出含说话人区分的纪要（md+PDF）」→ Task 7 命令串 `audio_to_transcript`（cam++）+ Task 6 管线 → MD/PDF。
- 「凭证走配置」→ Task 1 `FeishuConfig` + `FEISHU_*` env。
- 边界（不发机器人 / 不事件订阅 / 不 SDK / 不多格式）→ 计划顶部明确划出，Stage 2/3 不在本计划。

**2. Placeholder 扫描** —— 无 TBD/TODO；每个 code step 给了完整代码与可运行命令。两处显式的「运行时再核对」是有意的健壮性提示（pipeline 测试的 fake LLM JSON schema 对齐、`_meeting_output_paths` 残留引用 grep），非占位。

**3. 类型/命名一致性** —— `FeishuClient`(base_url/timeout/auth_headers)、`extract_minute_token`、`get_media_download_url(client, minute_token)`、`download_file(url, dest)`、`download_minute_media(client, minute_token, dest)`、`transcript_to_minutes_files(transcript, llm_client, output_dir, no_pdf)`、`meeting_output_paths(output_dir, name)`、`raise_for_feishu_code(code, msg, log_id)` 在测试与实现间签名一致。

**已知风险（实现/验证时留意）：**
- 真实端到端依赖飞书应用对目标妙记的**读权限**（2091005 是最可能的阻塞点）——属凭证/权限问题，非代码缺陷；手动冒烟暴露。
- `tests/test_meeting_pipeline.py` 的 `_FakeLLM` 返回 JSON 需匹配 `MeetingMinutesGenerator.generate` 期望的 schema；若不符，按 Step 1 注释参照 `tests/test_meeting_minutes.py` 现有 fake 对齐。

---

## 完工后（独立 review + 收尾）

- 实施完成后，按全局规则启动**独立 agent**用 code-reviewer rubric 复审本次改动（严禁自审），通过后再 SHIP。
- 本计划只覆盖 Stage 1。Stage 2（应用机器人私信推送，可配置文字/卡片/PDF）、Stage 3（事件订阅长连接自动触发）另起计划。
