# Worker-Orchestrated Distillation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task with one main agent. Do not spawn subagents: this workspace has a documented desktop stability issue with concurrent agent lifecycles.

**Goal:** Replace the single series runner with a browser-controlled, local
orchestrator that runs every work in its own complete pipeline worker process.

**Architecture:** FastAPI owns a `TaskManager`; it persists jobs, tasks, leases,
commands, and redacted events in SQLite. One worker process per work owns the
full pipeline and emits validated JSON Lines. React Dashboard receives one
authoritative SSE state stream and sends revisioned task commands.

**Tech Stack:** Python 3.14 standard-library `sqlite3`, FastAPI, Pydantic,
subprocess, existing platform adapters/distillation modules, React, TypeScript,
Fluent UI, Vitest.

## Global Constraints

- Use a single main agent and serial task cards; no subagents or parallel edits.
- Run Python tests only through `scripts\run-pytest-background.cmd` or the
  established non-popup background wrapper; never invoke direct `pytest`.
- Start long-lived local processes through `ProcessStartInfo` with
  `UseShellExecute=false` and `CreateNoWindow=true`; never expose a CMD window.
- Loopback only. Never send credentials, command lines, local paths, or raw
  cookies to Dashboard, SSE, SQLite, checkpoint, or test fixtures.
- Every new behavior follows red-green-refactor and each task ends in a small
  commit.

## Target File Structure

| Path | Responsibility |
| --- | --- |
| `src/orchestration/models.py` | Typed job, task, lease, command, and event records |
| `src/orchestration/store.py` | SQLite schema, transactions, optimistic revisions |
| `src/orchestration/protocol.py` | JSONL worker event parser and validation |
| `src/orchestration/worker.py` | Single-task full-pipeline executable entry point |
| `src/orchestration/manager.py` | Queue selection, process ownership, pause/resume/cancel, reconciliation |
| `src/orchestration/resources.py` | Download/ASR/LLM slot allocation |
| `src/dashboard/api/tasks.py` | Revisioned task command and query endpoints |
| `src/dashboard/sse.py` | Initial and incremental orchestrator event projection |
| `dashboard/src/features/mission-control/*` | Per-task queue, telemetry, controls, trace rendering |
| `tests/orchestration/*` | Store, protocol, worker, manager, recovery tests |

---

## Phase 1 — Durable Task Kernel

### Task 1: Add orchestration records and SQLite schema

**Files:**
- Create: `src/orchestration/__init__.py`
- Create: `src/orchestration/models.py`
- Create: `src/orchestration/store.py`
- Create: `tests/orchestration/__init__.py`
- Create: `tests/orchestration/test_store.py`

**Produces:** `OrchestrationStore(path: Path)` with
`create_job(...)`, `create_tasks(...)`, `get_task(task_id)`,
`transition_task(task_id, expected_revision, ...)`, and `append_event(...)`.

- [ ] **Step 1: Write failing store tests**

```python
def test_create_tasks_are_independent_and_revisioned(tmp_path):
    store = OrchestrationStore(tmp_path / "orchestration.sqlite3")
    job = store.create_job(platform="bilibili", target="https://example.invalid")
    first, second = store.create_tasks(job.job_id, ["p01", "p02"])
    paused = store.transition_task(first.task_id, first.revision, status="pause_requested")
    assert paused.status == "pause_requested"
    assert store.get_task(second.task_id).status == "pending"
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_store.py`

Expected: import failure for `src.orchestration.store`.

- [ ] **Step 3: Implement the smallest schema**

```python
CREATE TABLE tasks (
  task_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  revision INTEGER NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 0,
  checkpoint_revision INTEGER NOT NULL DEFAULT 0,
  UNIQUE(job_id, source_id)
);
```

