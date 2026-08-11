# Distill-Everything 全量改名与本地迁移实施计划

> **执行方式：** 单主代理串行执行。每个任务完成后做小提交；不启用子代理，不直接执行 `pytest`，不打开可见 CMD 窗口。

**目标：** 将 Distill-Anyone 安全迁移为 Distill-Everything，并保持已有数据、产物和 Dashboard 可用。

**架构：** GitHub、Git 工作树和本地运行目录按“停止服务 → 校验 → 移动 → 更新引用 → 验证”的顺序迁移。Python `src` 包和 Conda 环境保持不变；项目对外标识、脚本变量和运行路径改为新名称。

**技术栈：** Git/GitHub、PowerShell、Python 3.14 与既有 Conda 解释器、FastAPI/Uvicorn、React/Vite、Windows 本地文件系统。

## 全局约束

- 全部新增或更新的用户文档使用中文。
- 不移动 `C:\Coding\Anaconda\envs\Distill-Anyone`。
- 不删除 `data`、`output`、Git 历史或用户未提交改动。
- Dashboard 必须使用 `pythonw.exe` 隐藏启动；不得通过可见 CMD、任务计划程序或直接 `pytest` 验证。
- Python 测试仅使用项目的后台测试运行器或直接调用短小、无 pytest 依赖的回归测试函数；前端测试直接以 `C:\Coding\node\node.exe` 启动 Vitest。

---

### 任务 1：迁移前盘点与保护点

**文件：**
- 创建：`docs/superpowers/migrations/2026-08-11-distill-everything-preflight.md`
- 修改：无

- [ ] 记录当前 Git 分支、远端、主工作树与 Dashboard 工作树绝对路径。
- [ ] 记录 `data`、`output`、`.local-artifacts/start_dashboard_8765.pyw` 是否存在，并统计已完成任务状态文件与交付产物数量。
- [ ] 使用 `Get-NetTCPConnection -LocalPort 8765 -State Listen` 确认当前 Dashboard 监听进程；只停止该进程。
- [ ] 若任何目标新路径已经存在，停止迁移并报告冲突，不覆盖目录。
- [ ] 小提交：`docs: record distill-everything migration preflight`

### 任务 2：GitHub 仓库与 Git 远端迁移

**文件：**
- 修改：`.git/config`（由 Git 写入，不手工编辑）

- [ ] 在 GitHub 将 `AITCX08/Distill-Anyone` 重命名为 `AITCX08/Distill-Everything`。
- [ ] 执行 `git remote set-url origin https://github.com/AITCX08/Distill-Everything.git`。
- [ ] 用 `git ls-remote origin HEAD` 验证新远端可读，并记录仓库重命名结果。
- [ ] 验证旧地址仍由 GitHub 自动重定向，不将其作为运行配置。

### 任务 3：移动两个 Git 工作树与本地运行数据

**文件：**
- 修改：Git worktree 元数据（由 `git worktree move` 写入）
- 移动：`C:\Users\Administrator\Desktop\Vibe\Distill-Anyone` → `C:\Users\Administrator\Desktop\Vibe\Distill-Everything`
- 移动：`C:\Users\Administrator\Desktop\Vibe\Distill-Anyone-dashboard-runtime` → `C:\Users\Administrator\Desktop\Vibe\Distill-Everything-dashboard-runtime`
- 移动：新主目录中的 `data` 与 `output` 保持其相对位置

- [ ] 先执行 `git worktree list --porcelain` 确认两个工作树受 Git 管理且路径与盘点一致。
- [ ] 使用 `git worktree move` 移动 Dashboard 工作树；主工作树由受控目录移动后立刻运行 `git worktree repair` 校正元数据。
- [ ] 将主目录下 `data` 与 `output` 一并保留在新主目录中；迁移后验证状态文件、凭据目录和产物文件仍可读取。
- [ ] 使用 `git -C <新路径> status --short` 验证未提交修改仍完整存在。
- [ ] 若移动后的服务检查失败，在没有写入新数据前按相反顺序移动回旧路径。

### 任务 4：替换运行标识、脚本与活跃文档

