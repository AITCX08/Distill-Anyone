# Dashboard 创作者工作台开发计划

> **供 Goal 执行：** 只能使用单主代理与 `superpowers:executing-plans`，严格按任务顺序执行。禁止创建、委派或调用子代理；每个任务完成后先验证、提交小改动并记录 handoff，再进入下一任务。

**目标：** 将 Distill-Anyone Dashboard 优化为创作者可独立完成“创建、执行、交付”的本地工作台，提供可读标题、任务级保存目录、输出模板预览和产物交付闭环。

**架构：** 保持 Dashboard 只绑定 `127.0.0.1`，由 FastAPI 处理目录校验、短期令牌、私有任务配置和产物白名单；React 只显示安全的展示元数据。`TaskManager` 仍是唯一 Worker 进程所有者，目录和完整路径绝不进入 SSE、任务流、Worker JSONL 或执行日志。

**技术栈：** Python 3.14、FastAPI、Pydantic、SQLite、现有任务状态 JSON、React 18、TypeScript、Fluent UI v9、Vitest、Vite。

## 全局约束

- 项目新增或修改的 Markdown 文档使用简体中文，遵守 `AGENTS.md`。
- 禁止直接执行 `pytest` 或 `python -m pytest`。Python 测试只能通过 `scripts/run-pytest-background.cmd` 的无窗口后台包装器执行，并轮询 `.local-artifacts/test-runs/latest.exitcode` 与日志确认结果。
- 包装器必须以 `cmd /d /c start "" /b ...` 启动；不得使用交互式 CMD、`Start-Process`、计划任务或可见窗口运行测试。
- 不创建或使用子代理；不并发编辑工作区；一个任务卡只产生一个小提交。
- 长驻 Dashboard 使用既有 `pythonw` 无控制台启动；Worker 必须继续使用 `CREATE_NO_WINDOW`、`stdout=DEVNULL`、`stderr=DEVNULL`。
- Dashboard 只监听 `127.0.0.1`。Cookie、二维码载荷、API Key、进程命令行、PID 和原始 Worker 输出不得出现在浏览器、SSE、SQLite 事件或文档示例中。
- 本次用户明确允许在本地、经会话保护的创建确认和任务详情页显示保存目录；绝对目录仍不得出现在任务列表、SSE、实时日志和脱敏错误中。
- 前端使用既有 Fluent UI v9，不新增第二套组件库；所有用户可见文案为中文。

## 无窗口 Python 测试约定

每个 Python 测试任务使用以下固定流程，目标文件按任务替换：

```powershell
$env:DISTILL_ANYONE_PYTHON = 'C:\Coding\Anaconda\envs\Distill-Anyone\python.exe'
$previousExitWrite = if (Test-Path '.local-artifacts\test-runs\latest.exitcode') {
  (Get-Item '.local-artifacts\test-runs\latest.exitcode').LastWriteTimeUtc
} else { [datetime]::MinValue }
cmd /d /c start "" /b scripts\run-pytest-background.cmd tests\dashboard\test_output_directory.py
```

以不超过 30 秒的轮询读取 `latest.exitcode`；仅当该文件的修改时间晚于 `$previousExitWrite` 且内容为 `0` 时通过。失败时只读取本地日志中必要的错误段，不输出路径、Cookie 或环境变量值。每次运行后确认没有遗留 `pytest` 或包装器子进程。

---

## 文件结构与职责

