# Distill-Everything 开源发布完善与 macOS 正式文档支持设计

## 背景

Distill-Everything 已具备多平台 Source Adapter、可恢复流水线、隔离 Worker、中文 Dashboard 与 GitHub Python CI。发布前仍存在四类缺口：主工作树与远端 `main` 分叉、前端没有远端门禁、开源协作资料不足、以及 macOS 只有零散安装说明而没有正式支持边界。

本设计把项目提升到可公开发布的 Beta 标准；不会在没有真实 macOS 设备验收的前提下，宣称 B 站/抖音登录和 Apple Silicon ASR 与 Windows 完全等价。

## 目标

1. 使主项目目录安全收敛到 GitHub `main`，保留当前本地提交和未跟踪内容的可恢复副本。
2. 让 GitHub CI 同时覆盖 Python、Dashboard 前端构建和 macOS 基础安装/测试。
3. 将 macOS 作为正式文档支持的平台，提供可复制的安装、启动、测试、已验证能力和限制说明。
4. 补齐贡献、安全、版本记录、Issue/PR 模板与演示素材，让陌生开发者可以正确安装、反馈和贡献。
5. 清除活动文件中的遗留 `Distill-Anyone` 产品名称（Conda 环境路径的兼容例外除外）。

## 非目标

- 不重命名 `C:\\Coding\\Anaconda\\envs\\Distill-Anyone`。
- 不在没有真实 macOS 验收的情况下为扫码登录、Playwright Chromium 或 FunASR MPS 给出“全功能稳定”的承诺。
- 不改动已有任务 `data`、`output`、凭据、浏览器 profile 或用户蒸馏产物。
- 不引入云端服务、遥测、账号系统或跨设备同步。

## 支持策略

| 能力 | Windows | macOS |
| --- | --- | --- |
| CLI、文档蒸馏、Markdown/Skill/RAG 输出 | 正式支持 | 正式文档支持 |
| Dashboard | `pythonw.exe` 隐藏启动器 | `python main.py dashboard --no-open` 前台终端启动 |
| 前端构建与单元测试 | CI 覆盖 | CI 覆盖 |
| 打开产物目录 | Explorer | Finder（`open`） |
| B 站/抖音扫码与 Playwright | 已本机验证 | 需要真实 macOS 浏览器验收 |
| FunASR / Apple Silicon MPS | 不适用 | 需要真实 Apple Silicon 验收 |

这里的“正式文档支持”表示安装、启动、退出、故障排查与 CI 基础测试均有维护者负责；它不表示所有第三方平台登录行为在所有 macOS 版本、CPU 架构和网络环境中均已认证。

## 架构与实现边界

### 1. 主工作树收敛

主目录存在历史本地提交与未跟踪文件，不能通过强制重置处理。执行过程先创建只读式保护分支和带时间戳的 stash 记录，再在专门步骤中将远端 `main` 合并进本地 `main`。若发生文本冲突，只合并有明确语义的代码与文档；难以判断的旧本地改动保留在保护分支/stash，不覆盖远端发布版本。

完成标准是：项目根目录的 `main` 含最新 `origin/main`，运行工作树和主工作树指向一致的发布代码；保护分支与 stash 名称在迁移记录中可追溯。

### 2. CI 分层

保留 Python 3.11 全量 pytest 工作流，新增：

- Ubuntu 上的 Dashboard `npm ci`、Vitest、TypeScript 构建与发布静态文件一致性校验；
- macOS 上的 Python 安装与基础测试集，验证路径、文件打开适配及不依赖 Windows 创建标志的代码；
- Node 24 作为 Dashboard 构建环境，遵从项目既有锁文件与 `package.json` engines 约束。

CI 不启动真实浏览器登录、不下载用户媒体、不调用外部 LLM，也不读取任何凭据。

### 3. 文档与协作体验

README 拆出“支持矩阵”“三分钟上手”“Dashboard 启动方式”“平台登录免责声明”。新增中文 `CONTRIBUTING.md`、`SECURITY.md`、`CHANGELOG.md`、GitHub Issue/PR 模板；所有公开文档默认中文，必要的命令和变量保留英文原文。

`docs/平台支持与故障排查.md` 以 Windows/macOS 分栏描述依赖、启动、测试与已知限制。macOS 不引用 `.cmd`、PowerShell 或 Windows Conda 路径。

### 4. 演示素材

使用脱敏的本地 Dashboard 示例数据生成一张任务作战台截图，并将图片和简短结果说明放入 `docs/images/` 与 README。截图不得含 Cookie、二维码、绝对用户目录、LLM API Key、浏览器 profile 或原始 Worker 日志。

### 5. 品牌清理

通过受限 `rg` 清单检查运行代码、README、脚本、工作流和活动文档。允许遗留旧名仅出现在：历史迁移记录、旧仓库重定向说明，以及 Conda 环境兼容路径。`.gitignore` 中的旧项目目录规则改为新名称或删除。

## 验收标准

- GitHub `main`、主工作树和 Dashboard 运行工作树均可识别当前发布提交；保护点可列出且不含用户凭据。
- GitHub Actions 的 Python、前端、macOS 基础检查均为成功状态。
- README 和平台支持文档给出 Windows/macOS 的准确命令与能力边界。
- 新增协作、安全、变更记录、Issue/PR 模板可在 GitHub 根目录直接发现。
- `rg` 只在允许的兼容/历史位置找到旧产品名；无泄露凭据或绝对用户路径的演示素材。
- Dashboard 健康端点、现有任务列表、产物输出目录仍可用。

## 风险与回退

- 主工作树合并冲突：保留保护分支与 stash，停止继续写入主工作树；运行工作树和 GitHub `main` 不受影响。
- macOS CI 的依赖安装失败：先将失败限定到依赖矩阵，不降低 Windows 发布质量；修复依赖约束后再标记 macOS 基础支持完成。
- 截图包含敏感信息：不提交，改用专用脱敏示例数据重新生成。
- 第三方登录差异：在文档中降级为“需要设备验收”，不伪造成功状态。
