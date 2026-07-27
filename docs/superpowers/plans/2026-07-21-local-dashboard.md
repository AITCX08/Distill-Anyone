# Local Distillation Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local cyber-industrial Dashboard that creates and monitors distillation jobs with real download progress, fixed active rows, dual ETA, safe controls, external browser login, and artifact previews.

**Architecture:** FastAPI serves a bundled React/Vite/Fluent UI application and maps versioned REST/SSE endpoints onto the core `DistillationService`. Node is build-only; Python serves committed static assets and remains the only end-user runtime.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, Pydantic 2, React, TypeScript, Vite, Fluent UI React, Vitest, Testing Library, Playwright Test, SSE.

## Global Constraints

- This plan starts only after the core plan completion gate passes.
- Bind only `127.0.0.1`; v0.4 has no `--host`, LAN mode, account system, remote auth, or deletion endpoints.
- `python main.py dashboard` uses port 8765 by default and opens the browser after health succeeds; `--no-open` suppresses opening.
- CLI, Rich Live, and Dashboard use the same `DistillationService`, `JobState`, `ProgressSnapshot`, and ETA values.
- Douyin login always opens an external Chromium window; Cookie, QR code, profile, and API keys never enter API payloads.
- SSE is the only live transport. REST performs commands/queries; no WebSocket is introduced.
- Node major is 22 with `engines.node >=22 <23`; `package-lock.json` locks all packages. Runtime never executes npm, npx, or CDN resources.
- Python web dependencies are bounded to `fastapi>=0.116,<0.117` and `uvicorn>=0.35,<0.36` for the v0.4 release line.
- Static assets, API responses, events, logs, screenshots, fixtures, and Git diff must contain no real user content, secrets, profile path, or machine absolute path.
- Cyber style uses near-black surfaces, cyan running, mint success, amber retry/warning, red failure, readable Chinese text, monospaced metrics, and reduced-motion support.

---

### Task 1: FastAPI Host, Static Assets, and Local Security