| 路径 | 变更职责 |
| --- | --- |
| `src/dashboard/output_directory.py` | 默认目录、本地目录校验、短期会话令牌与原生文件夹选择器适配 |
| `src/dashboard/api/settings.py` | 默认目录、目录选择、目录校验 API |
| `src/dashboard/api/jobs.py` | 创建时解析目录令牌；提供仅本地详情的任务交付信息 |
| `src/dashboard/schemas.py` | 目录、任务详情、可读标题与产物响应模型 |
| `src/application/commands.py` | 私有任务保存目录、可读任务标题的命令与视图模型 |
| `src/application/service.py` | 将私有输出目录传入创建、恢复与重试的来源运行器 |
| `src/application/source_runner.py` | 将任务目录用于 episodes、Skill、RAG 输出目标 |
| `src/orchestration/models.py` | Worker Job/Task 的可读展示元数据与私有输出目录字段 |
| `src/orchestration/store.py` | SQLite 增量迁移、任务/产物展示元数据和私有目录读写 |
| `src/orchestration/bilibili_import.py` | 导入系列时保存系列标题、分集标题与默认/覆盖目录 |
| `src/orchestration/manager.py` | 将经验证的私有目录传给 Worker，不写入事件 |
| `src/orchestration/bilibili_worker.py` | 将完成产物原子交付到任务目录，并保留内部检查点产物 |
| `src/dashboard/api/tasks.py` | 任务 API 返回安全标题、集数、输出状态，不返回目录 |
| `src/dashboard/api/artifacts.py` | 从经批准的任务目录读取、预览、打开产物；返回安全元数据 |
| `src/dashboard/app.py` | 注册目录设置 API 与可注入的原生选择器 |
| `src/dashboard/sse.py` | 任务快照补充安全标题和完成摘要，保持目录脱敏 |
| `dashboard/src/api/schema.ts` | 对齐 Dashboard 安全展示契约 |
| `dashboard/src/features/create-job/*` | 引导式新建页、模板 Dialog、目录覆盖控件 |
| `dashboard/src/features/mission-control/*` | 标题优先的概览、交付摘要、作品卡与详情 Drawer |
| `dashboard/src/features/artifacts/*` | 可读产物分组、预览、打开文件夹与任务过滤 |
| `dashboard/src/theme/operations.css` | 密集工作台布局、可访问状态与移动端断点 |

---

### 任务 1：建立本地保存目录服务与安全目录 API

**文件：**

- 新建：`src/dashboard/output_directory.py`
- 新建：`src/dashboard/api/settings.py`
- 修改：`src/dashboard/app.py`
- 修改：`src/dashboard/schemas.py`
- 新建：`tests/dashboard/test_output_directory.py`
- 修改：`tests/dashboard/test_app.py`

**接口：**

- 消费：`app.state.local_session`、`require_mutation_security` 与 Dashboard `data` 根目录。
- 产出：`OutputDirectoryService`、`DirectorySelection`、`DirectoryValidationResult`；`GET/PUT /api/v1/settings/output-directory`、`POST /api/v1/directories/validate`、`POST /api/v1/directories/choose`。
- `DirectoryValidationResult` 固定包含 `token: str`、`directory: str`、`expires_at: str`；令牌必须绑定当前本地会话并在五分钟后失效。

- [ ] **步骤 1：先写失败测试**

```python
def test_directory_validation_returns_a_session_bound_token(tmp_path):
    service = OutputDirectoryService(tmp_path / "settings.json", session_id="session-a")
    result = service.validate(str(tmp_path / "deliveries"))

    assert result.directory.endswith("deliveries")
    assert service.resolve_token(result.token, session_id="session-a") == tmp_path / "deliveries"
    with pytest.raises(PermissionError):
        service.resolve_token(result.token, session_id="session-b")


def test_directory_validation_rejects_a_filesystem_root(tmp_path):
    service = OutputDirectoryService(tmp_path / "settings.json", session_id="session-a")

    with pytest.raises(ValueError, match="root"):
        service.validate(str(tmp_path.anchor))
```

另写 API 测试，断言 `PUT` 与两个 `POST` 缺少 Origin/CSRF 时返回 403；同一会话可获得默认目录，目录选择器返回取消时得到 `{"selected": false}`。

- [ ] **步骤 2：通过无窗口包装器运行失败测试**

运行：`tests/dashboard/test_output_directory.py`

预期：导入 `OutputDirectoryService` 失败；API 路由为 404。

- [ ] **步骤 3：实现最小目录服务与路由**

```python
@dataclass(frozen=True)
class DirectoryValidationResult:
    token: str
    directory: str
    expires_at: str


class OutputDirectoryService:
    def get_default(self) -> Path: ...
    def set_default(self, directory: str) -> Path: ...
    def validate(self, directory: str) -> DirectoryValidationResult: ...
    def resolve_token(self, token: str, *, session_id: str) -> Path: ...
```

目录校验必须执行 `expanduser()`、`resolve(strict=False)`，拒绝根目录；可创建父目录时创建一次测试目录并立即删除，以验证写权限。设置文件仅保存默认目录，令牌只保存在进程内存。`choose` 通过 `app.state.choose_output_directory` 调用可替换的本地原生选择器；测试注入 lambda，生产实现不得启动 CMD。

- [ ] **步骤 4：运行通过测试与边界测试**

运行：`tests/dashboard/test_output_directory.py tests/dashboard/test_app.py`

预期：默认目录持久化、根目录拒绝、令牌跨会话拒绝、取消选择器、Origin/CSRF 拒绝均通过。

- [ ] **步骤 5：检查差异并提交**