Implement transactions with `BEGIN IMMEDIATE`; compare expected revision before
incrementing it. Persist only sanitized metadata.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_store.py`

Expected: selected tests pass.

Commit: `git add src/orchestration tests/orchestration; git commit -m "feat(orchestration): add revisioned SQLite task store"`

### Task 2: Define and validate the worker JSONL protocol

**Files:**
- Create: `src/orchestration/protocol.py`
- Create: `tests/orchestration/test_protocol.py`

**Consumes:** `TaskRecord` from `src/orchestration/models.py`.

**Produces:** `parse_worker_event(line: str, expected_task_id: str) -> WorkerEvent`
and `ProtocolError`.

- [ ] **Step 1: Write failing protocol tests**

```python
def test_transfer_event_requires_matching_task_and_nonnegative_values():
    event = parse_worker_event(
        '{"v":1,"type":"transfer","task_id":"tsk_1","completed_bytes":2,"total_bytes":4,"bytes_per_second":1}',
        "tsk_1",
    )
    assert event.kind == "transfer"
    with pytest.raises(ProtocolError):
        parse_worker_event('{"v":1,"type":"transfer","task_id":"other","completed_bytes":-1}', "tsk_1")
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_protocol.py`

Expected: import failure for `parse_worker_event`.

- [ ] **Step 3: Implement only supported events**

Support `stage`, `transfer`, `checkpoint`, `log`, and `terminal`; reject payloads
over 16 KiB, unknown stages, negative measurements, and mismatched task ids.
Pass every text field through `redact_value` before it can leave the worker
boundary.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_protocol.py`

Expected: selected tests pass.

Commit: `git add src/orchestration/protocol.py tests/orchestration/test_protocol.py; git commit -m "feat(orchestration): validate worker event protocol"`

## Phase 2 — Isolated Full-Pipeline Worker

### Task 3: Extract one-work pipeline entry point and checkpoint contract

**Files:**
- Create: `src/orchestration/worker.py`
- Create: `tests/orchestration/test_worker.py`
- Modify: `src/application/source_runner.py`
- Modify: `src/distillation/engine.py`
- Modify: `src/distillation/artifacts.py`

**Consumes:** task id, source descriptor, output request, and task work directory.

**Produces:** `run_worker(task_id: str, payload_path: Path) -> int`, which writes
one `checkpoint.json` and JSONL events while executing the complete pipeline.

- [ ] **Step 1: Write failing worker checkpoint tests**

```python
def test_worker_resumes_after_valid_transcript_without_redownloading(tmp_path, fake_pipeline):
    payload = write_payload(tmp_path, task_id="tsk_1")
    write_checkpoint(tmp_path, stage="cleaning", transcript_verified=True)
    assert run_worker("tsk_1", payload, pipeline=fake_pipeline) == 0
    assert fake_pipeline.download_calls == 0
    assert fake_pipeline.clean_calls == 1
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_worker.py`

Expected: import failure for `run_worker`.

- [ ] **Step 3: Implement worker stages**

Use existing adapter/download, ASR, clean, knowledge, and output services in
order. After each validated artifact commit, atomically write:

```json
{"task_id":"tsk_1","stage":"cleaning","checkpoint_revision":3,"artifacts":{"transcript":"..."}}
```

Emit a `checkpoint` event only after that write succeeds. Read a parent-created
control file between stage boundaries and exit with `paused` or `cancelled`
terminal event when requested.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_worker.py tests\distillation\test_engine.py`

Expected: selected tests pass.

Commit: `git add src/orchestration/worker.py src/application/source_runner.py src/distillation tests/orchestration/test_worker.py; git commit -m "feat(worker): run one work through checkpointed pipeline"`

### Task 4: Emit real Bilibili downloader telemetry

**Files:**
- Modify: `src/platforms/bilibili/adapter.py`
- Modify: `src/crawl/audio_download.py`
- Modify: `src/orchestration/worker.py`
- Create: `tests/orchestration/test_bilibili_worker.py`

**Produces:** download-stage `transfer` events with known values when the
underlying downloader exposes them, and no transfer event during later stages.

- [ ] **Step 1: Write failing telemetry test**

```python
def test_bilibili_worker_forwards_download_hook_as_transfer_event(tmp_path, fake_downloader):
    events = run_fake_bilibili_worker(tmp_path, fake_downloader)
    assert events[0].kind == "transfer"
    assert events[0].payload["total_bytes"] == 100
    assert events[0].payload["bytes_per_second"] == 25
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_bilibili_worker.py`

Expected: transfer event assertion fails.

- [ ] **Step 3: Implement hook translation**

Translate downloader hook fields into protocol events only while stage is
`downloading`. Never synthesize `0 B/s`, a total size, or ETA for ASR and LLM
stages.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_bilibili_worker.py`

