# Controlled Series Runner Design

> **Superseded:** the release architecture is now [Worker-Orchestrated Distillation](2026-08-09-worker-orchestrated-distillation-design.md). This document remains as historical context for legacy `runtime.json` jobs only; new series are imported as ordinary isolated worker tasks.

## Goal

Make imported Bilibili series first-class Dashboard jobs: live download progress,
redacted execution trace, safe pause, and checkpointed resume. Existing completed
parts must remain reusable.

## Problem

`SeriesTaskBridge` currently mirrors `data/series/<bvid>/state.json` as a
read-only job. The one-off series script only writes coarse stages, so the
Dashboard has no byte totals, transfer speed, ETA, trace entries, process owner,
or control channel. Its existing pause/resume APIs therefore cannot act on the
external process.

## Design

### 1. Durable control and telemetry state

Each series gets `data/series/<bvid>/runtime.json` alongside its existing
checkpoint file. It contains only non-sensitive state:

- lifecycle status: `running`, `pause_requested`, `paused`, `completed`, or `failed`;
- active part and stage;
- transfer fields: downloaded bytes, optional total bytes, bytes/second, and ETA;
- an append-only, bounded execution trace;
- a monotonic revision and timestamps.

Writes are atomic. The existing `state.json` remains the authoritative artifact
checkpoint, so previously completed parts continue to be skipped.

### 2. Controlled runner

The series runner becomes a small controller around the current checkpointed
pipeline. It reads `runtime.json` at safe boundaries:

- download pause: honor after a current download callback has returned and before
  starting the next pipeline stage;
- ASR/LLM pause: finish the currently in-flight atomic call, then stop before the
  next part or stage;
- resume: start a new local runner process, reuse transcripts/cleaned knowledge,
  and continue from the first unfinished stage.

The controller records its process identifier only for local liveness reporting;
the Dashboard never exposes it. It clears stale ownership on startup.

### 3. Dashboard control API and UI

The series bridge projects `runtime.json` into the normal job state and progress
snapshot. Imported-series jobs are no longer labelled read-only. New endpoints
validate local session and revision, then set `pause_requested` or start a
checkpointed resume process. The mission card exposes:

- current part and named stage;
- transfer amount, total, speed, and ETA when a download is active;
- stage-specific indeterminate progress for ASR/LLM, instead of false `0 KB/s`;
- live trace lines;
- `暂停任务` while running, `恢复任务` while paused/failed.

The button acknowledgement is immediate; a `暂停中` state remains until the
runner reaches its next safe boundary.

### 4. Failure handling

If the runner exits unexpectedly, the controller writes a sanitized failure
message and keeps checkpoints intact. Dashboard resume is available only after
the cause is displayed. Login-required is represented as a paused `等待登录`
state and directs the user to the local Dashboard QR flow; it never opens an
external browser QR page.

## Data Flow

```text
Dashboard pause/resume API
        |                         |
        v                         v
runtime.json <---- controlled series runner ----> state.json / artifacts
        |
        v
SeriesTaskBridge -> SSE progress.snapshot + job.updated -> Mission Control
```

## Tests and Acceptance

- Unit test runtime state atomic persistence and revision checks.
- Unit test bridge maps transfer telemetry and trace into a progress snapshot.
- Unit test pause requests stop at a safe boundary and resume preserves completed
  parts.
- API test verifies imported-series pause/resume control, including a stale
  revision conflict.
- UI test verifies the button labels and the distinction between download metrics
  and an indeterminate ASR/LLM stage.
- Manual acceptance on the current 8-part series: Dashboard shows `6/8`, then
  real telemetry for parts 7 and 8 after login, and pause/resume never redoes a
  completed part.
