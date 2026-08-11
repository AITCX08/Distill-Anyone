# Distill-Everything 全量改名与本地迁移 Goal 实施计划

> **Goal 执行方式：** 一个 Goal 仅由单主代理串行执行。严格按任务 1 至任务 7 的顺序推进；每次只处理一张任务卡，完成“检查 → 最小变更 → 验证 → 小提交 → 更新本计划复选框”后才进入下一张。禁止启用子代理、并行执行流或并发编辑同一文件。

**目标：** 将 Distill-Anyone 安全迁移为 Distill-Everything，并保持已有数据、产物和 Dashboard 可用。

**架构：** GitHub、Git 工作树和本地运行目录按“停止服务 → 校验 → 移动 → 更新引用 → 验证”的顺序迁移。Python `src` 包和 Conda 环境保持不变；项目对外标识、脚本变量和运行路径改为新名称。

**技术栈：** Git/GitHub、PowerShell、Python 3.14 与既有 Conda 解释器、FastAPI/Uvicorn、React/Vite、Windows 本地文件系统。

## 全局约束

- 全部新增或更新的用户文档使用中文。
- 不移动 `C:\Coding\Anaconda\envs\Distill-Anyone`。
- 不删除 `data`、`output`、Git 历史或用户未提交改动。
- Dashboard 必须使用 `pythonw.exe` 隐藏启动；不得通过可见 CMD、任务计划程序或直接 `pytest` 验证。
- Python 测试仅使用项目的后台测试运行器或直接调用短小、无 pytest 依赖的回归测试函数；前端测试直接以 `C:\Coding\node\node.exe` 启动 Vitest。

## Goal 自主执行协议

### 状态与连续性

- 本文件是唯一执行状态图；开始时读取全部复选框，从第一张未完成任务卡继续。
- 每完成一个步骤立即将对应复选框改为 `- [x]`；完成一张任务卡后提交该卡产生的可提交文件。
- Goal 被中断或桌面端重启后，先读取本文件、`git status --short`、`git worktree list --porcelain` 与 Dashboard 健康状态，再从第一项未完成步骤恢复；不得重复已完成的移动、GitHub 改名或提交。
- 所有操作采用幂等检查：GitHub 已是新仓库名、远端已是新 URL、目录已在新路径、服务已监听 8765 时，记录现状后跳过重复动作。

### 非阻塞原则

- 普通构建/测试失败、端口暂未释放、静态资源过期、工作树元数据需要 repair、远端 URL 已自动重定向等情况，主代理必须自行诊断、修复和重新验证，不向用户索要常规确认。
- GitHub 改名、推送、创建 PR 与合并 `main` 已获授权；在仓库权限正常时直接执行。
- 只在以下情形停止并报告：新目标目录已存在且内容未知；源 `data/output` 不可读取；迁移前后任务/产物计数不一致且无法恢复；GitHub 权限拒绝且无可用替代凭据；或移动后回退也无法恢复路径。

### Windows 与稳定性约束

- 不执行 `pytest`、`python -m pytest`，也不将 pytest 附着到 Codex 命令流。Python 测试只走项目后台测试运行器并轮询日志/退出码，或调用不依赖 pytest 的短小测试函数。
- 仅用 `pythonw.exe` + `Start-Process -WindowStyle Hidden` 启动 Dashboard；不得运行 `.cmd`、`cmd /c start`、任务计划程序或任何会创建可见终端的启动方式。
- 不启动子代理、不做长时间阻塞轮询；单次等待不超过 60 秒，并用健康端点/退出码/文件状态判断完成条件。

### 每张任务卡的完成定义

- 每张卡必须有命令输出或文件状态证明，不凭推断标记完成。
- 小提交只包含该卡的文件；既有未提交 Dashboard 修复必须保持原样，直至任务 7 按逻辑单独提交。
- 提交前运行 `git diff --check`，确认没有密钥、Cookie、二维码、绝对私密凭据或无关文件被加入暂存区。

---

### 任务 1：迁移前盘点与保护点

- [x] **任务 1 完成：** 已保存迁移前盘点并确认可安全进入远端迁移。

**文件：**
- 创建：`docs/superpowers/migrations/2026-08-11-distill-everything-preflight.md`
- 修改：无

- [x] 记录当前 Git 分支、远端、主工作树与 Dashboard 工作树绝对路径。
- [x] 记录 `data`、`output`、`.local-artifacts/start_dashboard_8765.pyw` 是否存在，并统计已完成任务状态文件与交付产物数量。
- [x] 使用 `Get-NetTCPConnection -LocalPort 8765 -State Listen` 确认当前 Dashboard 监听进程；只停止该进程。
- [x] 若任何目标新路径已经存在，停止迁移并报告冲突，不覆盖目录。
- [x] 小提交：`docs: record distill-everything migration preflight`

### 任务 2：GitHub 仓库与 Git 远端迁移

- [x] **任务 2 完成：** GitHub 与本地 `origin` 都已切换至新仓库地址。

**文件：**
- 修改：`.git/config`（由 Git 写入，不手工编辑）