Expected: selected tests pass.

Commit: `git add src/platforms/bilibili src/crawl/audio_download.py src/orchestration/worker.py tests/orchestration/test_bilibili_worker.py; git commit -m "feat(worker): report Bilibili transfer telemetry"`

## Phase 3 — Process Manager and Recovery

### Task 5: Launch and own one hidden worker per task

**Files:**
- Create: `src/orchestration/manager.py`
- Create: `tests/orchestration/test_manager.py`
- Modify: `src/dashboard/server.py`

**Produces:** `TaskManager.start(task_id)`, `pause(task_id)`, `resume(task_id)`,
`cancel(task_id)`, and `tick()`.

- [ ] **Step 1: Write failing manager lifecycle test**

```python
def test_start_records_one_lease_and_reads_worker_events(tmp_path, fake_process_factory):
    manager = make_manager(tmp_path, process_factory=fake_process_factory)
    task = manager.enqueue("job-1", "p01")
    manager.tick()
    assert manager.store.get_lease(task.task_id).pid == fake_process_factory.pid
    assert manager.store.get_task(task.task_id).status == "running"
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_manager.py`

Expected: import failure for `TaskManager`.

- [ ] **Step 3: Implement guarded process launch**

Create workers with `subprocess.Popen`, `CREATE_NO_WINDOW`, stdin/stdout pipes,
and a task payload file. Persist the lease before reading events; include PID and
an opaque start marker only in the private store. Reject all control attempts
unless a current lease belongs to the requested task.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_manager.py`

Expected: selected tests pass.

Commit: `git add src/orchestration/manager.py src/dashboard/server.py tests/orchestration/test_manager.py; git commit -m "feat(orchestration): manage isolated worker processes"`

### Task 6: Add cooperative pause, cancel, and restart reconciliation

**Files:**
- Modify: `src/orchestration/manager.py`
- Modify: `src/orchestration/store.py`
- Modify: `tests/orchestration/test_manager.py`
- Create: `tests/orchestration/test_recovery.py`

**Produces:** pause writes a worker control file; cancel uses graceful exit then
lease-owned termination; restart reconciliation classifies `running`,
`interrupted`, and `paused` correctly.

- [ ] **Step 1: Write failing recovery tests**

```python
def test_restart_marks_missing_leased_process_interrupted_and_resumable(tmp_path, dead_pid_probe):
    manager = make_manager(tmp_path, pid_probe=dead_pid_probe)
    task = manager.store.create_running_task_with_lease("job-1", "p01", pid=123)
    manager.reconcile()
    assert manager.store.get_task(task.task_id).status == "interrupted"

def test_pause_requests_checkpoint_without_killing_an_unowned_process(tmp_path):
    manager = make_manager(tmp_path)
    task = manager.enqueue("job-1", "p01")
    manager.pause(task.task_id)
    assert read_control_file(task.task_id)["command"] == "pause"
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_recovery.py`

Expected: missing `reconcile` or incorrect lifecycle transition.

- [ ] **Step 3: Implement safe reconciliation**

Compare PID plus start marker, never a PID alone. Send graceful command first;
only after timeout may manager terminate its own active lease. Preserve
checkpoint and mark the terminal reason in a redacted event.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_manager.py tests\orchestration\test_recovery.py`

Expected: selected tests pass.

Commit: `git add src/orchestration tests/orchestration; git commit -m "feat(orchestration): recover and control worker leases"`

## Phase 4 — Browser Control Plane

### Task 7: Expose revisioned task APIs and SSE task snapshots

**Files:**
- Create: `src/dashboard/api/tasks.py`
- Modify: `src/dashboard/app.py`
- Modify: `src/dashboard/sse.py`
- Modify: `src/dashboard/schemas.py`
- Create: `tests/dashboard/test_task_api.py`
- Modify: `tests/dashboard/test_sse.py`

