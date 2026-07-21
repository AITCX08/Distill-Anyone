# 本地蒸馏 Dashboard 设计

日期：2026-07-21

状态：设计已确认，待书面规格复核

依赖规格：`2026-07-21-multi-platform-distillation-design.md`

## 1. 目标

为 Distill-Anyone 提供一个美观、可发布、跨平台的本地单用户 Dashboard。它把原 CMD 监控器中的核心反馈完整搬到浏览器：总进度、固定活跃作品行、当前阶段、Active x/3、完成/失败/重试/unsupported 数量、总 ETA 和最慢活跃任务 ETA，同时提供创建任务、平台登录、安全暂停、恢复、单项重试和产物预览。

Dashboard 是现有 CLI 的并列呈现层，不是第二套流水线。CLI、Rich Live 和 Dashboard 必须通过同一个应用服务读取同一个状态和 `ProgressSnapshot`，不得分别计算完成率、ETA 或任务状态。

## 2. 已确认的产品决策

- 使用模型：本地单用户控制台。
- 启动方式：`python main.py dashboard`，自动打开默认浏览器。
- 网络边界：只监听 `127.0.0.1`，v0.4 不支持局域网或公网绑定。
- 技术路线：FastAPI + React/Vite + Fluent UI + Server-Sent Events。
- 抖音登录：Dashboard 发起登录，独立 Chromium 窗口完成扫码；二维码和 Cookie 不经过 Dashboard。
- 视觉方向：赛博工业任务作战台，深黑背景、青色运行态、琥珀警告、红色失败、等宽数字与克制动效。
- Node 仅用于开发和构建；发布包内置静态资源，最终用户运行 Dashboard 不需要 Node。

## 3. 范围

### 3.1 v0.4 包含

- 启动、健康检查和浏览器自动打开。
- 新建创作者蒸馏任务和 dry-run 预检。
- 当前任务实时监控。
- 历史任务和作品状态查询。
- 安全暂停、恢复、整批失败项重试和单项重试。
- 平台能力、依赖、认证状态与外部浏览器登录。
- episode、SKILL.md 和 RAG metadata 的只读预览。
- 复制文本和在操作系统文件管理器中定位受控输出路径。
- SSE 断线重连、快照恢复和脱敏事件流。
- 桌面优先的响应式布局、键盘可达性和 reduced-motion。
- 前端构建产物随 Python 发布物分发。

### 3.2 v0.4 不包含

- 用户账号、角色、权限、多租户或远程访问。
- 局域网/公网绑定、HTTPS 终止或远程认证。
- 删除任务、批量删除文件或清空用户数据。
- 在线编辑 Markdown、Skill 或状态 JSON。
- 在网页内显示抖音二维码、Cookie、API key 或浏览器 profile。
- 原生桌面壳、Electron、移动 App 或后台系统服务安装器。
- 把完整视频、音频或图片通过浏览器提供下载。
- OCR、小红书等核心规格之外的新平台能力。

## 4. 技术架构

```text
Browser
  ├─ GET/POST /api/v1/*
  └─ GET /api/v1/events  (SSE)
           │
           ▼
FastAPI Dashboard Host
  ├─ API schemas + security
  ├─ SSE adapter
  └─ bundled React static assets
           │
           ▼
DistillationService
  ├─ command handlers
  ├─ query handlers
  ├─ JobLeaseManager
  └─ EventHub
           │
           ├─ PlatformManager
           ├─ DistillationEngine
           ├─ JobStateStore
           └─ OutputManager
```

### 4.1 共享应用服务

新增 `src/application/`，作为 CLI 与 Dashboard 的唯一业务入口：

```text
src/application/
  __init__.py
  service.py        # DistillationService facade
  commands.py       # create/pause/resume/retry/login
  queries.py        # platforms/jobs/items/artifacts
  events.py         # immutable ApplicationEvent 和 EventHub
  leases.py         # job 排他 lease、heartbeat、陈旧 lease 恢复
  errors.py         # 面向呈现层的统一错误
```

`DistillationService` 的公共方法返回领域 DTO，不返回 FastAPI response、Click context 或 React 专用结构。CLI 将领域 DTO 渲染成终端文本；FastAPI 将同一 DTO 映射为版本化 JSON。