```powershell
git diff --check
git add src/dashboard/output_directory.py src/dashboard/api/settings.py src/dashboard/app.py src/dashboard/schemas.py tests/dashboard/test_output_directory.py tests/dashboard/test_app.py
git commit -m "feat(dashboard): validate local output directories"
```

**Handoff：** 记录默认目录的私有设置位置、令牌生存期与原生选择器可用性；不记录实际目录。

---

### 任务 2：将默认/覆盖目录持久化并传入完整流水线

**文件：**

- 修改：`src/dashboard/schemas.py`
- 修改：`src/dashboard/api/jobs.py`
- 修改：`src/application/commands.py`
- 修改：`src/application/service.py`
- 修改：`src/application/source_runner.py`
- 修改：`src/orchestration/models.py`
- 修改：`src/orchestration/store.py`
- 修改：`src/orchestration/manager.py`
- 修改：`src/orchestration/bilibili_import.py`
- 修改：`src/orchestration/bilibili_worker.py`
- 新建：`tests/dashboard/test_job_destination.py`
- 修改：`tests/orchestration/test_store.py`
- 修改：`tests/orchestration/test_manager.py`
- 修改：`tests/orchestration/test_bilibili_pipeline.py`

**接口：**

- `CreateJobInput` 增加 `destination_mode: Literal["default", "override"] = "default"` 和 `destination_token: str | None = None`。
- `CreateJobRequest` 增加私有 `output_directory: str`；该字段可写入任务请求状态，但不得加入 `JobView`、`JobResponse`、SSE 或事件。
- `JobRecord` 增加私有 `output_directory: str`；`TaskManager._write_payload()` 从 JobRecord 读取目录并写为 Worker 私有 `output_directory`。
- `SourceCreatorRequest` 增加 `output_directory: Path | None`；来源流水线的三个输出目标都使用该目录而不是无条件使用全局配置目录。

- [ ] **步骤 1：先写失败测试**

```python
def test_create_job_with_override_uses_resolved_token_but_never_returns_path(client, tmp_path):
    token = client.app.state.output_directories.validate(str(tmp_path / "delivery")).token
    response = client.post("/api/v1/jobs", json={
        "target": "https://example.invalid/creator",
        "preview_fingerprint": "preview-1",
        "destination_mode": "override",
        "destination_token": token,
    }, headers=mutation_headers(client))

    assert response.status_code == 200
    assert "output_directory" not in response.json()


def test_worker_payload_carries_private_output_directory_without_event_leak(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid", output_directory=str(tmp_path / "delivery"))
    task = store.create_tasks(job.job_id, [TaskSpec("bilibili_BV1xx_p01", "第 1 集")])[0]
    payload = write_payload_for_test(store, task)

    assert payload["output_directory"].endswith("delivery")
    assert "delivery" not in json.dumps(store.list_events(task.task_id), default=str)
```

补充测试：默认目录在创建时被复制；之后更新默认目录不会修改旧任务；覆盖目录令牌缺失、过期或跨会话时返回 409；Worker 写入使用 `temporary -> os.replace`，且输出目录错误变为脱敏的 `保存位置不可用`。

- [ ] **步骤 2：通过无窗口包装器运行失败测试**

运行：`tests/dashboard/test_job_destination.py tests/orchestration/test_store.py tests/orchestration/test_manager.py tests/orchestration/test_bilibili_pipeline.py`

预期：创建模型不接受 `destination_mode`，Store 不接受私有目录，Worker 产物不在指定目录。

- [ ] **步骤 3：实现目录解析与流水线传递**

```python
def _resolve_destination(payload: CreateJobInput, request: Request) -> Path:
    directories = request.app.state.output_directories
    if payload.destination_mode == "default":
        return directories.get_default()
    if not payload.destination_token:
        raise HTTPException(status_code=409, detail="output directory must be validated")
    return directories.resolve_token(payload.destination_token, session_id=request.app.state.local_session.value)
```

在 `jobs.create()` 中将解析后的目录写入 `CreateJobRequest.output_directory`。在 `OrchestrationStore.__init__()` 中使用幂等 `PRAGMA table_info` 加 `output_directory` 列，不破坏已有 `orchestration.sqlite3`。新增 `TaskSpec(source_id, display_title, part_number)`，保留字符串 `source_id` 输入兼容旧测试和旧导入。

`BilibiliWorkPipeline.write()` 先写 Worker 私有 artifacts，再将可交付的 Markdown 和 JSON 复制到 `context.payload["output_directory"] / "episodes"`。目标文件名只由已清理的标题和稳定集数生成；使用临时同目录文件与 `os.replace`。错误信息仅输出 `保存位置不可用`，绝不包含路径。

