# Distill-Everything 迁移前盘点

盘点时间：2026-08-11（Asia/Shanghai）

## Git 与工作树

- 主工作树：`C:\Users\Administrator\Desktop\Vibe\Distill-Anyone`，分支 `main`。
- Dashboard 运行工作树：`C:\Users\Administrator\Desktop\Vibe\Distill-Anyone-dashboard-runtime`，分支 `agent/bilibili-dialog-autoclose`。
- 当前远端：`https://github.com/AITCX08/Distill-Anyone.git`。
- 目标主目录：`C:\Users\Administrator\Desktop\Vibe\Distill-Everything`，盘点时不存在。
- 目标运行工作树：`C:\Users\Administrator\Desktop\Vibe\Distill-Everything-dashboard-runtime`，盘点时不存在。
- 主工作树已有未跟踪的 `.local-artifacts/`、`dashboard/`、`docs/superpowers/plans/2026-07-27-remaining-dashboard-release.md`、`src/series/`、`tools/`；迁移时必须原样保留。

## 本地数据与交付物

- 数据目录：`C:\Users\Administrator\Desktop\Vibe\Distill-Anyone\data`，存在。
- 产物目录：`C:\Users\Administrator\Desktop\Vibe\Distill-Anyone\output`，存在。
- 已发现 `job_state.json`：1 个。
- 已发现系列 `state.json`：1 个。
- 已发现产物文件：23 个。
- Dashboard 当前可读取已完成的 `imported-series-BV18bLkztE7R`：共 8 集、完成 8 集、失败 0 集。

## 当前 Dashboard

- 地址：`http://127.0.0.1:8765`。
- 监听进程：`pythonw.exe`，仅用于本地 Dashboard。
- 隐藏启动器：`.local-artifacts/start_dashboard_8765.pyw`，当前显式引用旧运行工作树、旧数据目录与旧产物目录。
- 健康检查在停止前返回：`status=ok`、`static_compatible=true`。

## 迁移保护结论

目标路径未占用，数据和产物可读，且当前没有运行中的系列任务。可以停止 Dashboard 后进行 GitHub 改名和路径迁移；不得删除或覆盖任何盘点项。