**Produces:** task query and command API, plus initial SSE snapshots containing
tasks and their bounded redacted traces.

- [ ] **Step 1: Write failing API and SSE tests**

```python
def test_pause_task_requires_current_revision(local_client, seeded_task):
    response = local_client.post(
        f"/api/v1/tasks/{seeded_task.task_id}/pause",
        json={"expected_revision": seeded_task.revision, "command_id": "cmd_1"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pause_requested"

def test_initial_sse_snapshot_contains_task_trace(local_service):
    message = next_sse_message(local_service)
    assert '"tasks"' in message
    assert '"traces"' in message
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\dashboard\test_task_api.py tests\dashboard\test_sse.py`

Expected: 404 for task routes and no task snapshot payload.

- [ ] **Step 3: Implement local-only endpoints**

Require existing local session, Origin, CSRF, revision, and a UUID-like
`command_id`. Route commands to `TaskManager`; publish only sanitized task
fields and event text to SSE.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\dashboard\test_task_api.py tests\dashboard\test_sse.py tests\dashboard\test_security.py`

Expected: selected tests pass.

Commit: `git add src/dashboard tests/dashboard/test_task_api.py tests/dashboard/test_sse.py; git commit -m "feat(dashboard): expose worker task controls"`

### Task 8: Replace series-only controls with per-task Mission Control

**Files:**
- Modify: `dashboard/src/api/schema.ts`
- Modify: `dashboard/src/api/events.ts`
- Modify: `dashboard/src/features/mission-control/useMissionControl.ts`
- Modify: `dashboard/src/features/mission-control/MissionControlPage.tsx`
- Modify: `dashboard/src/features/mission-control/MissionControls.tsx`
- Modify: `dashboard/src/features/mission-control/ActiveItemRow.tsx`
- Modify: `dashboard/src/features/mission-control/LiveTrace.tsx`
- Create: `dashboard/src/features/mission-control/TaskControlCard.tsx`
- Create: `dashboard/src/features/mission-control/TaskControlCard.test.tsx`

**Produces:** individual task cards, job-level queue summary, and task-level
pause/resume/cancel/retry without any raw PID or path.

- [ ] **Step 1: Write failing UI tests**

```tsx
it("shows independent controls for two active tasks", () => {
  render(<MissionControlPage snapshot={twoTaskSnapshot} />);
  expect(screen.getAllByRole("button", { name: "暂停任务" })).toHaveLength(2);
});