所有变更命令接收 `expected_revision`。状态 revision 不匹配时返回冲突，避免浏览器旧页面覆盖已经变化的作业。

### 4.2 Job lease

同一 job 同时只能有一个执行者。lease 文件位于 job 数据目录，包含随机 owner token、PID、启动时间和 heartbeat：

- CLI 和 Dashboard 启动作业前必须获取 lease。
- heartbeat 在作业运行时定期更新。
- 正常暂停或退出释放 lease。
- 进程已不存在且 heartbeat 超时后才允许恢复陈旧 lease。
- 活进程持有的 lease 不得被 `--retry-failed` 或网页按钮抢占。
- Windows 与 POSIX 使用同一接口，并分别测试 PID liveness 行为。

### 4.3 Dashboard Host

```text
src/dashboard/
  __init__.py
  app.py            # create_dashboard_app()
  server.py         # uvicorn 生命周期、端口和浏览器打开
  schemas.py        # API request/response models
  security.py       # loopback、Origin、session/CSRF、CSP
  sse.py            # event serialization、heartbeat、reconnect
  api/
    health.py
    platforms.py
    jobs.py
    artifacts.py
  static/           # 经过验证的 React 构建产物
```

FastAPI 不直接导入具体 Douyin/Bilibili adapter，也不直接操作 `job_state.json`。所有读写都经过 `DistillationService`。

### 4.4 前端工程

```text
dashboard/
  package.json
  package-lock.json
  vite.config.ts
  tsconfig.json
  src/
    app/             # router、providers、shell
    api/             # client、SSE、由 OpenAPI 生成的类型
    features/
      mission-control/
      create-job/
      platforms/
      job-history/
      artifacts/
    components/      # 复用的状态和布局组件
    theme/           # Fluent tokens 与赛博主题
    test/            # mock server 和通用 fixture
```

Node build major 固定为 22，`package.json` 使用 `engines.node >=22 <23`，`package-lock.json` 锁定全部直接和传递依赖。React 源码构建后复制到 `src/dashboard/static/`；CI 验证重新构建没有未提交差异。发布物包含 static 目录，因此运行时不调用 npm、npx 或网络 CDN。

## 5. 启动与生命周期

新增命令：

```text
python main.py dashboard
python main.py dashboard --port 8765
python main.py dashboard --no-open
```

规则：

- host 固定为 `127.0.0.1`，不提供 `--host` 参数。
- 默认端口 8765；端口被占用时返回可操作错误，不自动扫描并隐藏实际端口。
- 默认在健康检查成功后打开浏览器；`--no-open` 只打印完整 URL。
- 浏览器关闭不影响后台作业。
- 收到正常终止信号时停止接收新命令，要求引擎在安全点落盘，关闭 SSE 后退出。
- 非正常退出依赖核心状态账本恢复；重新启动后历史任务立即可见，用户可选择恢复。
- Dashboard 进程不安装为系统服务，v0.4 不承诺终端窗口关闭后继续运行。

## 6. API 设计

所有接口位于 `/api/v1`。JSON 字段使用 `snake_case`，时间使用带时区 ISO 8601，状态值与核心状态机一致。

### 6.1 平台与认证

```text
GET  /api/v1/platforms
GET  /api/v1/platforms/{platform}/auth
POST /api/v1/platforms/{platform}/login
```

`POST .../login` 返回登录 operation ID，并启动独立 Chromium。前端通过 SSE 接收 `auth.updated`，同时可重新查询 auth endpoint。并发登录请求幂等复用同一未完成 operation。

### 6.2 作业

```text
POST /api/v1/jobs/preview
POST /api/v1/jobs
GET  /api/v1/jobs
GET  /api/v1/jobs/{job_id}
GET  /api/v1/jobs/{job_id}/items
POST /api/v1/jobs/{job_id}/pause
POST /api/v1/jobs/{job_id}/resume
POST /api/v1/jobs/{job_id}/retry-failed
POST /api/v1/jobs/{job_id}/items/{source_id}/retry
```

`preview` 对应 CLI dry-run，只做依赖/认证检查、target 解析和枚举，不下载、不调用 ASR/LLM、不创建 job。创建作业时客户端提交 preview fingerprint；目标内容或认证状态已变化时服务器要求重新预检。