**Files:**
- Create: `src/dashboard/__init__.py`
- Create: `src/dashboard/app.py`
- Create: `src/dashboard/server.py`
- Create: `src/dashboard/security.py`
- Create: `src/dashboard/schemas.py`
- Create: `src/dashboard/api/__init__.py`
- Create: `src/dashboard/api/health.py`
- Create: `src/dashboard/static/index.html`
- Create: `tests/dashboard/test_app.py`
- Create: `tests/dashboard/test_security.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: core `DistillationService`.
- Produces: `create_dashboard_app(service, static_dir, session_secret) -> FastAPI`, `run_dashboard(service, port, open_browser)`.
- Security dependencies are `require_local_session(request)` and `require_mutation_security(request)`.

- [ ] **Step 1: Write failing host/security tests**

```python
def test_health_and_spa_are_served(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert "Distill Anyone" in client.get("/").text

def test_mutation_rejects_foreign_origin(client):
    response = client.post(
        "/api/v1/test-mutation",
        headers={"Origin": "https://evil.example", "X-CSRF-Token": "bad"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "invalid_origin"

def test_server_rejects_non_loopback_host():
    with pytest.raises(NonLoopbackHostError):
        validate_host("0.0.0.0")
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/dashboard/test_app.py tests/dashboard/test_security.py -q`

Expected: `src.dashboard` imports fail.

- [ ] **Step 3: Implement app factory, loopback host, CSP, local session, CSRF, and static fallback**

```python
def create_dashboard_app(service: DistillationService, static_dir: Path, session_secret: str) -> FastAPI:
    app = FastAPI(title="Distill-Anyone Local Dashboard", docs_url=None, redoc_url=None)
    app.state.service = service
    app.state.session_secret = session_secret
    app.include_router(health_router, prefix="/api/v1")
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        return FileResponse(static_dir / "index.html")
    return app

def validate_host(host: str) -> str:
    if ipaddress.ip_address(host) != ipaddress.ip_address("127.0.0.1"):
        raise NonLoopbackHostError(host)
    return host
```

- [ ] **Step 4: Run dashboard host tests**

Run: `python -m pytest tests/dashboard/test_app.py tests/dashboard/test_security.py -q`

Expected: tests pass with a fixture static directory and no browser/network.

- [ ] **Step 5: Commit**

```bash
git add src/dashboard tests/dashboard requirements.txt
git commit -m "feat: add secure local dashboard host"
```

### Task 2: Versioned Query and Command APIs

**Files:**
- Create: `src/dashboard/api/platforms.py`
- Create: `src/dashboard/api/jobs.py`
- Create: `src/dashboard/api/artifacts.py`
- Modify: `src/dashboard/app.py`
- Modify: `src/dashboard/schemas.py`
- Test: `tests/dashboard/test_platform_api.py`
- Test: `tests/dashboard/test_job_api.py`
- Test: `tests/dashboard/test_artifact_api.py`

**Interfaces:**
- Consumes: `DistillationService.preview/create/pause/resume/retry_failed/retry_item`, platform/job/artifact queries.
- Produces: `/api/v1/platforms`, platform auth/login, job preview/create/list/detail/items/actions, artifact list/read/reveal.

- [ ] **Step 1: Write failing API mapping and safety tests**

```python
def test_preview_does_not_create_job(client, service):
    response = secure_post(client, "/api/v1/jobs/preview", {"target": "https://v.douyin.com/x/", "platform": "auto"})
    assert response.status_code == 200
    assert response.json()["creator"]["platform"] == "douyin"
    service.create.assert_not_called()

def test_pause_returns_revision_conflict(client, service):
    service.pause.side_effect = RevisionConflict(expected=2, actual=3)
    response = secure_post(client, "/api/v1/jobs/job-1/pause", {"expected_revision": 2})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "revision_conflict"

def test_artifact_path_escape_is_rejected(client):
    response = client.get("/api/v1/jobs/job-1/artifacts/escape")
    assert response.status_code == 403
```

- [ ] **Step 2: Run API tests and verify failure**

Run: `python -m pytest tests/dashboard/test_platform_api.py tests/dashboard/test_job_api.py tests/dashboard/test_artifact_api.py -q`

Expected: routes return 404.

- [ ] **Step 3: Implement explicit Pydantic schemas and route-to-service mapping**

```python
@jobs_router.post("/jobs/{job_id}/pause", response_model=JobResponse)
def pause_job(job_id: str, body: RevisionRequest, service: ServiceDep, _: MutationSecurity) -> JobResponse:
    return JobResponse.from_view(service.pause(job_id, body.expected_revision))

@platforms_router.post("/platforms/{platform}/login", response_model=LoginOperationResponse)
def login(platform: str, service: ServiceDep, _: MutationSecurity) -> LoginOperationResponse:
    return LoginOperationResponse.from_view(service.login(platform, headful=True))
```

- [ ] **Step 4: Run API and application tests**

Run: `python -m pytest tests/dashboard tests/application -q`

Expected: API contract and core application tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dashboard tests/dashboard
git commit -m "feat: expose dashboard job APIs"
```

### Task 3: SSE Snapshots, Reconnect, and Redacted Trace

**Files:**
- Create: `src/dashboard/sse.py`
- Create: `src/dashboard/api/events.py`
- Modify: `src/dashboard/app.py`
- Modify: `src/application/events.py`
- Create: `src/application/event_log.py`
- Test: `tests/dashboard/test_sse.py`
- Test: `tests/dashboard/test_redaction.py`
- Test: `tests/application/test_event_log.py`

**Interfaces:**
- Consumes: core `EventHub` and application snapshots.
- Produces: `GET /api/v1/events`, `serialize_sse(event)`, `redact_event(event)`, 15-second heartbeat, snapshot reset for expired IDs.

- [ ] **Step 1: Write failing SSE and redaction tests**

```python
def test_expired_last_event_id_receives_snapshot(event_client, event_hub):
    for index in range(1100):
        event_hub.publish("job.updated", {"job_id": str(index)})
    frames = event_client.frames(headers={"Last-Event-ID": "1"}, limit=1)
    assert frames[0].event == "snapshot"

@pytest.mark.parametrize("secret", ["SESSDATA=abc", "Authorization: Bearer token", "sk-secret"])
def test_trace_redacts_secrets(secret):
    event = redact_event(ApplicationEvent(1, "trace.appended", now(), {"message": secret}))
    assert secret not in event.payload["message"]
    assert "[REDACTED]" in event.payload["message"]

def test_event_log_rotates_at_five_mib_and_keeps_three_files(tmp_path):
    log = SanitizedEventLog(tmp_path / "events.jsonl", max_bytes=5 * 1024 * 1024, backups=3)
    for index in range(8):
        log.append(make_trace_event(message="x" * 1024 * 1024, event_id=index))
    assert len(list(tmp_path.glob("events.jsonl*"))) <= 4
    assert all(path.stat().st_size <= 5 * 1024 * 1024 + 1024 for path in tmp_path.glob("events.jsonl*"))
```

- [ ] **Step 2: Run SSE tests and verify failure**

Run: `python -m pytest tests/dashboard/test_sse.py tests/dashboard/test_redaction.py tests/application/test_event_log.py -q`

Expected: SSE route/redactor missing.

- [ ] **Step 3: Implement bounded client queues and snapshot fallback**

```python
async def event_stream(service: DistillationService, last_event_id: int | None, job_id: str | None):
    replay = service.events.replay_after(last_event_id)
    if replay.requires_snapshot:
        yield serialize_sse(service.events.snapshot(job_id))
    for event in replay.events:
        yield serialize_sse(redact_event(event))
    async with service.events.subscribe(job_id, max_queue=128) as subscription:
        while True:
            try:
                event = await asyncio.wait_for(subscription.get(), timeout=15)
                yield serialize_sse(redact_event(event))
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"

class SanitizedEventLog:
    def append(self, event: ApplicationEvent) -> None:
        payload = (json.dumps(asdict(redact_event(event)), ensure_ascii=False) + "\n").encode("utf-8")
        with self._lock:
            if self.path.exists() and self.path.stat().st_size + len(payload) > self.max_bytes:
                self._rotate()
            with self.path.open("ab") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
```

- [ ] **Step 4: Run SSE/API tests**

Run: `python -m pytest tests/dashboard/test_sse.py tests/dashboard/test_redaction.py tests/application/test_event_log.py tests/dashboard/test_job_api.py -q`

Expected: snapshot, replay, heartbeat, overflow reset, and redaction tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dashboard src/application/events.py src/application/event_log.py tests/dashboard tests/application/test_event_log.py
git commit -m "feat: stream dashboard progress events"
```

### Task 4: React Scaffold, API Contract, and Cyber Theme

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/package-lock.json`
- Create: `dashboard/tsconfig.json`
- Create: `dashboard/vite.config.ts`
- Create: `dashboard/index.html`
- Create: `dashboard/src/main.tsx`
- Create: `dashboard/src/app/App.tsx`
- Create: `dashboard/src/app/AppShell.tsx`
- Create: `dashboard/src/api/client.ts`
- Create: `dashboard/src/api/events.ts`
- Create: `dashboard/src/api/schema.ts`
- Create: `dashboard/src/theme/cyberTheme.ts`
- Create: `dashboard/src/theme/global.css`
- Create: `dashboard/src/test/setup.ts`
- Create: `dashboard/src/app/AppShell.test.tsx`

**Interfaces:**
- Consumes: `/api/v1` OpenAPI schema and SSE event names from Tasks 2–3.
- Produces: typed `apiClient`, `subscribeToEvents`, Fluent `cyberTheme`, responsive `AppShell` routes.

- [ ] **Step 1: Add locked Node 22 project and failing shell test**

```tsx
it("shows local private engine status and primary navigation", async () => {
  render(<AppShell />)
  expect(screen.getByText("任务作战台")).toBeInTheDocument()
  expect(screen.getByText("LOCAL ENGINE ONLINE")).toBeInTheDocument()
  expect(screen.getByRole("navigation")).toBeVisible()
})
```

- [ ] **Step 2: Install and run the failing frontend test**

Run: `cd dashboard && npm ci && npm test -- --run src/app/AppShell.test.tsx`

Expected: test fails because `AppShell` is not implemented.

- [ ] **Step 3: Implement router shell, typed client, SSE adapter, and theme tokens**

```ts
export const cyberTheme = createDarkTheme({
  10: "#001013", 20: "#03242b", 30: "#07515d", 40: "#087b8d",
  50: "#0aa8be", 60: "#26e6ff", 70: "#61efff", 80: "#93f5ff",
  90: "#c4faff", 100: "#effeff", 110: "#f5ffff", 120: "#ffffff",
  130: "#ffffff", 140: "#ffffff", 150: "#ffffff", 160: "#ffffff",
})

export function subscribeToEvents(onEvent: (event: DashboardEvent) => void): () => void {
  const source = new EventSource("/api/v1/events")
  for (const type of EVENT_TYPES) source.addEventListener(type, event => onEvent(parseEvent(event)))
  return () => source.close()
}
```

- [ ] **Step 4: Run shell tests and production build**

Run: `cd dashboard && npm test -- --run && npm run build`

Expected: tests pass and `dist/index.html` plus hashed assets are produced.

- [ ] **Step 5: Commit**

```bash
git add dashboard
git commit -m "feat: scaffold cyber dashboard frontend"
```

### Task 5: Mission Control with Real Transfer Progress

**Files:**
- Create: `dashboard/src/features/mission-control/MissionControlPage.tsx`
- Create: `dashboard/src/features/mission-control/OverallProgress.tsx`
- Create: `dashboard/src/features/mission-control/ActiveItemRow.tsx`
- Create: `dashboard/src/features/mission-control/MetricsPanel.tsx`
- Create: `dashboard/src/features/mission-control/LiveTrace.tsx`
- Create: `dashboard/src/features/mission-control/useMissionControl.ts`
- Create: `dashboard/src/features/mission-control/MissionControlPage.test.tsx`
- Modify: `dashboard/src/app/App.tsx`

**Interfaces:**
- Consumes: `ProgressSnapshot`, `job.updated`, `item.updated`, `trace.appended`.
- Produces: fixed-key active rows, bytes/total/speed/download ETA, ASR duration/RTF, dual ETA, counters, pause/resume actions.

- [ ] **Step 1: Write failing fixed-row and progress tests**

```tsx
it("keeps one row per source id while the stage changes", async () => {
  const { emit } = renderMissionControl(snapshotWithItem("douyin_1", "downloading"))
  const row = screen.getByTestId("active-douyin_1")
  emit(itemUpdated("douyin_1", "transcribing", 0.53))
  expect(screen.getByTestId("active-douyin_1")).toBe(row)
  expect(within(row).getByText("TRANSCRIBING")).toBeVisible()
})

it("shows byte progress and speed during download", () => {
  renderMissionControl(snapshotDownloading({completed_bytes: 8_400_000, total_bytes: 39_800_000, bytes_per_second: 2_000_000}))
  expect(screen.getByText(/8.4 MB \/ 39.8 MB/)).toBeVisible()
  expect(screen.getByText(/2.0 MB\/s/)).toBeVisible()
})
```

- [ ] **Step 2: Run focused test and verify failure**

Run: `cd dashboard && npm test -- --run src/features/mission-control/MissionControlPage.test.tsx`

Expected: mission-control components missing.

- [ ] **Step 3: Implement server-value-only progress rendering and cooperative controls**

```tsx
export const ActiveItemRow = memo(function ActiveItemRow({ item }: { item: ItemProgress }) {
  return <div data-testid={`active-${item.source_id}`} className="activeItemRow">
    <div><strong>{item.title}</strong><code>{item.item_id}</code></div>
    <StatusText status={item.stage} />
    <ProgressBar value={item.stage_progress} indeterminate={item.stage_progress == null} />
    <StageDetail item={item} />
  </div>
})
```

- [ ] **Step 4: Run mission-control and accessibility tests**

Run: `cd dashboard && npm test -- --run src/features/mission-control src/app`

Expected: fixed row, unknown total, reconnecting, pausing/paused, counters, dual ETA, and keyboard tests pass.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat: add live mission control dashboard"
```

### Task 6: Create Job, Platform Login, History, and Artifacts

**Files:**
- Create: `dashboard/src/features/create-job/CreateJobPage.tsx`
- Create: `dashboard/src/features/create-job/CreateJobPage.test.tsx`
- Create: `dashboard/src/features/platforms/PlatformsPage.tsx`
- Create: `dashboard/src/features/platforms/PlatformsPage.test.tsx`
- Create: `dashboard/src/features/job-history/JobHistoryPage.tsx`
- Create: `dashboard/src/features/job-history/JobHistoryPage.test.tsx`
- Create: `dashboard/src/features/artifacts/ArtifactsPage.tsx`
- Create: `dashboard/src/features/artifacts/ArtifactsPage.test.tsx`
- Modify: `dashboard/src/app/App.tsx`

**Interfaces:**
- Consumes: preview/create/platform auth/login/job list/items/artifact endpoints.
- Produces: preview fingerprint gate, external-login statuses, status filters, single-item retry, text preview/copy/reveal.

- [ ] **Step 1: Write failing workflow tests**

```tsx
it("requires a fresh preview before creating a job", async () => {
  render(<CreateJobPage />)
  await userEvent.type(screen.getByLabelText("创作者链接"), "https://v.douyin.com/x/")
  expect(screen.getByRole("button", {name: "启动蒸馏"})).toBeDisabled()
  await userEvent.click(screen.getByRole("button", {name: "预检"}))
  expect(await screen.findByText("预计作品 628")).toBeVisible()
  expect(screen.getByRole("button", {name: "启动蒸馏"})).toBeEnabled()
})

it("describes external chromium login", async () => {
  render(<PlatformsPage />)
  await userEvent.click(screen.getByRole("button", {name: "登录抖音"}))
  expect(await screen.findByText("请在已打开的 Chromium 窗口中扫码")).toBeVisible()
})
```

- [ ] **Step 2: Run feature tests and verify failure**

Run: `cd dashboard && npm test -- --run src/features/create-job src/features/platforms src/features/job-history src/features/artifacts`

Expected: feature modules missing.

- [ ] **Step 3: Implement the four feature pages with explicit loading/empty/offline/partial states**

```tsx
function canStart(preview: PreviewResult | null, target: string): boolean {
  return preview !== null && preview.target === target && preview.fingerprint.length > 0
}

function retryVisible(item: JobItemView): boolean {
  return item.processing_status === "failed" && item.retryable
}
```

- [ ] **Step 4: Run all frontend unit tests**

Run: `cd dashboard && npm test -- --run`

Expected: all feature, shell, mission-control, accessibility, and responsive behavior tests pass.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat: add dashboard workflows and artifacts"
```

### Task 7: E2E, Responsive Screenshots, Static Packaging, CLI, and Docs

**Files:**
- Create: `dashboard/playwright.config.ts`
- Create: `dashboard/e2e/mission-control.spec.ts`
- Create: `dashboard/e2e/job-workflow.spec.ts`
- Create: `scripts/build_dashboard.py`
- Modify: `src/dashboard/static/`
- Modify: `main.py`
- Modify: `README.md`
- Modify: `DEVELOPMENT.md`
- Modify: `.gitignore`
- Create: `tests/dashboard/test_cli.py`
- Create: `tests/dashboard/test_packaged_static.py`

**Interfaces:**
- Consumes: all Dashboard tasks.
- Produces: `dashboard` Click command, reproducible static build, no-Node Python smoke, desktop/tablet/mobile screenshot tests.

- [ ] **Step 1: Write failing CLI/package/E2E tests**

```python
def test_dashboard_cli_defaults(runner, monkeypatch):
    run = Mock()
    monkeypatch.setattr("main.run_dashboard", run)
    result = runner.invoke(cli, ["dashboard", "--no-open"])
    assert result.exit_code == 0
    run.assert_called_once_with(port=8765, open_browser=False)

def test_packaged_static_works_without_node(client, monkeypatch):
    monkeypatch.setenv("PATH", "")
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/health").json()["static_compatible"] is True
```

```ts
test("job survives reload and restores snapshot", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByText("72.4%")).toBeVisible()
  await page.reload()
  await expect(page.getByText("ACTIVE 3 / 3")).toBeVisible()
})
```

- [ ] **Step 2: Run tests and verify missing command/build failures**

Run: `python -m pytest tests/dashboard/test_cli.py tests/dashboard/test_packaged_static.py -q`

Run: `cd dashboard && npx playwright test`

Expected: dashboard command/static compatibility and E2E fixtures fail before implementation.

- [ ] **Step 3: Implement deterministic build copier, Click command, docs, and fixture-only E2E**

```python
@cli.command("dashboard")
@click.option("--port", type=click.IntRange(1, 65535), default=8765, show_default=True)
@click.option("--open/--no-open", "open_browser", default=True, show_default=True)
def dashboard_command(port: int, open_browser: bool) -> None:
    run_dashboard(get_distillation_service(), port=port, open_browser=open_browser)

def copy_dashboard_build(source: Path, destination: Path) -> None:
    manifest = json.loads((source / ".vite" / "manifest.json").read_text("utf-8"))
    validate_manifest(manifest, source)
    replace_directory_atomically(source, destination)
```

- [ ] **Step 4: Run complete frontend/backend/package verification**

Run: `cd dashboard && npm test -- --run && npm run build && npx playwright test`

Expected: unit, workflow, responsive screenshot, and reload/reconnect E2E pass using mock server data.

Run: `python scripts/build_dashboard.py --check && python -m pytest -q`

Expected: static assets match frontend source and all Python tests pass.

Run: `python main.py dashboard --help`

Expected: only `--port` and `--open/--no-open` network/lifecycle options are shown; there is no `--host`.

- [ ] **Step 5: Review and commit**

Run: `git diff --check && git status --short`

Expected: only scoped Dashboard source, generated static, tests, scripts, config, and docs are changed.

```bash
git add dashboard src/dashboard scripts/build_dashboard.py main.py tests/dashboard README.md DEVELOPMENT.md .gitignore
git commit -m "feat: ship local distillation dashboard"
```

## Dashboard Plan Completion Gate

- [ ] Run `python -m pytest -q` and record exact results.
- [ ] Run `cd dashboard && npm test -- --run && npm run build && npx playwright test`.
- [ ] Run `python scripts/build_dashboard.py --check` and the no-Node packaged-static smoke test.
- [ ] Verify the server binds only `127.0.0.1`, mutation security tests pass, and no `--host` exists.
- [ ] Verify live fixtures show byte progress, speed, stage ETA, fixed item rows, Active x/3, counters, and both ETAs.
- [ ] Scan tracked content for secrets, machine paths, user artifacts, browser profile, state, media, and `.superpowers` files.
- [ ] Request final code review and run release-preparation checks before push, PR, or release.
