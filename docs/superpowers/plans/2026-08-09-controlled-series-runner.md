# Controlled Series Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give imported multi-part series real local telemetry and safe Dashboard pause/resume controls.

**Architecture:** A durable `runtime.json` records runner lifecycle, current stage, transfer measurements, and trace entries next to the existing artifact checkpoint. A local controller starts/resumes the worker and the bridge projects runtime state into Dashboard job/SSE snapshots.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, pytest, React, TypeScript, Fluent UI, Vitest.

## Global Constraints

- Loopback only; never return credentials, process command lines, or local paths to the browser.
- Pause cooperatively after the active download/ASR/LLM call; resume must reuse completed artifacts.
- Python tests run through `scripts\\run-pytest-background.cmd`, never direct `pytest`.
- Launch long commands with `cmd.exe /d /c 'start "" /b ...'`; never use `Start-Process`.

---

### Task 1: Durable series telemetry state

**Files:**
- Create: `src/series/runtime.py`
- Create: `tests/series/test_runtime.py`
- Modify: `.local-artifacts/bilibili-series/distill_tianji_sizhu.py`

**Interfaces:** `SeriesRuntimeStore(root: Path)` provides `load() -> dict[str, Any]`, `update(**changes) -> dict[str, Any]`, `append_trace(level: str, message: str) -> dict[str, Any]`, and `pause_requested() -> bool`.

- [ ] **Step 1: Write failing tests**

```python
def test_update_is_atomic_and_monotonic(tmp_path):
    store = SeriesRuntimeStore(tmp_path)
    assert store.update(status="running", active_part=7)["revision"] == 1
    assert store.update(transfer={"completed_bytes": 25, "total_bytes": 100})["revision"] == 2

def test_pause_and_bounded_trace(tmp_path):
    store = SeriesRuntimeStore(tmp_path, trace_limit=2)
    store.append_trace("info", "one")
    store.append_trace("info", "two")
    assert [x["message"] for x in store.append_trace("info", "three")["trace"]] == ["two", "three"]
    store.update(status="pause_requested")
    assert store.pause_requested()
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\series\test_runtime.py`

Expected: import failure for `src.series.runtime`.

- [ ] **Step 3: Implement runtime state and instrument the script**

```python
def update(self, **changes: Any) -> dict[str, Any]:
    value = self.load()
    value.update(changes)
    value["revision"] = int(value.get("revision", 0)) + 1
    value["updated_at"] = utc_now_iso()
    atomic_write_json(self.path, value)
    return value
```

Write `running`, active part, stage, parsed yt-dlp transfer values, and redacted trace at every existing stage boundary. Before each next stage, if pause is requested write `paused` and exit without changing artifact checkpoints.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\series\test_runtime.py`

Expected: `2 passed`.

Commit: `git add src/series tests/series .local-artifacts/bilibili-series/distill_tianji_sizhu.py; git commit -m "feat(series): persist runtime telemetry and pause state"`.

### Task 2: Revisioned local series controls

**Files:**
- Create: `src/dashboard/series_control.py`
- Create: `src/dashboard/api/series.py`
- Create: `tests/dashboard/test_series_control.py`
- Modify: `src/dashboard/app.py`

**Interfaces:** `SeriesController(data_dir: Path, launcher: Callable[[str], None])` has `pause(bvid: str, expected_revision: int) -> dict[str, Any]` and `resume(bvid: str, expected_revision: int) -> dict[str, Any]`; routes are `POST /api/v1/series/{bvid}/pause|resume` with `RevisionInput`.

- [ ] **Step 1: Write failing controller tests**

```python
def test_pause_records_cooperative_request(tmp_path):
    SeriesRuntimeStore(tmp_path / "series" / "BV1").update(status="running")
    assert SeriesController(tmp_path, launcher=Mock()).pause("BV1", 1)["status"] == "pause_requested"

def test_resume_starts_one_checkpointed_worker(tmp_path):
    SeriesRuntimeStore(tmp_path / "series" / "BV1").update(status="paused")
    launch = Mock()
    assert SeriesController(tmp_path, launcher=launch).resume("BV1", 1)["status"] == "running"
    launch.assert_called_once_with("BV1")
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\dashboard\test_series_control.py`

Expected: import failure for `SeriesController`.

- [ ] **Step 3: Implement controller and route registration**

```python
def pause(self, bvid: str, expected_revision: int) -> dict[str, Any]:
    store = SeriesRuntimeStore(self.data_dir / "series" / bvid)
    if store.load()["revision"] != expected_revision:
        raise RevisionConflict(expected_revision, store.load()["revision"])
    return store.update(status="pause_requested")
```

`resume()` accepts only paused/failed, writes `running`, and calls the hidden launcher once. Register controller on `app.state`; route errors use existing local-session, CSRF, and revision-conflict handling.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\dashboard\test_series_control.py tests\dashboard\test_platform_api.py`

Expected: selected tests pass.

Commit: `git add src/dashboard/series_control.py src/dashboard/api/series.py src/dashboard/app.py tests/dashboard/test_series_control.py; git commit -m "feat(dashboard): control local series runs"`.

### Task 3: Telemetry bridge and SSE projection