暂停是协作式安全暂停：请求后状态先变为 `pause_requested`，活跃 item 在当前不可中断操作结束并写入安全 artifact 后进入 `paused`。按钮不得把“暂停请求已接受”误显示为“已经暂停”。

resume/retry 命令幂等；对不允许的状态返回 409 和当前状态。v0.4 不提供 cancel/delete endpoint。

### 6.3 产物

```text
GET  /api/v1/jobs/{job_id}/artifacts
GET  /api/v1/jobs/{job_id}/artifacts/{artifact_id}
POST /api/v1/jobs/{job_id}/artifacts/{artifact_id}/reveal
```

只允许读取白名单文本产物及 metadata。解析后的最终路径必须位于配置的 `output_dir` 或文本 artifact 目录内；拒绝 `..`、符号链接逃逸和任意绝对路径。`reveal` 只在本机文件管理器中定位已经验证的路径，不返回文件系统任意浏览能力。

## 7. SSE 实时事件

接口：

```text
GET /api/v1/events?job_id=<optional>
```

事件类型：

- `snapshot`：连接后或事件缺口时的完整平台/作业/进度快照。
- `job.updated`：作业状态、revision、总体进度和汇总计数。
- `item.updated`：固定 source_id 对应的阶段、进度、ETA 和简化错误。
- `trace.appended`：经过脱敏的终端式事件行。
- `auth.updated`：平台登录 operation 和 auth 状态。
- `server.draining`：服务准备退出。

每个事件包含单调递增 event ID、schema version 和 server timestamp。浏览器使用 `Last-Event-ID` 重连：

- EventHub 内存保留最近 1000 个事件。
- 事件仍在缓冲区时续发缺口。
- event ID 已过期时先发送 `snapshot`，再发送后续事件。
- 15 秒无业务事件时发送 SSE heartbeat comment。
- 慢客户端队列有界；溢出时丢弃增量并强制下一条为 snapshot，不阻塞流水线。

为恢复最近终端轨迹，每个 job 保存脱敏 JSONL 事件日志，单文件上限 5 MiB，保留 3 个轮转文件。读取时忽略崩溃留下的不完整末行。事件日志不得记录 Cookie、Authorization、API key、完整请求头、浏览器 profile 路径或原始异常对象。

## 8. 页面与交互

### 8.1 任务作战台

首页显示一个当前任务：

- 博主、平台、输出目标和 running/pausing/paused/partial 状态。
- 全部作品总进度和 `completed / enumerated`。
- enumerate、download、ASR、LLM、output 阶段轨道。
- 最多 3 条固定活跃 item 行；同一 source_id 始终复用同一 React key 和同一行。
- 每行显示序号、标题、作品 ID、阶段、真实百分比和简短状态。
- 下载阶段显示 `已下载字节 / 总字节`、近期吞吐速度和该下载的阶段 ETA；总字节未知时显示已下载字节和速度，不伪造百分比。
- ASR 阶段显示已处理音频时长/总时长和 RTF；LLM 阶段显示 cleaning 或 knowledge 子步骤，不用虚假 token 百分比填充未知进度。
- Active x/3、ASR RTF、总 ETA、最慢活跃 item ETA。
- completed、failed、retry、unsupported、queued 数量。
- 可折叠的实时 trace，不将同一 item 的阶段拆成多行进度条。

进度、阶段权重、ETA 和汇总值全部来自后端 `ProgressSnapshot`。前端只格式化，不重新估算。

### 8.2 新建蒸馏

单页表单流程：

1. 粘贴创作者链接，平台默认 auto。
2. 点击预检，显示平台、博主、登录状态、预计作品数、已知/新增/unsupported 数。
3. 选择 episodes、skill 或 both；both 为默认值。
4. 高级区域提供 worker 数、max active、重试、keep media、headful 和 RAG。
5. preview fingerprint 有效后才能启动。

默认值与 CLI 完全一致。表单不显示或编辑 API key、Cookie 和 profile 路径。

### 8.3 平台与登录

每个平台显示 enabled、缺失依赖、支持的 item types、认证状态和最后检查时间。Douyin 登录按钮打开独立 Chromium；页面展示 opening browser、waiting for scan、authenticated、expired、timeout 或 failed。timeout 不得伪装成未登录。

### 8.4 历史任务

按 updated time 倒序显示 running、pausing、paused、partial、completed 和 failed。支持按平台/状态筛选。详情页显示所有 item，并可筛选 failed、retry、unsupported、completed。仅失败项出现重试操作。