it("shows bytes and speed only for a downloading task", () => {
  render(<TaskControlCard task={{ ...task, stage: "transcribing" }} />);
  expect(screen.getByText("正在转写，暂不显示下载速度")).toBeVisible();
  expect(screen.queryByText(/KB\/秒/)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Verify red**

Run: `npm test -- --run src/features/mission-control/TaskControlCard.test.tsx src/features/mission-control/MissionControlPage.test.tsx`

Expected: missing task card and task-level controls.

- [ ] **Step 3: Implement task presentation**

Render immutable task id only internally; show user-friendly work title, stage,
checkpoint, elapsed time, transfer details only during `downloading`, and
redacted trace. Every action posts `{expected_revision, command_id}` and waits
for server confirmation before changing its label.

- [ ] **Step 4: Verify, package, and commit**

Run: `npm test -- --run src/features/mission-control; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run build; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }`

Then run: `& C:\Coding\Anaconda\envs\Distill-Anyone\python.exe scripts\build_dashboard.py --from-dist; & C:\Coding\Anaconda\envs\Distill-Anyone\python.exe scripts\build_dashboard.py --check`

Commit: `git add dashboard/src src/dashboard/static; git commit -m "feat(dashboard): manage individual pipeline workers"`

## Phase 5 — Bilibili Series Migration and Controlled Release

### Task 9: Import Bilibili series into ordinary orchestration tasks

**Files:**
- Create: `src/orchestration/bilibili_import.py`
- Modify: `src/platforms/bilibili/adapter.py`
- Modify: `src/dashboard/series_bridge.py`
- Create: `tests/orchestration/test_bilibili_import.py`
- Modify: `tests/dashboard/test_series_bridge.py`

**Produces:** a Bilibili series is one Job with one Task per part; the temporary
`runtime.json` bridge remains only for unmigrated legacy jobs.

- [ ] **Step 1: Write failing import test**

```python
def test_import_creates_one_task_per_series_part_and_preserves_completed_parts(tmp_path):
    importer = BilibiliSeriesImporter(make_store(tmp_path), fake_adapter(parts=8))
    result = importer.import_series("BV18bLkztE7R", legacy_state=legacy_state(completed=(1, 2, 3, 4, 5, 6)))
    assert result.created_tasks == 8
    assert result.completed_tasks == 6
    assert result.pending_tasks == 2
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_bilibili_import.py`

Expected: importer is unavailable.

- [ ] **Step 3: Implement idempotent import**

Map each Bilibili part to a stable source id and task id. Verify legacy
artifacts before importing a part as completed; import all others as pending.
Refuse a duplicate import unless it resolves to the same source URL and parts.

- [ ] **Step 4: Verify green and commit**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_bilibili_import.py tests\dashboard\test_series_bridge.py`

Expected: selected tests pass.

Commit: `git add src/orchestration/bilibili_import.py src/platforms/bilibili src/dashboard/series_bridge.py tests/orchestration tests/dashboard/test_series_bridge.py; git commit -m "feat(bilibili): import series as isolated tasks"`

### Task 10: Add resource limits, two-task acceptance, and migration documentation

**Files:**
- Create: `src/orchestration/resources.py`
- Create: `tests/orchestration/test_resources.py`
- Modify: `src/orchestration/manager.py`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-09-controlled-series-runner-design.md`

**Produces:** stage resource allocation and user-facing migration instructions.

- [ ] **Step 1: Write failing resource tests**

```python
def test_only_one_asr_task_receives_the_asr_slot():
    slots = ResourceSlots(download=2, asr=1, llm=1)
    assert slots.acquire("tsk_1", "transcribing")
    assert not slots.acquire("tsk_2", "transcribing")
    slots.release("tsk_1", "transcribing")
    assert slots.acquire("tsk_2", "transcribing")
```

- [ ] **Step 2: Verify red**

Run: `scripts\run-pytest-background.cmd tests\orchestration\test_resources.py`

Expected: import failure for `ResourceSlots`.

- [ ] **Step 3: Implement limits and acceptance checks**

Configure default limits `pipeline=2`, `download=2`, `asr=1`, `llm=1`. Update
README with Dashboard-only workflow: local QR login, create/import, inspect
per-task progress, pause/resume/cancel, restart recovery, and privacy rules.
Mark the older controlled-series design as superseded by this document.

- [ ] **Step 4: Verify release candidate and commit**

Run Python selected suite through the background wrapper:

`tests/orchestration tests/dashboard/test_task_api.py tests/dashboard/test_sse.py tests/platforms/test_bilibili_adapter.py`

Run frontend suite and package:

`npm test -- --run src/features/mission-control; npm run build; python scripts/build_dashboard.py --from-dist; python scripts/build_dashboard.py --check`

Manual acceptance: import the current eight-part Bilibili series, confirm parts
1–6 remain completed, start parts 7 and 8 with two worker leases, pause one,
restart Dashboard, resume it, and confirm no credential appears in Dashboard or
event history.

Commit: `git add src/orchestration README.md docs/superpowers/specs dashboard src tests; git commit -m "feat(orchestration): ship controlled multi-worker Bilibili jobs"`

## Plan Self-Review

- Spec coverage: task store (Task 1), worker isolation and checkpoints (Tasks 2–4), PID lifecycle and recovery (Tasks 5–6), browser control and SSE (Tasks 7–8), Bilibili migration and concurrency (Tasks 9–10).
- No placeholders: every task names files, contracts, failing tests, verification, and a small commit.
- Type consistency: `task_id`, `expected_revision`, `command_id`, `TaskManager`, `OrchestrationStore`, `WorkerEvent`, and `ResourceSlots` are introduced before later tasks consume them.