- [ ] **步骤 4：运行通过测试及来源运行器回归**

运行：`tests/dashboard/test_job_destination.py tests/application/test_service.py tests/orchestration/test_store.py tests/orchestration/test_manager.py tests/orchestration/test_bilibili_pipeline.py`

预期：默认与覆盖目录均可生效；私有目录不出现在响应、任务事件和日志；旧调用不需要新增参数；失败目录不发生静默回退。

- [ ] **步骤 5：检查差异并提交**

```powershell
git diff --check
git add src/dashboard/schemas.py src/dashboard/api/jobs.py src/application/commands.py src/application/service.py src/application/source_runner.py src/orchestration/models.py src/orchestration/store.py src/orchestration/manager.py src/orchestration/bilibili_import.py src/orchestration/bilibili_worker.py tests/dashboard/test_job_destination.py tests/orchestration
git commit -m "feat(output): support per-job delivery directories"
```

**Handoff：** 记录新字段的私有边界和旧数据库增量迁移结果；不得记录真实目录。

---

### 任务 3：为任务和作品建立可读标题的安全展示契约

**文件：**

- 修改：`src/orchestration/models.py`
- 修改：`src/orchestration/store.py`
- 修改：`src/orchestration/bilibili_import.py`
- 修改：`src/dashboard/api/tasks.py`
- 修改：`src/dashboard/schemas.py`
- 修改：`src/dashboard/sse.py`
- 修改：`dashboard/src/api/schema.ts`
- 修改：`dashboard/src/features/mission-control/useMissionControl.ts`
- 新建：`tests/orchestration/test_task_metadata.py`
- 修改：`tests/orchestration/test_bilibili_import.py`
- 修改：`tests/dashboard/test_task_api.py`
- 修改：`tests/dashboard/test_sse.py`
- 修改：`dashboard/src/api/events.test.ts`

**接口：**

- `TaskRecord` 和 `TaskResponse` 增加 `display_title: str`、`part_number: int | None`。
- 任务 SSE 快照包含同名字段与只读 `delivery_state: Literal["pending", "available", "unavailable"]`，不包含路径。
- B 站导入从 legacy `title` 和分集 metadata 取得标题；缺失时固定回退为 `第 {part_number} 集`。

- [ ] **步骤 1：先写失败测试**

```python
def test_imported_bilibili_task_prefers_part_title_and_has_human_fallback(tmp_path):
    result = BilibiliSeriesImporter(make_store(tmp_path)).import_series(
        "BV18bLkztE7R",
        legacy_state={"bvid": "BV18bLkztE7R", "title": "课程（2 集）", "parts": {
            "1": {"stage": "completed", "title": "开场与概念"},
            "2": {"stage": "pending"},
        }},
    )
    tasks = tasks_for_job(result.job_id)

    assert tasks[0].display_title == "开场与概念"
    assert tasks[1].display_title == "第 2 集"
    assert tasks[1].part_number == 2
```

补充 API/SSE 测试：返回 `display_title`、`part_number`、`delivery_state`；序列化 JSON 中没有 `output_directory`、盘符路径或凭据标记。

- [ ] **步骤 2：通过无窗口包装器运行失败测试**

运行：`tests/orchestration/test_task_metadata.py tests/orchestration/test_bilibili_import.py tests/dashboard/test_task_api.py tests/dashboard/test_sse.py`

预期：TaskRecord 没有展示字段；API/SSE 不含可读标题。

- [ ] **步骤 3：实现元数据迁移与投影**

```python
@dataclass(frozen=True)
class TaskSpec:
    source_id: str
    display_title: str = ""
    part_number: int | None = None


def display_title_for(task: TaskRecord) -> str:
    return task.display_title or (f"第 {task.part_number} 集" if task.part_number else task.source_id)
```

为 SQLite `tasks` 表加入 `display_title` 和 `part_number` 的幂等迁移；旧记录读取时以 `source_id` 解析 B 站分集并生成回退标题。`_response()` 和 `_snapshot_message()` 只投影上述安全字段。前端 schema guard 必须将它们列为必填的安全字符串/可选正整数，拒绝不完整快照而不是展示空标题。

- [ ] **步骤 4：运行通过测试与前端类型测试**

运行 Python：`tests/orchestration/test_task_metadata.py tests/orchestration/test_bilibili_import.py tests/dashboard/test_task_api.py tests/dashboard/test_sse.py`。

运行前端：`npm run test -- --run src/api/events.test.ts`。

