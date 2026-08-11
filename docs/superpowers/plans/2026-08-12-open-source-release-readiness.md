# Distill-Everything 开源发布完善实施计划

> **给 Goal 执行器：** 必须单主代理串行执行本计划；逐张任务卡完成“检查 → 最小变更 → 验证 → 小提交 → 勾选复选框”。严禁启用子代理、并发编辑或并行任务卡。

**目标：** 将 Distill-Everything 发布为可公开分享的 Beta：主工作树可安全收敛、Windows/macOS 有准确的正式文档支持、CI 覆盖 Python/前端/macOS 基础路径，且开源协作资料齐备。

**架构：** 保持本地优先的 Python + FastAPI + React 架构不变。Windows 继续使用隐藏 `pythonw.exe` Dashboard 启动器；macOS 使用前台 `python main.py dashboard --no-open`，通过文档与 CI 提供可维护的基础支持，不承诺未经真实设备验证的扫码登录和 Apple Silicon ASR 完整兼容性。

**技术栈：** Python 3.11、pytest、FastAPI/Uvicorn、React、TypeScript、Vite、Vitest、GitHub Actions、Node 24。

## 全局约束

- 所有新建或大幅修改的公开文档默认使用中文；命令、文件名、环境变量保留原文。
- 禁止移动或重命名 `C:\Coding\Anaconda\envs\Distill-Anyone`；新变量使用 `DISTILL_EVERYTHING_PYTHON`。
- 禁止直接执行 `pytest` 或 `python -m pytest`。Windows 本地 Python 测试仅可通过 `scripts/run-pytest-background.cmd`，以 `cmd /d /c start "" /b` 后台启动并轮询 `.local-artifacts/test-runs/latest.exitcode` 与日志。
- Dashboard 仅可通过 `pythonw.exe` + `Start-Process -WindowStyle Hidden` 在 Windows 启动；不得创建可见 CMD 或使用任务计划程序。
- 不读取、不提交或打印 `.env`、`data/`、`output/`、浏览器 profile、Cookie、二维码、API Key、原始 Worker 日志或用户绝对路径。
- 当前运行工作树：`C:\Users\Administrator\Desktop\Vibe\Distill-Everything-dashboard-runtime`；主工作树：`C:\Users\Administrator\Desktop\Vibe\Distill-Everything`。
- GitHub 推送、创建 PR、合并 `main` 已获授权。出现普通构建/测试失败、端口占用或静态资源过期时自行修复；仅在无法无损处理的主工作树语义冲突、凭据/数据不可读或 GitHub 权限拒绝时停止。

---

### 任务 1：恢复并保护主工作树

**文件：**
- 修改：`C:\Users\Administrator\Desktop\Vibe\Distill-Everything` 的 Git 引用与工作树元数据（由 Git 写入）
- 创建：`docs/本地工作树收敛记录.md`

**接口：**
- 输入：主工作树 `main`、`origin/main`、既有 `stash@{0}: preserve-local-pre-distill-everything-sync`
- 输出：主工作树包含最新 `origin/main`；保护分支和 stash 可追溯，不删除用户本地内容。

- [x] 记录 `git -C <主目录> status --branch --short`、`git log --left-right --oneline origin/main...main`、`git stash list` 与 `git worktree list --porcelain`；不得打印 stash 内容。
- [x] 创建保护分支 `backup/pre-release-main-20260812`，指向当前主工作树 `HEAD`；确认分支存在后才继续。
- [x] 不执行 `reset --hard`、`clean` 或 `stash drop`。先用 `git merge-tree` 或等价只读方式定位主工作树独有提交与 `origin/main` 的冲突文件。
- [x] 若所有冲突均为可明确合并的文本，执行 `git merge --no-ff origin/main -m "merge: synchronize release main"`，逐个解决并运行 `git diff --check`；若任一冲突包含用户业务逻辑且无法判断，保留主工作树在保护分支，不覆盖，改以新的干净工作树作为官方主目录并在记录中说明。
- [x] 写入 `docs/本地工作树收敛记录.md`：记录保护分支名、stash 名、采用的收敛方式、最终 `HEAD` 与 `origin/main` 关系；禁止写入绝对用户路径或 stash 内容。
- [x] 验证主工作树与运行工作树都可执行 `git status --short`；运行工作树不出现未提交发布代码。
- [ ] 小提交：`docs: record primary worktree convergence`。