### 8.5 作品与产物

提供 episode、SKILL.md 和 RAG metadata 的只读预览、复制和 reveal。大文本采用虚拟化或分段加载，避免一次把全部 corpus 放入 DOM。没有产物时展示原因和当前处理阶段，不显示空白面板。

## 9. 视觉系统与响应式

使用 Fluent UI React 的可访问组件和焦点行为，通过单一深色主题覆盖 tokens：

- 页面背景：近黑蓝；面板：两级深色表面。
- 主运行色：青色；成功：薄荷绿；警告/重试：琥珀；失败：红色。
- 颜色必须同时配合图标、文字或状态名，不把颜色作为唯一信息。
- 标题和正文使用系统无衬线中文字体；ID、百分比、ETA、trace 使用等宽字体。
- 圆角保持 6—8 px，边框细而明确；网格背景和发光只用于作战台层级，不覆盖正文。
- 不使用紫色 AI 渐变、全屏玻璃拟态、无意义扫描线或持续闪烁动画。
- 动效仅用于进度变化、阶段切换、重连和错误反馈；`prefers-reduced-motion` 下关闭非必要动画。

断点：

- `>=1100px`：完整侧栏、作战台双栏、trace 位于右侧。
- `768—1099px`：侧栏折叠为图标，trace 移到活跃任务下方。
- `<768px`：单列监控和操作，所有关键进度可读且不横向溢出；复杂表格切换为列表。

目标是浏览器自适应，不承诺手机上长时间管理大型任务的最佳体验。

## 10. 安全与隐私

本地监听不是完整安全模型。Dashboard 仍实施以下保护：

- Uvicorn 只绑定 `127.0.0.1`；创建 app 时拒绝非 loopback 配置。
- 启动时生成随机本地 session；使用 `HttpOnly`、`SameSite=Strict` cookie。
- mutation endpoint 同时校验精确 Origin 和由同源 boot endpoint 提供的 CSRF token。
- CSP 默认 `default-src 'self'`，不使用外部脚本、字体、分析或 CDN。
- API 错误和 trace 先经过统一 redactor。
- Pydantic response model 使用显式字段，不直接序列化配置、异常或平台 raw metadata。
- artifact 路径返回稳定 ID 和相对显示路径，不向网页暴露浏览器 profile、凭据缓存或任意本机绝对路径。
- 打开文件夹前执行 realpath containment 检查。
- 状态变更记录 job ID、动作、时间和结果，不记录敏感参数。

## 11. 错误模型

API 错误结构：

```json
{
  "error": {
    "code": "auth_expired",
    "message": "抖音登录已过期，请重新登录后恢复任务。",
    "retryable": false,
    "action": "login",
    "trace_id": "local-01J..."
  }
}
```

规则：

- 4xx 表示请求、revision、状态、认证或安全边界问题；5xx 表示未预期的服务失败。
- 原始 traceback 只写入本地开发日志，网页不展示。
- 登录过期时停止接收新下载，保留已经完成的 artifact，并提供重新登录后 resume。
- SSE 断线保留最后画面并显示 reconnecting；恢复后以 snapshot 为准。
- lease 冲突显示当前执行者类型和 heartbeat 时间，不提供强制抢占按钮。
- 作业级错误与 item failed 分开展示。
- loading、empty、offline、reconnecting、pausing、paused、partial 和 unsupported 都有明确状态组件。

## 12. 测试策略

### 12.1 Python

- `DistillationService` command/query 不依赖 FastAPI 或 Click。
- lease 获取、heartbeat、陈旧恢复、活 lease 冲突和跨平台 PID 检测。
- API request/response schema、revision 冲突和幂等命令。
- SSE 首次 snapshot、增量、Last-Event-ID、缓冲区过期、heartbeat 和慢客户端。
- login operation 幂等、timeout、auth expired 和可操作错误。
- Origin/session/CSRF/CSP/loopback 检查。
- redactor 覆盖 Cookie、Authorization、API key、profile 和敏感路径。
- artifact allowlist、`..`、绝对路径和符号链接逃逸。
- static fallback、SPA route 和无构建产物时的启动错误。

### 12.2 React

使用 Vitest、Testing Library 和 mock API/SSE fixture：

