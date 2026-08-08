# 黑曜石作战台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Dashboard 重构为中文、高密度、单工作区聚焦的黑曜石作战台，同时保持现有 FastAPI、SSE 和任务 API 行为不变。

**Architecture:** 保留 React、Fluent UI 和现有 SSE hook。`App` 根据 hash 只渲染一个工作区；作战台由概览、系列轨道、执行队列和实时日志四个纯展示组件组成。Python 服务端只在现有项目查询响应中补充安全的展示数据，前端不读取本地文件路径或凭据。

**Tech Stack:** React 18、TypeScript、Vite、Fluent UI v9、Vitest、FastAPI、Pydantic。

## Global Constraints

- 使用现有 `@fluentui/react-components`，不引入第二套组件库或大型动画依赖。
- 深色主题只使用石墨和蓝灰表面，青绿色为常规强调色；红色和黄色仅表示真实失败或告警。
- 保留 `#mission`、`#create`、`#platforms`、`#history`、`#artifacts` 作为可访问的导航目标。
- 未由服务端提供的大小、速率、阶段进度或 ETA 必须显示“未知”，禁止推断数值。
- 服务端原始日志和作品标题保持原文；已知静态文案、平台名和状态值使用中文。
- Windows Codex Desktop 中 Python 测试只可使用 `scripts/run-pytest-background.cmd`，不得直接调用 `pytest`。
- 每个任务在通过其目标测试后单独提交；不得使用子代理或并发写入。

---

### Task 1: 工作区导航和作战台主题壳层

**Files:**
- Modify: `dashboard/src/app/App.tsx`
- Modify: `dashboard/src/app/AppShell.tsx`
- Modify: `dashboard/src/theme/global.css`
- Modify: `dashboard/src/app/App.test.tsx`
- Modify: `dashboard/src/app/AppShell.test.tsx`
- Create: `dashboard/src/app/useWorkspace.ts`
- Create: `dashboard/src/app/useWorkspace.test.ts`

**Interfaces:**
- Consumes: 浏览器 `location.hash`。
- Produces: `useWorkspace(): WorkspaceId`，其中 `WorkspaceId = "mission" | "create" | "platforms" | "history" | "artifacts"`。
- Produces: `AppShell` 的 `activeWorkspace: WorkspaceId` 属性，用于当前导航语义状态。

- [ ] **Step 1: Write the failing test**

```tsx
it("uses the mission workspace for an unknown hash", () => {
  window.location.hash = "#unknown";
  const view = renderHook(() => useWorkspace());
  expect(view.result.current).toBe("mission");
});

it("renders only the selected creation workspace", () => {
  window.location.hash = "#create";
  render(<App />);
  expect(screen.getByRole("region", { name: "新建任务" })).toBeVisible();
  expect(screen.queryByRole("region", { name: "任务执行台" })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/app/useWorkspace.test.ts src/app/App.test.tsx`

Expected: FAIL，因为 hook 不存在且 App 同时渲染所有工作区。

- [ ] **Step 3: Write minimal implementation**

```ts
export const workspaces = ["mission", "create", "platforms", "history", "artifacts"] as const;
export type WorkspaceId = typeof workspaces[number];

export function useWorkspace(): WorkspaceId {
  const [workspace, setWorkspace] = useState<WorkspaceId>(() => readWorkspace(window.location.hash));
  useEffect(() => {
    const update = () => setWorkspace(readWorkspace(window.location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return workspace;
}
```

Render exactly one workspace in `App`; pass the active value to `AppShell`. In `AppShell`, set `aria-current="page"` on the active navigation link.