### 任务 2：建立跨平台 CI 门禁

**文件：**
- 修改：`.github/workflows/pytest.yml`
- 创建：`.github/workflows/dashboard.yml`
- 测试：`dashboard/src/app/AppShell.test.tsx`、`tests/dashboard/test_series_control.py`

**接口：**
- 输入：`requirements.txt`、`dashboard/package-lock.json`、`scripts/build_dashboard.py`
- 输出：Python CI 与 Dashboard CI 都对 push、PR 触发；macOS 基础 Python 测试不依赖真实登录或外部模型。

- [ ] 为现有 Python 工作流添加清晰的 job 名称：`python-linux` 保持 Ubuntu + Python 3.11 全量测试；`python-macos` 使用 macOS + Python 3.11 仅运行 `tests/dashboard/test_series_control.py tests/dashboard/test_artifact_api.py tests/outputs/test_episodes.py -q`。
- [ ] macOS job 安装方式固定为：升级 pip、安装 CPU PyTorch、`pip install -r requirements.txt pytest`；不执行 Playwright 浏览器下载、真实扫码、外部 LLM、媒体下载。
- [ ] 新建 Dashboard 工作流，使用 `actions/setup-node@v4` 与 `node-version: 24`；在 `dashboard/` 依次执行 `npm ci`、`node node_modules/vitest/vitest.mjs run src/app/AppShell.test.tsx src/features/mission-control/TaskControlCard.test.tsx`、`node node_modules/typescript/bin/tsc -b`、`node node_modules/vite/bin/vite.js build`。
- [ ] 在仓库根目录使用 Python 调用 `scripts/build_dashboard.py --from-dist` 与 `--check`，确保提交的静态资源 manifest 与前端源一致。
- [ ] 在 Windows 本地通过后台测试运行器运行 `tests/dashboard/test_series_control.py tests/dashboard/test_artifact_api.py -q`，轮询退出码为 0；通过固定 Node 24 执行同一组前端目标测试和构建。
- [ ] 小提交：`ci: verify dashboard and macos basics`。

### 任务 3：补齐 macOS 正式文档支持与发布指引

**文件：**
- 修改：`README.md`
- 创建：`docs/平台支持与故障排查.md`
- 修改：`docs/迁移到-Distill-Everything.md`

**接口：**
- 输入：`main.py dashboard --help`、`scripts/README.md`、`src/dashboard/api/artifacts.py`
- 输出：Windows/macOS 的安装、启动、测试、限制与故障排查命令准确且可复制。

- [ ] 在 README 增加“支持矩阵”，精确区分 Windows 正式支持、macOS 正式文档支持、B 站/抖音扫码与 Apple Silicon ASR 的设备验收状态。
- [ ] 将 README 安装流程分为 Windows PowerShell 与 macOS zsh 两个代码块；macOS 使用 `python3 -m venv .venv`、`source .venv/bin/activate`、`brew install ffmpeg`、`cp config.example.env .env`、`python -m playwright install chromium`。
- [ ] 在 README 增加 Dashboard 启动表：Windows 指向隐藏启动器；macOS 指向 `python main.py dashboard --port 8765 --no-open` 并说明通过浏览器访问 `http://127.0.0.1:8765/`。
- [ ] 创建 `docs/平台支持与故障排查.md`，包含：依赖检查、Node/ffmpeg/Playwright 问题、端口 8765 占用、Finder/Explorer 打开产物行为、macOS 真实扫码与 MPS 未验收边界、如何提供脱敏 issue 信息。
- [ ] 修改迁移说明，链接支持矩阵与故障排查文档，并把 Windows 专用后台 pytest 规则明确为 Codex Desktop Windows 的稳定性约束，而非 macOS 用户的通用命令。
- [ ] 使用 `rg` 检查 macOS 文档段落不含 `pythonw.exe`、`.cmd`、`Start-Process` 或 Windows Conda 绝对路径；检查所有新增文档为 UTF-8 中文。
- [ ] 小提交：`docs: document macos support boundaries`。

### 任务 4：补齐开源协作、安全与发布材料