- 同一 source_id 在阶段变化后保持同一任务行。
- total/item progress、Active x/3、计数和双 ETA 只渲染服务端值。
- SSE reconnecting、snapshot reset 和错误恢复。
- pause_requested 与 paused 文案/按钮不同。
- failed 单项重试、unsupported 无重试按钮。
- 新建任务 preview fingerprint 和高级默认值。
- 登录 operation 状态与外部浏览器提示。
- loading、empty、partial、offline 和 artifact 缺失。
- 键盘焦点、aria label、对比度和 reduced-motion。
- 三个响应式断点不产生核心内容横向溢出。

### 12.3 契约与端到端

- 从 FastAPI OpenAPI schema 生成 TypeScript types，CI 检查生成结果无漂移。
- 浏览器端到端测试全部使用本地 fixture，不访问真实 Bilibili/Douyin 或 LLM。
- 覆盖新建 → 运行事件 → 暂停 → 恢复 → 单项失败 → 重试 → partial/completed。
- 覆盖刷新页面和 SSE 断线后的 snapshot 恢复。
- 覆盖登录按钮发起 operation，但 mock 外部 Chromium。
- 在 1440×900、1024×768、390×844 做关键页面截图回归。
- 构建 static 后，在没有 npm/node 命令可用的子进程环境中运行 Dashboard Python smoke test。

## 13. 构建、打包与发布

- Python requirements 增加受限 minor 版本的 FastAPI 和 Uvicorn。
- 前端所有依赖由 `package-lock.json` 锁定；禁止运行时 `npx -y`。
- `npm run build` 输出可复现 static；构建命令失败不得沿用过期 bundle。
- static manifest 包含前端 commit/build hash，健康接口报告 API/static schema 是否兼容。
- Python 发布配置显式包含 `src/dashboard/static/`。
- README 说明普通用户无需 Node；只有修改前端的贡献者需要 Node 22。
- DEVELOPMENT 说明生成 API 类型、运行前端测试、构建 static 和验证无 diff 的命令。
- 发布检查包含 Python tests、frontend tests、frontend build、E2E、无 Node smoke、CLI help、Dashboard health 和敏感信息扫描。

## 14. 实施边界

Dashboard 是独立实施子项目，开始前必须先具备以下稳定核心接口：

1. 平台注册表与统一 `SourceItem`。
2. 可恢复 `JobStateStore` 和 revision。
3. `ProgressSnapshot`、阶段进度和双 ETA。
4. 可被应用服务调用的 start/pause/resume/retry 操作。
5. 输出 artifact index 和安全相对标识。

Dashboard 实施顺序：

1. 共享 `DistillationService`、DTO、lease 和 events。
2. FastAPI health/security 与版本化 query API。
3. mutation API、SSE 和脱敏 trace。
4. React shell、主题和 API contract。
5. 任务作战台与真实 fixture。
6. 新建任务、平台登录、历史任务和产物预览。
7. 响应式、无障碍、E2E 和静态打包。

## 15. 完成定义

- `python main.py dashboard` 在 Windows、Linux 和 macOS 的受支持 Python 环境中启动并打开本地页面。
- 服务仅监听 127.0.0.1，变更操作通过 Origin/session/CSRF 校验。
- CLI、Rich Live 和 Dashboard 对同一 job 显示一致状态、进度、计数和双 ETA。
- Dashboard 实时显示总进度、最多三条固定活跃 item、Active x/3 和脱敏 trace。
- 下载中的 item 实时显示字节进度、速度和有依据的阶段 ETA；总大小未知时明确使用不定进度状态。
- 浏览器关闭或 SSE 中断后，重开页面能从状态快照恢复，不影响后台作业。
- 用户可以 dry-run、新建、协作式暂停、恢复、重试失败项和查看文本产物。
- 抖音登录使用外部 Chromium；网页和 API 不接触 Cookie 或二维码。
- 视觉符合已确认的赛博工业方向，并在桌面、平板和窄屏下保持核心信息可读。
- 前后端单元、契约、E2E、截图、无 Node 运行时 smoke tests 全部通过。
- 发布包内置静态资源，普通用户无需安装 Node 或访问 CDN。
- API、事件日志、静态包和 Git diff 不包含 Cookie、API key、profile、用户媒体、真实蒸馏内容或本机绝对路径。