Replace `global.css` with semantic CSS custom properties for `--surface-canvas`, `--surface-raised`, `--surface-terminal`, `--text-primary`, `--text-secondary`, `--accent`, `--danger` and `--warning`. Use a 264px desktop navigation column and a 72px collapsed mobile top navigation. Give controls explicit foreground, background, border and focus colors.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/app/useWorkspace.test.ts src/app/App.test.tsx src/app/AppShell.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add dashboard/src/app dashboard/src/theme/global.css
git commit -m "feat(dashboard): add focused workspace navigation"
```

### Task 2: 作战台概览、作品轨道和紧凑执行队列

**Files:**
- Modify: `dashboard/src/features/mission-control/MissionControlPage.tsx`
- Modify: `dashboard/src/features/mission-control/ActiveItemRow.tsx`
- Modify: `dashboard/src/features/mission-control/MissionControlPage.test.tsx`
- Modify: `dashboard/src/features/mission-control/ActiveItemRow.test.tsx`
- Create: `dashboard/src/features/mission-control/MissionOverview.tsx`
- Create: `dashboard/src/features/mission-control/MissionOverview.test.tsx`
- Create: `dashboard/src/features/mission-control/SeriesRail.tsx`
- Create: `dashboard/src/features/mission-control/SeriesRail.test.tsx`

**Interfaces:**
- Consumes: `ProgressSnapshot` 和 `ActiveItem[]`。
- Produces: `MissionOverview({ snapshot, job })`、`SeriesRail({ total, completed, active, failed, selectedRowId, onSelect })`。
- Produces: `ActiveItemRow({ item, selected, onSelect })`，选择状态仅属于前端视图。

- [ ] **Step 1: Write the failing test**

```tsx
it("shows stage-specific transfer metrics without inventing a total", () => {
  render(<ActiveItemRow item={{ ...activeItem, total_bytes: null, stage: "downloading" }} />);
  expect(screen.getByText("文件大小未知")).toBeVisible();
  expect(screen.queryByText("0.0 KB / 0.0 KB")).not.toBeInTheDocument();
});

