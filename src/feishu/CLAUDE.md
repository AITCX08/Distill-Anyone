[← 返回 Distill-Everything](../../CLAUDE.md) > **src/feishu**

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
