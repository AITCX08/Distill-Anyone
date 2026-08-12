# 更新日志

本项目采用 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格，并遵循语义化版本号。

## [0.4.0-beta] - 2026-08-12

### 新增

- Source Adapter 平台层与 episodes、Skill、RAG 分块三类输出层。
- 受控 Worker：每个作品在独立子进程中完成下载、音频、转写、摘要和交付，可暂停、恢复与重试。
- 本地 Dashboard：展示脱敏状态、真实阶段、任务队列、产物预览和平台登录入口。
- Linux、macOS 基础 Python CI 与 Node 24 Dashboard CI。
- Windows 与 macOS 的安装、启动、排障及安全边界文档。

### 变更

- 产品与仓库名称统一为 Distill-Everything。
- Dashboard 固定仅监听本机回环地址。

### 已知限制

- Bilibili / 抖音扫码、Playwright 浏览器行为和 Apple Silicon FunASR MPS 需要在真实 macOS 设备上验收。
- 不应将 Dashboard 暴露到局域网或公网。