预期：标题优先、分集回退、目录脱敏与严格 schema guard 全部通过。

- [ ] **步骤 5：检查差异并提交**

```powershell
git diff --check
git add src/orchestration/models.py src/orchestration/store.py src/orchestration/bilibili_import.py src/dashboard/api/tasks.py src/dashboard/schemas.py src/dashboard/sse.py dashboard/src/api/schema.ts dashboard/src/features/mission-control/useMissionControl.ts tests/orchestration/test_task_metadata.py tests/orchestration/test_bilibili_import.py tests/dashboard/test_task_api.py tests/dashboard/test_sse.py dashboard/src/api/events.test.ts
git commit -m "feat(dashboard): expose readable task metadata"
```

**Handoff：** 记录旧导入标题的回退策略与 SSE 脱敏检查结果。

---

### 任务 4：实现引导式新建页、输出说明与模板预览

**文件：**

- 新建：`dashboard/src/features/create-job/outputTemplates.ts`
- 新建：`dashboard/src/features/create-job/OutputTemplateDialog.tsx`
- 新建：`dashboard/src/features/create-job/OutputSelectionCard.tsx`
- 新建：`dashboard/src/features/create-job/OutputDirectoryField.tsx`
- 修改：`dashboard/src/features/create-job/CreateJobPage.tsx`
- 修改：`dashboard/src/features/create-job/CreateJobPage.test.tsx`
- 新建：`dashboard/src/features/create-job/OutputTemplateDialog.test.tsx`
- 新建：`dashboard/src/features/create-job/OutputDirectoryField.test.tsx`
- 修改：`dashboard/src/theme/operations.css`

**接口：**

- `OUTPUT_TEMPLATES` 是静态本地数据，键为 `episodes`、`skill`、`rag`；每项有 `title`、`description`、`bestFor`、`sample`。
- `OutputTemplateDialog({ output, open, onOpenChange })` 使用 Fluent `Dialog`，展示只读模板，不调用 API。
- `OutputDirectoryField` 读取默认目录、可验证手动输入、可调用目录选择器，向父组件只返回 `destinationMode` 与已验证 `destinationToken`。

- [ ] **步骤 1：先写失败前端测试**

```tsx
it("explains every deliverable and opens its representative template", async () => {
  render(<CreateJobPage />);

  expect(screen.getByText("逐作品 Markdown")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "查看 Skill 示例" }));
  expect(await screen.findByRole("dialog", { name: "蒸馏 Skill 示例" })).toHaveTextContent("工作流");
});

it("sends an override token only after the directory is validated", async () => {
  render(<CreateJobPage />);
  await userEvent.click(screen.getByRole("checkbox", { name: "本次使用其他保存位置" }));
  await userEvent.type(screen.getByLabelText("本次保存位置"), "D:/notes");
  await userEvent.click(screen.getByRole("button", { name: "校验位置" }));
  await screen.findByText("保存位置可用");

  expect(postJson).toHaveBeenCalledWith("/api/v1/directories/validate", { directory: "D:/notes" });
});
```

补充测试：未预检禁止创建；未校验的覆盖目录禁止创建；默认目录不带 token；点击原生选择器后把返回 token 传入创建请求；Dialog 可由 Escape 关闭且焦点返回触发按钮。

- [ ] **步骤 2：运行失败前端测试**

运行：`npm run test -- --run src/features/create-job/CreateJobPage.test.tsx src/features/create-job/OutputTemplateDialog.test.tsx src/features/create-job/OutputDirectoryField.test.tsx`

预期：找不到示例按钮、Dialog 和保存位置控件。

- [ ] **步骤 3：实现引导式创建体验**

```tsx
const request = {
  target: target.trim(),
  platform,
  outputs,
  rag_chunks: ragChunks,
  preview_fingerprint: preview.fingerprint,
  destination_mode: directory.mode,
  ...(directory.mode === "override" ? { destination_token: directory.token } : {}),
};
```

将三个输出项变为带标题、用途、适用场景、选择框和示例按钮的卡片；默认选择逐作品 Markdown 与蒸馏 Skill。预检成功后显示创作者名称、作品数量、跳过数和登录状态。创建成功显示可读确认、保存位置和跳转 `任务作战台`/`产物库` 的链接，而非只显示 job ID。

- [ ] **步骤 4：运行通过测试与生产构建**

运行：任务步骤 2 的 Vitest 命令，随后执行 `npm run build`。

预期：所有测试通过；`tsc -b && vite build` 成功，且不出现颜色/焦点可访问性警告。