**Files:**
- Modify: `src/dashboard/series_bridge.py`
- Modify: `tests/dashboard/test_series_bridge.py`

**Interfaces:** `SeriesTaskBridge` reads sibling `runtime.json`, publishes transfer fields and trace entries, and marks a series request `controlled_series=True` rather than `read_only=True`.

- [ ] **Step 1: Write a failing bridge test**

```python
def test_bridge_projects_runtime_transfer(tmp_path, events):
    write_series_state(tmp_path, "BV1", part_stage="downloading")
    SeriesRuntimeStore(tmp_path / "series" / "BV1").update(
        status="running", active_part=1, stage="downloading",
        transfer={"completed_bytes": 50, "total_bytes": 100, "bytes_per_second": 10},
    )
    SeriesTaskBridge(data_dir=tmp_path, events=events).sync()
    snapshot = event_payload(events, "progress.snapshot")["snapshot"]
    assert snapshot["active_items"][0]["completed_bytes"] == 50
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\dashboard\test_series_bridge.py`

Expected: transfer assertion fails because the old bridge emits only stages.

- [ ] **Step 3: Implement projection**

```python
transfer = runtime.get("transfer", {})
ItemProgress(source_id=source_id, title=title, stage=stage,
             completed_bytes=int(transfer.get("completed_bytes", 0)),
             total_bytes=transfer.get("total_bytes"),
             bytes_per_second=float(transfer.get("bytes_per_second", 0)))
```

Map `runtime.status` to the job lifecycle, emit bounded sanitized traces, and use absent transfer metrics for ASR/LLM so UI never invents `0 KB/s`.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\dashboard\test_series_bridge.py`

Expected: selected tests pass.

Commit: `git add src/dashboard/series_bridge.py tests/dashboard/test_series_bridge.py; git commit -m "feat(dashboard): stream controlled series telemetry"`.

### Task 4: Mission controls and stage-aware progress

**Files:**
- Modify: `dashboard/src/features/mission-control/MissionControlPage.tsx`
- Modify: `dashboard/src/features/mission-control/MissionControls.tsx`
- Modify: `dashboard/src/features/mission-control/MissionControls.test.tsx`
- Modify: `dashboard/src/features/mission-control/MissionOverview.tsx`
- Modify: `dashboard/src/features/mission-control/MissionOverview.test.tsx`

**Interfaces:** `MissionControls` receives `{jobId, revision, status, controlledSeries}`; `MissionOverview` renders transfer metrics only when `stage === "downloading"`.

- [ ] **Step 1: Write failing UI tests**

```tsx
it("offers pause for a running controlled series", () => {
  render(<MissionControls jobId="imported-series-BV1" revision={3} status="running" controlledSeries />)
  expect(screen.getByRole("button", { name: "暂停任务" })).toBeVisible()
})

it("does not render false download speed during ASR", () => {
  render(<MissionOverview activeItem={{ stage: "transcribing", completedBytes: 0, totalBytes: null }} />)
  expect(screen.getByText("正在转写，暂不显示下载速度")).toBeVisible()
})
```

- [ ] **Step 2: Verify red**

Run: `npm test -- MissionControls.test.tsx MissionOverview.test.tsx`

Expected: missing controls and stage-specific text.

- [ ] **Step 3: Implement the controls**

```tsx
const action = status === "running" ? "pause" : "resume";
await post(`/api/v1/series/${encodeURIComponent(bvid)}/${action}`, { expected_revision: revision });
```

Render `暂停任务` while running, disabled `暂停中` after acknowledgement, and `恢复任务` while paused/failed. Show bytes/s and ETA for download; show indeterminate named progress and latest trace for ASR/cleaning/knowledge extraction.

- [ ] **Step 4: Verify, package, and commit**

Run: `npm test -- MissionControls.test.tsx MissionOverview.test.tsx; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run build; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }`

Then run: `& C:\Coding\Anaconda\envs\Distill-Anyone\python.exe scripts\build_dashboard.py --from-dist; & C:\Coding\Anaconda\envs\Distill-Anyone\python.exe scripts\build_dashboard.py --check`

Commit: `git add dashboard/src src/dashboard/static; git commit -m "feat(dashboard): control and visualize series runs"`.

### Task 5: Current-series acceptance

**Files:**
- Modify: `.local-artifacts/bilibili-series/resume_with_dashboard_credential.py`

- [ ] **Step 1: Restart Dashboard with `DATA_DIR=C:\Users\Administrator\Desktop\Vibe\Distill-Anyone\data`**

- [ ] **Step 2: Confirm `GET /api/v1/jobs` returns `imported-series-BV18bLkztE7R` with six completed parts**

- [ ] **Step 3: Use Dashboard pause then resume during a safe stage boundary; confirm `runtime.json` transitions `running → pause_requested → paused → running`**

- [ ] **Step 4: Confirm part 8 download exposes nonzero transfer metrics, later stages expose named indeterminate progress, and no completed part is rerun**

- [ ] **Step 5: Commit operational wrapper changes**

Commit: `git add .local-artifacts/bilibili-series/resume_with_dashboard_credential.py; git commit -m "chore(series): run current series under dashboard control"`.