- [x] 在 GitHub 将 `AITCX08/Distill-Anyone` 重命名为 `AITCX08/Distill-Everything`。
- [x] 执行 `git remote set-url origin https://github.com/AITCX08/Distill-Everything.git`。
- [x] 用 GitHub API 验证新远端可读，并记录仓库重命名结果。（本机 Git TLS 短暂握手失败，不影响 API 证据。）
- [x] 验证新仓库是 GitHub 规范地址；旧地址仅由 GitHub 重定向兼容，不作为运行配置。

### 任务 3：移动两个 Git 工作树与本地运行数据

- [x] **任务 3 完成：** 两个工作树、数据和产物均在新路径且计数一致。

**文件：**
- 修改：Git worktree 元数据（由 `git worktree move` 写入）
- 移动：`C:\Users\Administrator\Desktop\Vibe\Distill-Anyone` → `C:\Users\Administrator\Desktop\Vibe\Distill-Everything`
- 移动：`C:\Users\Administrator\Desktop\Vibe\Distill-Anyone-dashboard-runtime` → `C:\Users\Administrator\Desktop\Vibe\Distill-Everything-dashboard-runtime`
- 移动：新主目录中的 `data` 与 `output` 保持其相对位置

- [x] 先执行 `git worktree list --porcelain` 确认两个工作树受 Git 管理且路径与盘点一致。
- [x] 使用 `git worktree move` 移动 Dashboard 工作树；主工作树由受控目录移动后立刻运行 `git worktree repair` 校正元数据。
- [x] 将主目录下 `data` 与 `output` 一并保留在新主目录中；迁移后验证状态文件、凭据目录和产物文件仍可读取。
- [x] 使用 `git -C <新路径> status --short` 验证未提交修改仍完整存在。
- [x] 移动后 Git 元数据、状态文件、产物计数均通过校验，不需要回退。

### 任务 4：替换运行标识、脚本与活跃文档

- [x] **任务 4 完成：** 活跃代码、脚本与用户文档不再使用旧产品标识。

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

- [x] 先用 `rg` 生成当前运行代码、README、脚本和活跃导航中的旧名称清单；历史 `docs/superpowers/plans/**` 与 `docs/superpowers/specs/**` 不在批量替换范围。
- [x] 将用户可见名称统一替换为 `Distill-Everything`，机器可读名称统一替换为 `distill-everything`。
- [x] 将 `DISTILL_ANYONE_PYTHON` 改为 `DISTILL_EVERYTHING_PYTHON`，并更新示例与后台测试运行器的读取逻辑。
- [x] 保持所有 Python 导入 `src.*` 不变；未重命名 `src` 目录。
- [x] 新增短回归断言，证明 `main.py --help` 输出新项目名称、脚本读取新变量。
- [x] 小提交：`refactor: rename product identifiers to distill-everything`（`a972751`）。

### 任务 5：更新 Dashboard 品牌与发布静态资源

- [ ] **任务 5 完成：** Dashboard 源码和发布静态资源均显示新品牌并通过构建。

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

- [ ] **任务 6 完成：** 隐藏启动器从新路径运行且 Dashboard 可读取已有任务。

**文件：**
- 修改：`<新运行工作树>/.local-artifacts/start_dashboard_8765.pyw`（本机运行配置，不提交）
- 修改：`<新运行工作树>/.local-artifacts/dashboard-launcher.log`（仅在异常时产生，不提交）

- [ ] 将 `ROOT`、`DATA_DIR`、`OUTPUT_DIR` 更新为新项目路径。
- [ ] 保持解释器为 `C:\Coding\Anaconda\envs\Distill-Anyone\pythonw.exe`。
- [ ] 使用 `Start-Process -WindowStyle Hidden` 启动启动器；不得调用 `.cmd` 或创建可见终端。
- [ ] 请求 `http://127.0.0.1:8765/api/v1/health`，预期 `status=ok` 与 `static_compatible=true`。
- [ ] 校验 SSE 快照与 `/api/v1/jobs/imported-series-BV18bLkztE7R/items`：已有 8 集的标题、BV 号、完成时间和交付目录仍存在。

### 任务 7：全量回归、发布与迁移记录

- [ ] **任务 7 完成：** 验收、发布、合并与迁移文档均已完成。

**文件：**
- 创建：`docs/迁移到-Distill-Everything.md`
- 修改：`README.md`
- 修改：`.local-artifacts/start_dashboard_8765.pyw`（若发现运行路径偏差，仅本机）

- [ ] 执行前端目标测试与 TypeScript 构建；使用后台测试运行器执行 Python Dashboard/CLI 的短测试集，并轮询退出码和日志。
- [ ] 检查 `git diff --check`、`git status --short`、静态资源 manifest 与 Git 远端。
- [ ] 在迁移文档列出旧/新名称映射、Conda 环境保留说明、旧链接重定向说明和启动命令。
- [ ] 将本次与此前未提交的 Dashboard 修复按逻辑拆分为小提交，推送到重命名后的远端，并创建或更新对应 PR；通过检查后合并到 `main`。
- [ ] 最终验证新仓库默认分支、新本地路径、Dashboard 健康端点和已交付任务内容。
- [ ] 在最终输出中按任务卡汇报证据、提交、PR/合并结果和剩余风险。