- [ ] **步骤 5：检查差异并提交**

```powershell
git diff --check
git add dashboard/src/features/create-job dashboard/src/theme/operations.css
git commit -m "feat(dashboard): guide creators through job creation"
```

**Handoff：** 记录新建页的键盘路径、默认输出和目录覆盖行为。

---

### 任务 5：重构任务作战台为标题优先的执行与交付视图

**文件：**

- 修改：`dashboard/src/features/mission-control/MissionOverview.tsx`
- 修改：`dashboard/src/features/mission-control/MissionOverview.test.tsx`
- 修改：`dashboard/src/features/mission-control/MissionControlPage.tsx`
- 修改：`dashboard/src/features/mission-control/TaskControlCard.tsx`
- 修改：`dashboard/src/features/mission-control/TaskControlCard.test.tsx`
- 修改：`dashboard/src/features/mission-control/TaskDetailDrawer.tsx`
- 修改：`dashboard/src/features/mission-control/useMissionControl.ts`
- 修改：`dashboard/src/api/schema.ts`
- 修改：`dashboard/src/theme/operations.css`

**接口：**

- `MissionJob` 增加 `display_title`、`creator_name`、`platform`、`artifact_count`、`completed_at`，均为安全展示字段。
- `WorkerTask` 使用任务 3 的 `display_title`、`part_number`、`delivery_state`。
- `MissionOverview` 接收 `onViewArtifacts(jobId)` 和 `onRevealOutput(jobId)`；完成态不接收或渲染 ETA/下载速度。

- [ ] **步骤 1：先写失败前端测试**

```tsx
it("uses a series title instead of a job identifier in the completed overview", () => {
  render(<MissionOverview snapshot={completedSnapshot} job={{ ...job, display_title: "天纪四柱命卦", creator_name: "倪海厦" }} />);

  expect(screen.getByRole("heading", { name: "倪海厦 · 天纪四柱命卦" })).toBeVisible();
  expect(screen.getByText("已完成 8/8")).toBeVisible();
  expect(screen.queryByText("估算中")).not.toBeInTheDocument();
});

it("uses the work title before its stable source id", () => {
  render(<TaskControlCard task={{ ...task, display_title: "开场与概念", part_number: 1, status: "completed", stage: "completed" }} />);

  expect(screen.getByRole("heading", { name: "第 1 集 · 开场与概念" })).toBeVisible();
  expect(screen.getByText(task.source_id)).toBeVisible();
});
```

补充测试：下载中才出现 bytes/速度/ETA；转写/摘要显示阶段和检查点；失败卡包含原因和重试；暂停、继续、取消、重试仍只作用于所点击 task；内部 ID 不出现在概览主标题。

- [ ] **步骤 2：运行失败前端测试**

运行：`npm run test -- --run src/features/mission-control/MissionOverview.test.tsx src/features/mission-control/TaskControlCard.test.tsx src/features/mission-control/MissionControlPage.test.tsx`

预期：现有组件将 job/source ID 用作主标题，完成态仍有 ETA 文案。

- [ ] **步骤 3：实现状态专属信息层级**

```tsx
const heading = task.part_number
  ? `第 ${task.part_number} 集 · ${task.display_title}`
  : task.display_title;
const isComplete = task.status === "completed";
const showTransfer = task.stage === "downloading" && task.transfer !== undefined;
```

完成概览改为交付摘要：`完成时间`、`已生成产物`、`保存位置`、`查看产物`；活动概览保留阶段与可靠的下载遥测。技术 ID 位于可展开区域并可复制。作品卡为紧凑两层布局，标题第一、状态第二、技术 ID 最后；空状态提供 `新建任务`，而不是仅一行“暂无活动”。

- [ ] **步骤 4：运行通过测试与可访问性检查**

运行：任务步骤 2 的 Vitest 命令，再运行 `npm run build`。

预期：已完成态不展示 ETA；标题、操作按钮、状态播报和键盘焦点均可检索；构建通过。

- [ ] **步骤 5：检查差异并提交**

```powershell
git diff --check
git add dashboard/src/features/mission-control dashboard/src/api/schema.ts dashboard/src/theme/operations.css
git commit -m "feat(dashboard): make mission control creator friendly"
```

**Handoff：** 记录活动态与完成态的可见指标差异，确认内部 ID 只处于次级信息。

---

### 任务 6：完善产物库、任务详情与打开目录闭环

**文件：**

