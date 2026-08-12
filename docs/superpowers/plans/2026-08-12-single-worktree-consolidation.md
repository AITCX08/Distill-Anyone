# 单目录安全收敛实施计划

> **执行方式：** 单主代理串行执行，不使用子代理；每一步完成后核验状态再进入下一步。

**目标：** 只保留 `Distill-Everything` 一个物理目录，并让它承载最新主线、现有数据和 Dashboard 运行服务。

**架构：** 代码历史使用 Git 分支保存，运行数据继续留在唯一目录。关联 worktree 只在对应修改已提交且新服务验证成功后移除。

**技术栈：** Git worktree、PowerShell、Python `pythonw.exe`、FastAPI Dashboard。

## 全局约束

- 不执行 `pytest`。
- 不使用 `git reset --hard`、`git clean` 或手工递归删除 worktree。
- 不修改或删除 `data/`、`output/`、凭据和现有产物。
- 所有路径在操作前必须解析并核对位于 `C:\Users\Administrator\Desktop\Vibe`。

---

### 任务 1：建立恢复点

- [x] 记录三个目录的 HEAD、分支、工作树状态和数据文件计数。
- [x] 提交本设计与计划，保存文档提交哈希。
- [x] 确认旧本地 `main` 已有归档引用，必要时创建新的日期化归档分支。

### 任务 2：保存 Dashboard 未提交现场

- [x] 在 `Distill-Everything-dashboard-runtime` 检查差异中没有凭据和运行数据。
- [x] 将全部代码、测试和中文文档修改提交到 `wip/legacy-state-cleanup`。
- [x] 验证该 worktree 状态干净并记录提交哈希。

### 任务 3：建立唯一正式主线

- [x] 获取远程引用并确认 `origin/main` 未在执行期间变化。
- [x] 将旧本地 `main` 改名为日期化归档分支。
- [x] 在 `Distill-Everything` 基于 `origin/main` 创建新的本地 `main`。
- [x] 将本设计与执行计划提交移植到新的 `main`。

### 任务 4：迁移 Dashboard 运行入口

- [x] 记录并停止当前端口 8765 的旧 `pythonw.exe` 进程。
- [x] 在唯一目录中创建隐藏启动器，代码、数据和输出路径全部指向唯一目录。
- [x] 使用隐藏窗口方式启动 Dashboard，不打开 CMD 窗口。
- [x] 请求 `/api/v1/health`，确认服务正常且静态资源兼容。

### 任务 5：移除关联 worktree

- [x] 再次确认两个关联 worktree 均无未提交修改。
- [x] 使用 `git worktree remove` 移除 `Distill-Everything-main`。
- [x] 使用 `git worktree remove` 移除 `Distill-Everything-dashboard-runtime`。
- [x] 执行 `git worktree prune` 并确认列表只剩唯一目录。

### 任务 6：最终验收

- [x] 确认唯一目录的 `main`、`origin/main` 和保留分支引用均正确。
- [x] 确认 `data/`、`output/` 和 `.local-artifacts/` 文件数量未减少。
- [x] 确认端口 8765 的进程命令行指向唯一目录。
- [x] 确认 `C:\Users\Administrator\Desktop\Vibe` 下只剩 `Distill-Everything` 一个相关项目目录。
- [x] 报告保留分支、提交哈希、健康检查结果和后续需要单独评审的 WIP 分支。