it("renders a selectable rail for every known series part", () => {
  render(<SeriesRail total={4} completed={2} active={1} failed={0} selectedRowId={3} onSelect={vi.fn()} />);
  expect(screen.getAllByRole("button", { name: /第 [1-4] 集/ })).toHaveLength(4);
  expect(screen.getByRole("button", { name: "第 3 集，执行中" })).toHaveAttribute("aria-pressed", "true");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/features/mission-control/ActiveItemRow.test.tsx src/features/mission-control/SeriesRail.test.tsx src/features/mission-control/MissionOverview.test.tsx`

Expected: FAIL，因为概览和轨道组件尚不存在，执行行仍是默认卡片布局。

- [ ] **Step 3: Write minimal implementation**

`MissionOverview` 渲染四个语义指标：总体进度、当前阶段、实时吞吐、预计总剩余时间。没有活动项时，阶段与吞吐显示“暂无活动任务”。

`SeriesRail` 用 `total` 渲染连续的原生 `button`，按稳定顺序分配完成、执行中、失败和等待状态。每个按钮使用中文可访问名称，如 `第 3 集，执行中`。不虚构标题或子阶段。

`ActiveItemRow` 使用 `article` 和紧凑网格布局：标题、阶段、阶段匹配指标和可用的阶段进度。下载总量未知时只显示已传输、速度和“文件大小未知”。转写时只显示音频时长与实时系数。通过 `data-selected` 和 `aria-pressed` 表示选择状态。

`MissionControlPage` 用 `useState<number | null>` 管理已选作品；任务概览、轨道、队列和日志成为独立视觉区，不再用连续 Fluent `Card` 包裹每个层级。

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/features/mission-control/ActiveItemRow.test.tsx src/features/mission-control/SeriesRail.test.tsx src/features/mission-control/MissionOverview.test.tsx src/features/mission-control/MissionControlPage.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add dashboard/src/features/mission-control
git commit -m "feat(dashboard): build mission overview and execution queue"
```

### Task 3: 实时日志终端和任务详情抽屉

**Files:**
- Modify: `dashboard/src/features/mission-control/LiveTrace.tsx`
- Modify: `dashboard/src/features/mission-control/LiveTrace.test.tsx`
- Modify: `dashboard/src/features/mission-control/MissionControlPage.tsx`
- Create: `dashboard/src/features/mission-control/TaskDetailDrawer.tsx`
- Create: `dashboard/src/features/mission-control/TaskDetailDrawer.test.tsx`

**Interfaces:**
- Consumes: `readonly string[]` 日志、选中 `ActiveItem | null`、`MissionJob | null`。
- Produces: `LiveTrace({ entries })` 和 `TaskDetailDrawer({ item, job, onClose })`。

- [ ] **Step 1: Write the failing test**

```tsx
it("does not force a scrolled-up reader back to the newest log", () => {
  render(<LiveTrace entries={["first", "second"]} />);
  const terminal = screen.getByRole("log", { name: "实时日志" });
  fireEvent.scroll(terminal, { target: { scrollTop: 0 } });
  expect(terminal).toHaveTextContent("first");
});

it("shows the selected item details and closes on request", () => {
  const onClose = vi.fn();
  render(<TaskDetailDrawer item={activeItem} job={runningJob} onClose={onClose} />);
  fireEvent.click(screen.getByRole("button", { name: "关闭详情" }));
  expect(onClose).toHaveBeenCalledOnce();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/features/mission-control/LiveTrace.test.tsx src/features/mission-control/TaskDetailDrawer.test.tsx`

Expected: FAIL，因为日志面板没有 `log` 语义且详情抽屉不存在。

- [ ] **Step 3: Write minimal implementation**

Use a `ref` in `LiveTrace` to determine whether scroll position is within 24px of the bottom. Only call `scrollTo` after a new entry when the user is already following the tail. Render the terminal as `<section role="log" aria-label="实时日志">` with a static empty state.

`TaskDetailDrawer` renders only when an item is selected. It shows source id, stage label, stage-specific metrics, last confirmed job status, a close button, and an explicit read-only message for externally monitored jobs. It must not fabricate actions for `read_only` jobs.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/features/mission-control/LiveTrace.test.tsx src/features/mission-control/TaskDetailDrawer.test.tsx src/features/mission-control/MissionControlPage.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add dashboard/src/features/mission-control
git commit -m "feat(dashboard): add live terminal and task detail drawer"
```

### Task 4: 任务创建、平台登录、历史和产物的作战台视觉统一

**Files:**
- Modify: `dashboard/src/features/create-job/CreateJobPage.tsx`
- Modify: `dashboard/src/features/platforms/PlatformsPage.tsx`
- Modify: `dashboard/src/features/job-history/JobHistoryPage.tsx`
- Modify: `dashboard/src/features/artifacts/ArtifactsPage.tsx`
- Modify: `dashboard/src/features/create-job/CreateJobPage.test.tsx`
- Modify: `dashboard/src/features/platforms/PlatformsPage.test.tsx`
- Modify: `dashboard/src/features/job-history/JobHistoryPage.test.tsx`
- Modify: `dashboard/src/features/artifacts/ArtifactsPage.test.tsx`

**Interfaces:**
- Consumes: 现有 Dashboard API 路径与响应 schema。
- Produces: 不改变请求参数、响应校验或现有可访问名称语义的独立工作区布局。

- [ ] **Step 1: Write the failing test**

```tsx
it("keeps creation inputs and its inspected summary in separate labelled columns", async () => {
  render(<CreateJobPage />);
  expect(screen.getByRole("region", { name: "任务配置" })).toBeVisible();
  expect(screen.getByRole("region", { name: "预检结果" })).toBeVisible();
});

it("labels the platform login flow as local and credential-safe", async () => {
  render(<PlatformsPage />);
  expect(await screen.findByText("凭据仅保存在本机，不会显示在页面上。"))
    .toBeVisible();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/features/create-job/CreateJobPage.test.tsx src/features/platforms/PlatformsPage.test.tsx src/features/job-history/JobHistoryPage.test.tsx src/features/artifacts/ArtifactsPage.test.tsx`

Expected: FAIL，因为创建与预检尚未划分工作区区域，平台页面没有新的安全文案。

- [ ] **Step 3: Write minimal implementation**

`CreateJobPage` 使用 `form` 内的“任务配置”和“预检结果”两个 `section`。预检前右栏显示说明，预检后显示平台、可处理数、跳过数、未支持数和登录状态。保持当前预检指纹和创建请求不变。

`PlatformsPage` 改为紧凑状态列表。保留既有外部浏览器登录调用，并将说明明确为“当前将在本地浏览器会话中完成登录”；不得声称已实现页面内二维码。

历史和产物页面使用列表与可展开详情视觉，而不是嵌套卡片；保留所有已有操作按钮、路径安全限制和 API 调用。

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/features/create-job/CreateJobPage.test.tsx src/features/platforms/PlatformsPage.test.tsx src/features/job-history/JobHistoryPage.test.tsx src/features/artifacts/ArtifactsPage.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add dashboard/src/features/create-job dashboard/src/features/platforms dashboard/src/features/job-history dashboard/src/features/artifacts
git commit -m "feat(dashboard): unify operational workspaces"
```

### Task 5: 生产构建、静态发布和本地服务验收

**Files:**
- Modify: `src/dashboard/static/index.html`
- Modify: `src/dashboard/static/.vite/manifest.json`
- Modify: `src/dashboard/static/assets/index-*.js`
- Modify: `src/dashboard/static/assets/index-*.css`
- Test: `dashboard/e2e/mission-control.spec.ts`

**Interfaces:**
- Consumes: 生产前端 bundle。
- Produces: `src/dashboard/static/` 中的自包含静态资源，供 `main.py dashboard` 提供服务。

- [ ] **Step 1: Write the failing end-to-end assertion**

```ts
await expect(page.getByRole("region", { name: "任务执行台" })).toBeVisible();
await expect(page.getByRole("log", { name: "实时日志" })).toBeVisible();
await page.goto("/#create");
await expect(page.getByRole("link", { name: "新建任务" })).toHaveAttribute("aria-current", "page");
```

- [ ] **Step 2: Run the focused browser test to verify it fails**

Run: `npm run e2e -- mission-control.spec.ts`

Expected: FAIL until the new landmark and workspace navigation are present.

- [ ] **Step 3: Build and publish the static bundle**

```powershell
npm run build
& 'C:\Coding\Anaconda\envs\Distill-Anyone\python.exe' scripts\build_dashboard.py --from-dist
& 'C:\Coding\Anaconda\envs\Distill-Anyone\python.exe' scripts\build_dashboard.py --check
```

Restart only the Dashboard process, then verify `GET /` and `GET /api/v1/health` both return HTTP 200. Verify the served HTML points to the current hashed JavaScript asset.

- [ ] **Step 4: Run all frontend tests and production checks**

Run: `npm test -- --run`

Expected: all Vitest files PASS.

Run: `npm run e2e`

Expected: all Playwright scenarios PASS.

- [ ] **Step 5: Commit**

```powershell
git add dashboard/e2e src/dashboard/static
git commit -m "build(dashboard): publish obsidian mission control"
```

## Plan self-review

- Spec coverage: Task 1 implements workspaces and theme; Task 2 implements overview, series rail and truthful phase metrics; Task 3 implements terminal and details; Task 4 implements creation, login, history and artifacts; Task 5 verifies the served bundle.
- No-placeholder scan: every task has paths, interfaces, tests, commands and a commit.
- Type consistency: `WorkspaceId`, `MissionOverview`, `SeriesRail`, `ActiveItemRow`, `LiveTrace` and `TaskDetailDrawer` are introduced before any downstream dependency uses them.