- 修改：`src/dashboard/api/artifacts.py`
- 修改：`src/dashboard/api/jobs.py`
- 修改：`src/dashboard/schemas.py`
- 新建：`tests/dashboard/test_job_details.py`
- 修改：`tests/dashboard/test_artifacts.py`
- 修改：`dashboard/src/features/artifacts/ArtifactsPage.tsx`
- 修改：`dashboard/src/features/artifacts/ArtifactsPage.test.tsx`
- 修改：`dashboard/src/features/mission-control/TaskDetailDrawer.tsx`
- 修改：`dashboard/src/theme/operations.css`

**接口：**

- `GET /api/v1/jobs/{job_id}/details` 返回 `display_title`、`creator_name`、`destination`、`artifact_count`、`completed_at`；只能由本地会话读取。
- `ArtifactSummary` 增加 `display_title`、`kind`、`size_bytes`、`created_at`；不返回实际文件路径。
- `POST /api/v1/jobs/{job_id}/reveal-output` 只打开任务已批准目录，不接受客户端目录参数。

- [ ] **步骤 1：先写失败测试**

```python
def test_job_details_return_destination_only_from_the_private_details_route(client, seeded_job):
    response = client.get(f"/api/v1/jobs/{seeded_job.job_id}/details")

    assert response.status_code == 200
    assert response.json()["destination"].endswith("delivery")
    assert "destination" not in client.get("/api/v1/jobs").text
    assert "delivery" not in client.get("/api/v1/events").text


def test_reveal_output_uses_only_the_job_allowlisted_destination(client, seeded_job):
    response = client.post(f"/api/v1/jobs/{seeded_job.job_id}/reveal-output", headers=mutation_headers(client))

    assert response.status_code == 204
    assert client.app.state.reveal_directory.call_args.args[0] == seeded_job.destination
```

前端测试覆盖：下拉框显示“创作者 · 任务标题”；每个产物显示类型、大小、时间；预览与打开文件夹的状态信息可读；没有产物时提供返回作战台和新建任务操作。

- [ ] **步骤 2：通过无窗口包装器运行失败测试**

运行 Python：`tests/dashboard/test_job_details.py tests/dashboard/test_artifacts.py`。

运行前端：`npm run test -- --run src/features/artifacts/ArtifactsPage.test.tsx`。

预期：详情路由不存在，产物响应缺少安全展示字段，前端显示 job/source ID。

- [ ] **步骤 3：实现白名单详情与交付动作**

```python
@router.get("/{job_id}/details", response_model=JobDetailsResponse)
def job_details(job_id: str, request: Request) -> JobDetailsResponse:
    details = request.app.state.job_delivery_details(job_id)
    return JobDetailsResponse(**details.public_local_view())


@router.post("/{job_id}/reveal-output", status_code=204, dependencies=[Depends(require_mutation_security)])
def reveal_output(job_id: str, request: Request) -> Response:
    request.app.state.reveal_directory(request.app.state.job_delivery_details(job_id).destination)
    return Response(status_code=204)
```

实现 `job_delivery_details()` 时只从私有 JobState/OrchestrationStore 读取目录，并验证其在该任务批准的根中。产物 API 应合并来源流水线和 Worker 交付清单，但只按不透明 artifact id 操作。前端按可读标题分组、使用详情接口显示本地目录、按钮调用既有或新 reveal API，绝不自行打开/拼接路径。

- [ ] **步骤 4：运行通过测试与目录脱敏扫描**

运行：步骤 2 的 Python 与 Vitest 命令。

额外检查：对任务列表、SSE 初始快照和任务 trace 的序列化结果搜索测试目录名，预期为零；对 details 路由预期为一处本地显示。

- [ ] **步骤 5：检查差异并提交**

```powershell
git diff --check
git add src/dashboard/api/artifacts.py src/dashboard/api/jobs.py src/dashboard/schemas.py tests/dashboard/test_job_details.py tests/dashboard/test_artifacts.py dashboard/src/features/artifacts dashboard/src/features/mission-control/TaskDetailDrawer.tsx dashboard/src/theme/operations.css
git commit -m "feat(dashboard): close the artifact delivery loop"
```

**Handoff：** 记录详情路由与 SSE 的目录可见性边界，以及打开目录只使用白名单目标的验证结果。

---

### 任务 7：完成视觉整理、端到端验收与中文发布文档

**文件：**

- 修改：`dashboard/src/theme/operations.css`
- 修改：`dashboard/src/app/AppShell.tsx`
- 修改：`dashboard/src/app/AppShell.test.tsx`
- 修改：`README.md`
- 修改：`docs/superpowers/specs/2026-08-10-dashboard-creator-workbench-design.md`
- 新建：`docs/superpowers/reviews/2026-08-10-dashboard-creator-workbench-acceptance.md`