**文件：**
- 修改：`README.md`
- 修改：`main.py`
- 修改：`src/__init__.py`
- 修改：`src/dashboard/__init__.py`
- 修改：`dashboard/package.json`
- 修改：`dashboard/package-lock.json`
- 修改：`dashboard/index.html`
- 修改：`scripts/README.md`
- 修改：`scripts/run-pytest-background.cmd`
- 修改：`src/platforms/bilibili/adapter.py`
- 修改：活跃的 `src/**/CLAUDE.md` 导航链接

- [ ] 先用 `rg` 生成当前运行代码、README、脚本和活跃导航中的旧名称清单；历史 `docs/superpowers/plans/**` 与 `docs/superpowers/specs/**` 不在批量替换范围。
- [ ] 将用户可见名称统一替换为 `Distill-Everything`，机器可读名称统一替换为 `distill-everything`。
- [ ] 将 `DISTILL_ANYONE_PYTHON` 改为 `DISTILL_EVERYTHING_PYTHON`，并更新示例与后台测试运行器的读取逻辑。
- [ ] 保持所有 Python 导入 `src.*` 不变；不得重命名 `src` 目录。
- [ ] 更新版本帮助测试或新增断言，证明 `main.py --help` 输出新项目名称、脚本读取新变量。
- [ ] 小提交：`refactor: rename product identifiers to distill-everything`

### 任务 5：更新 Dashboard 品牌与发布静态资源

**文件：**
- 修改：`dashboard/src/**` 中产品名称字符串
- 修改：`dashboard/index.html`
- 修改：`src/dashboard/static/index.html`
- 修改：`src/dashboard/static/.vite/manifest.json`
- 更新：`src/dashboard/static/assets/*`
- 测试：`dashboard/src/app/App.test.tsx` 或新增品牌断言测试

- [ ] 写前端断言，要求页面标题/品牌区域显示 `DISTILL // EVERYTHING` 或 `Distill-Everything 作战台`。
- [ ] 先用 Vitest 运行该断言，确认当前旧名称导致失败。
- [ ] 最小化替换 Dashboard 品牌、浏览器标题、静态 HTML 与 npm 包名。
- [ ] 使用 `C:\Coding\node\node.exe node_modules\typescript\bin\tsc -b` 与 `vitest.mjs run <目标测试>` 验证前端。
- [ ] 使用 `scripts/build_dashboard.py --from-dist` 发布静态资源，再用 `--check` 校验 manifest 自洽。
- [ ] 小提交：`feat(dashboard): brand workspace as distill-everything`

### 任务 6：迁移并重建隐藏 Dashboard 启动器

**文件：**
- 修改：`<新运行工作树>/.local-artifacts/start_dashboard_8765.pyw`（本机运行配置，不提交）
- 修改：`<新运行工作树>/.local-artifacts/dashboard-launcher.log`（仅在异常时产生，不提交）

- [ ] 将 `ROOT`、`DATA_DIR`、`OUTPUT_DIR` 更新为新项目路径。
- [ ] 保持解释器为 `C:\Coding\Anaconda\envs\Distill-Anyone\pythonw.exe`。
- [ ] 使用 `Start-Process -WindowStyle Hidden` 启动启动器；不得调用 `.cmd` 或创建可见终端。
- [ ] 请求 `http://127.0.0.1:8765/api/v1/health`，预期 `status=ok` 与 `static_compatible=true`。
- [ ] 校验 SSE 快照与 `/api/v1/jobs/imported-series-BV18bLkztE7R/items`：已有 8 集的标题、BV 号、完成时间和交付目录仍存在。

### 任务 7：全量回归、发布与迁移记录

**文件：**
- 创建：`docs/迁移到-Distill-Everything.md`
- 修改：`README.md`
- 修改：`.local-artifacts/start_dashboard_8765.pyw`（若发现运行路径偏差，仅本机）

- [ ] 执行前端目标测试与 TypeScript 构建；使用后台测试运行器执行 Python Dashboard/CLI 的短测试集，并轮询退出码和日志。
- [ ] 检查 `git diff --check`、`git status --short`、静态资源 manifest 与 Git 远端。
- [ ] 在迁移文档列出旧/新名称映射、Conda 环境保留说明、旧链接重定向说明和启动命令。
- [ ] 将本次与此前未提交的 Dashboard 修复按逻辑拆分为小提交，推送到重命名后的远端，并创建或更新对应 PR；通过检查后合并到 `main`。
- [ ] 最终验证新仓库默认分支、新本地路径、Dashboard 健康端点和已交付任务内容。
