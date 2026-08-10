# Worker-Orchestrated Distillation Design

## Status and Decision

Approved design direction: every individual work is executed by one isolated
local worker process for its complete pipeline: download, media extraction,
transcription, cleaning, knowledge extraction, and artifact writing. The
browser is the sole operator-facing control plane. The loopback Dashboard
service, not browser JavaScript, owns Windows process creation and control.

This design supersedes the single-process operational approach in
`2026-08-09-controlled-series-runner-design.md`. Existing JSON job checkpoints
remain readable during migration; no completed artifact is discarded.

## Goals

- A user can create several creator or series jobs from Dashboard and run their
  works concurrently within explicit resource limits.
- Every work has a stable task id, PID ownership record, durable checkpoint,
  bounded log, retry history, and independently controllable lifecycle.
- Dashboard can create, pause, resume, cancel, retry, and inspect tasks without
  opening a terminal or an external QR page.
- A stopped Dashboard service can reconcile worker processes after restart and
  mark lost workers accurately instead of reporting invented progress.
- Platform adapters remain responsible only for source enumeration, media
  access, and credentials; orchestration is platform independent.

## Non-goals

- The browser never receives credentials, process command lines, filesystem
  paths, raw cookies, or access to arbitrary local processes.
- The first migration does not distribute work across machines or expose the
  Dashboard outside `127.0.0.1`.
- The first migration does not split one work into one process per stage. A
  work owns one pipeline worker so its checkpoint and failure boundary are
  obvious.

## Target Architecture

```text
React Dashboard
  | REST commands + Server-Sent Events
  v
FastAPI loopback service
  | owns process creation and command authorization
  v
TaskManager ---- SQLite scheduler store ---- TaskEventStore
  |              |                           |
  |              |                           +--> SSE snapshots and trace
  |              +--> restart reconciliation
  |
  +--> Worker process per task
         download -> audio -> ASR -> clean -> summarize -> artifact commit
         private JSONL event file + manager resource permits
         task work directory: checkpoint + media + artifacts
```

### Responsibility boundaries

| Component | Responsibility | Must not do |
| --- | --- | --- |
| Dashboard React | Render state and send authenticated user intent | Spawn processes or read credentials |
| FastAPI API | Validate local session, CSRF, revisions, and command payloads | Contain pipeline implementation |
| `TaskManager` | Queue tasks, allocate resource slots, create/reap workers, reconcile restart | Parse platform pages or generate artifacts |
| Worker | Execute one work through the full pipeline, persist checkpoint, emit sanitized JSONL | Mutate scheduler state or spawn sibling workers |
| Platform adapter | Enumerate source works and create media access inputs | Schedule work or expose secrets |
| SQLite store | Durable task lifecycle, worker lease, command outcome, event cursor | Store cookies, raw command line, or temporary secrets |

## Durable Model

SQLite under `data/orchestration.sqlite3` is the scheduler authority. Existing
`data/jobs/<job_id>/job_state.json` stays as artifact and compatibility state
until migration is complete. Each worker gets a deterministic work directory:

```text
data/workers/<task_id>/
  checkpoint.json
  events.jsonl
  resource-request.json / resource-grant.json
  media/
  artifacts/
```

`checkpoint.json` records only the last durable pipeline boundary and validated
artifact references. It has stages: `pending`, `downloading`, `downloaded`,
`extracting_audio`, `transcribing`, `cleaning`, `summarizing`, `writing`,
`completed`, `paused`, `failed`, and `cancelled`.

The scheduler has the following normalized records:

- `jobs`: request metadata, platform, requested outputs, job status and revision.
- `tasks`: one row per work, lifecycle status, stage, attempt count, checkpoint
  revision, resource class, and latest safe error.
- `worker_leases`: `task_id`, PID, opaque start marker, launched time, heartbeat,
  and ownership state. Process command lines are never persisted or returned.
- `task_events`: ordered redacted events with task id, sequence, timestamp, kind,
  and compact JSON payload.

## Worker Protocol

The parent passes only a task id, a private worker-directory reference, and a
stable source descriptor to a worker. Credentials are resolved inside the
worker's local platform adapter and never enter the payload. Worker events are
appended as line-delimited UTF-8 JSON to its private `events.jsonl`; worker
stdout and stderr are discarded. Required event shapes are:

```json
{"v":1,"type":"stage","task_id":"tsk_...","stage":"transcribing"}
{"v":1,"type":"transfer","task_id":"tsk_...","completed_bytes":10485760,"total_bytes":52428800,"bytes_per_second":3145728}
{"v":1,"type":"checkpoint","task_id":"tsk_...","stage":"cleaning","checkpoint_revision":4}
{"v":1,"type":"terminal","task_id":"tsk_...","status":"completed"}
```

The manager validates task id, protocol version, numeric ranges, stage
transitions, payload size, and redaction before writing an event. Invalid events
fail only their worker; they cannot corrupt another task.

## Lifecycle and Control Semantics

1. Dashboard creates or imports a job. The service enumerates works and creates
   one `pending` task per work in one transaction.
2. TaskManager creates at most two hidden worker processes and records a lease
   for each. Before every constrained stage, a worker writes a private resource
   request; TaskManager alone grants download (2), ASR (1), and LLM (1) permits.
3. Download events update exact bytes, speed, and download ETA. Later stages
   report a named stage and checkpoint activity; they never pretend to have
   download speed.
4. Pause first prevents new worker launches. A running worker receives a
   cooperative pause command. It finishes the current atomic call, writes
   `paused` at the next safe checkpoint, and exits with a recognized code.
5. Resume requeues the same task id and work directory. Completed validated
   artifacts are skipped; partial media uses downloader resume when supported.
6. Cancel first requests graceful stop. After a bounded timeout, only the
   leased child PID may be terminated. Its checkpoint and artifacts remain for
   inspection; it is never silently reported as completed.
7. Service restart checks every lease against PID and start marker. A live worker
   is reattached as an event-file observer and consumes later JSONL entries; a
   missing worker becomes `interrupted` and is resumable from its checkpoint.

## Concurrency and Resource Policy

The default policy is deliberately conservative:

- `max_pipeline_workers=2` limits all live workers.
- `max_download_workers=2` permits two network downloads.
- `max_asr_workers=1` permits one GPU/CPU transcription at a time.
- `max_llm_workers=1` serializes knowledge extraction until provider limits are
  configured per provider.

Workers acquire a resource slot at a stage boundary and release it before the
next stage. A worker may remain alive while queued for a scarce slot, but it
cannot perform that stage until granted. The UI shows `等待转写资源` or
`等待摘要资源`, not a fabricated speed or ETA.

## Dashboard Contract

The browser uses revisioned APIs:

- `POST /api/v1/tasks/import/bilibili` imports a saved local Bilibili series.
- `GET /api/v1/tasks` returns sanitized task summaries.
- `POST /api/v1/tasks/{task_id}/pause|resume|cancel` accepts
  `{expected_revision, command_id}`.
- `GET /api/v1/events?job_id=...` sends initial job, task, and bounded trace
  snapshots followed by incremental events.

Mission Control has a job-level queue summary and one card per active or selected
task. Each card displays PID-free lifecycle, named stage, exact transfer only
during download, checkpoint position, elapsed time, retry count, and its own
controls. A job-level pause applies to all eligible tasks; individual controls
affect exactly one task.

## Bilibili Migration

The existing `SeriesTaskBridge` and one-off `runtime.json` are compatibility
inputs only. Importing a Bilibili series creates ordinary tasks, one per part,
with task work directories and worker protocol events. The worker invokes the
existing Bilibili adapter/downloader and the established ASR and output modules.
The Dashboard QR login remains local; successful credentials are supplied to
new workers by the service and redacted from all persisted event data.

## Security and Failure Rules

- Bind only to `127.0.0.1`; keep session, Origin, and CSRF protections on every
  mutation endpoint.
- Allow TaskManager to control only PIDs it created and has a current lease for.
- Never persist secrets in SQLite, checkpoints, stdout logs, SSE, errors, or
  browser responses.
- Validate every artifact before marking its stage durable.
- Convert unexpected worker exit to `interrupted` or `failed` with a sanitized
  reason, preserving the most recent checkpoint.

## Acceptance Criteria

1. Two Bilibili works can run concurrently as separate child processes and show
   distinct task ids, stages, and real download telemetry in Dashboard.
2. Pausing one task does not pause another; pausing a job prevents new tasks and
   safely pauses its existing tasks.
3. Restarting the Dashboard while a worker is alive restores the task without
   starting a duplicate process; an absent leased PID is marked resumable.
4. Resuming a partially completed Bilibili series skips all completed parts and
   validated artifacts.
5. No API, event, SQLite record, page, or worker log includes credentials,
   command lines, or arbitrary filesystem paths.