**接口：**

- 不新增业务 API。
- Sidebar、页面标题、任务状态和按钮文案必须复用任务 4 至任务 6 已建立的中文术语。
- 验收文档只写测试结论、提交号、脱敏状态和已知风险；不写真实本机目录、Cookie、命令行或任务密钥。

- [ ] **步骤 1：先写失败前端测试**

```tsx
it("keeps the creator workbench navigation readable on a narrow viewport", () => {
  render(<AppShell activeWorkspace="create">内容</AppShell>);

  expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
  expect(screen.getByRole("link", { name: "新建任务" })).toBeVisible();
});
```

补充视觉回归断言：主题下输入控件、按钮、错误与成功状态有可读文本；移动端不横向溢出；任务完成态的主按钮仅有一个。

- [ ] **步骤 2：运行失败前端测试**

运行：`npm run test -- --run src/app/AppShell.test.tsx`。

预期：当前测试没有窄屏导航和完成态层级断言。

- [ ] **步骤 3：实施最小视觉与文档收口**

整理重复“任务/作品”前缀、空白区域和无关技术标签；保证信息密度、44px 操作目标、焦点环、深色主题输入对比度、错误/成功色和小屏单列布局。README 新增中文“创作者工作台”章节，说明预检、模板预览、默认与单次目录、任务级控制、产物预览与本地隐私边界。设计文档补记实际实现决定，验收文档逐条映射本计划的验收标准。

- [ ] **步骤 4：完整验证**

按无窗口包装器依次运行：

```text
tests/dashboard/test_output_directory.py
tests/dashboard/test_job_destination.py
tests/dashboard/test_job_details.py
tests/dashboard/test_task_api.py
tests/dashboard/test_sse.py
tests/dashboard/test_artifacts.py
tests/orchestration/test_task_metadata.py
tests/orchestration/test_bilibili_import.py
tests/orchestration/test_manager.py
tests/orchestration/test_bilibili_pipeline.py
```

运行前端：

```powershell
npm run test -- --run src/features/create-job src/features/mission-control src/features/artifacts src/app/AppShell.test.tsx
npm run build
& 'C:\Coding\Anaconda\envs\Distill-Anyone\python.exe' scripts\build_dashboard.py --from-dist
& 'C:\Coding\Anaconda\envs\Distill-Anyone\python.exe' scripts\build_dashboard.py --check
```

最后无窗口启动 Dashboard，确认健康接口为 200；使用本地浏览器验证：默认目录创建、覆盖目录创建、模板 Dialog、可读标题、运行态指标、完成交付摘要、打开产物目录。模拟一条无效目录，确认创建前拒绝；模拟一条不可用已保存目录，确认写入阶段暂停而非回退。

- [ ] **步骤 5：完成审查、提交与 handoff**

```powershell
git diff --check
git status --short
git add dashboard/src/theme/operations.css dashboard/src/app/AppShell.tsx dashboard/src/app/AppShell.test.tsx README.md docs/superpowers/specs/2026-08-10-dashboard-creator-workbench-design.md docs/superpowers/reviews/2026-08-10-dashboard-creator-workbench-acceptance.md src/dashboard/static
git commit -m "feat(dashboard): ship creator workbench experience"
```

Handoff 必须报告：各任务提交号、无窗口测试与前端构建结果、目录脱敏扫描结果、默认目录与覆盖目录的验收结果、剩余风险。若没有风险，明确写“无已知阻塞风险”。

---

## 计划自检

- **规格覆盖：** 创建解释与模板预览由任务 4 完成；默认和单任务目录由任务 1 至任务 2 完成；标题与集数由任务 3 完成；作战台可读性由任务 5 完成；产物闭环由任务 6 完成；可访问性、移动端、中文说明和发布验收由任务 7 完成。
- **安全一致性：** 目录只存在于私有设置、私有 JobState/SQLite 字段、Worker 私有 payload 及会话保护详情接口；任务响应、SSE、事件、日志和错误均有明确排除检查。
- **兼容性：** SQLite 改动采用幂等增量迁移；旧 B 站导入记录有标题回退；旧创建调用保留默认目录行为；来源流水线和 Worker 流水线均接收解析后的目录。
- **执行一致性：** 所有 Python 测试禁止直接 pytest，全部使用无窗口后台包装器；无子代理；每项任务都遵循失败测试、最小实现、通过测试、差异检查、小提交的顺序。