**文件：**
- 创建：`CONTRIBUTING.md`
- 创建：`SECURITY.md`
- 创建：`CHANGELOG.md`
- 创建：`.github/ISSUE_TEMPLATE/bug_report.yml`
- 创建：`.github/ISSUE_TEMPLATE/feature_request.yml`
- 创建：`.github/pull_request_template.md`
- 创建：`docs/images/dashboard-workbench.png`
- 修改：`README.md`

**接口：**
- 输入：MIT `LICENSE`、现有 CI 工作流、Dashboard 静态页面
- 输出：贡献者能复现环境、报告问题、不泄露敏感信息；README 能展示脱敏的产品界面。

- [ ] 新建中文 `CONTRIBUTING.md`：包含分支/PR 流程、Windows 后台 pytest 规则、Node 24 前端检查、不得提交的敏感文件、平台适配器与输出层的边界。
- [ ] 新建中文 `SECURITY.md`：说明项目仅监听 `127.0.0.1`、凭据不进入 Dashboard/SSE、如何私下报告漏洞、报告中禁止附带 Cookie/API Key/二维码/完整日志；不承诺不具备的 SLA。
- [ ] 新建中文 `CHANGELOG.md`，采用 Keep a Changelog 风格，登记 `0.4.0-beta` 的多平台适配、受控 Worker、Dashboard、macOS 文档支持和已知限制。
- [ ] 创建两个 GitHub YAML Issue 表单：Bug 表单收集版本、系统、复现步骤和脱敏日志；Feature 表单收集使用场景、平台、期望输出。两者都提示不得上传凭据、二维码或媒体原文件。
- [ ] 创建 PR 模板，要求影响范围、测试证据、文档变更、隐私检查和 UI 截图（若涉及界面）。
- [ ] 使用脱敏的本地 Dashboard 状态启动页面并生成 `docs/images/dashboard-workbench.png`；图片只显示 UI 模板或公开示例，不能显示任务真实标题、BV 号、绝对保存位置、二维码、Cookie 或日志。README 添加图片和“三分钟上手”链接。
- [ ] 用 `git grep -nE '(SESSDATA|bili_jct|sk-[A-Za-z0-9_-]{8,}|ANTHROPIC_API_KEY=.{8,}|OPENAI_API_KEY=.{8,})'` 检查新增文件；只允许测试中的显式脱敏占位符，其他命中必须在提交前移除。
- [ ] 小提交：`docs: add contributor release materials`。

### 任务 5：清理遗留品牌并进行发布验收

**文件：**
- 修改：`.gitignore`
- 修改：`README.md`
- 修改：`docs/superpowers/plans/2026-08-12-open-source-release-readiness.md`

**接口：**
- 输入：活动代码、脚本、工作流、公开文档、GitHub PR 检查状态
- 输出：唯一保留旧品牌的位置有明确兼容/历史理由；所有发布检查通过并已合并。

- [ ] 使用受限 `rg` 扫描 `README.md`、`main.py`、`src/`、`scripts/`、`dashboard/`、`.github/`、公开根文档；将 `.gitignore` 的 `Distill-Anyone/` 规则改为 `Distill-Everything/` 或删除。
- [ ] 对每个剩余 `Distill-Anyone` 命中标注理由：仅允许 Conda 环境兼容路径、旧仓库重定向、迁移设计/历史记录；其他运行标识必须替换。
- [ ] 使用 Windows 后台测试运行器运行短 Python 回归集，固定 Node 24 执行 Vitest、TypeScript、Vite 构建和静态资源 `--check`；请求 Dashboard 健康端点验证 `status=ok`、`static_compatible=true`。
- [ ] 对主工作树、运行工作树分别运行 `git diff --check` 与 `git status --short`；确认 `data`、`output` 未被纳入暂存区，Dashboard 的现有任务/产物接口仍可读取。
- [ ] 推送当前分支，创建 PR，等待 GitHub Python、macOS、Dashboard 检查均成功后合并 `main`；不得因未完成 CI 提前宣布发布成功。
- [ ] 将本计划所有完成项改为 `- [x]`，记录 PR 链接、关键测试结果与主工作树保护点；小提交：`docs: record beta release readiness`。
