# Dashboard Creator Workbench Design

## Status

Approved direction: evolve the local Dashboard from a process monitor into a
creator-facing workbench. The product must explain what will be created, let a
creator choose where each new job is delivered, show human-readable source
titles throughout execution, and close every completed job with clear artifact
actions.

This design extends, but does not replace,
the worker-orchestrated runtime. `TaskManager` remains the only process owner,
workers retain their complete pipeline boundaries, and the Dashboard remains
loopback-only.

## Product Outcomes

- A creator can understand every requested output before starting a job.
- A job can use the configured default output directory or a per-job override.
- Task and job views lead with creator, series, part number, and work title;
  opaque IDs remain available only as secondary diagnostic metadata.
- A completed job leads directly to its artifacts and output folder.
- Progress, empty, blocked, failed, paused, and completed states each state the
  next useful action in Chinese.

## Scope and Non-goals

### In scope

- Guided creation flow with source inspection, output explanations, template
  previews, and destination selection.
- Per-job optional destination override with a persisted default destination.
- User-facing job and work display metadata.
- Artifact preview, download/open-folder actions, and completion summaries.
- Mission Control information hierarchy, readable states, and responsive,
  keyboard-accessible controls.

### Out of scope

- Cloud storage, multi-user workspaces, or remote Dashboard access.
- Arbitrary file-system browsing by browser JavaScript.
- Displaying credentials, raw worker payloads, process command lines, or raw
  diagnostic paths in SSE, traces, task lists, or error events.

## Experience Model

The Dashboard has three deliberately connected moments:

```text
Create
  inspect source -> choose deliverables -> choose destination -> create
      |
      v
Operate
  named job -> named works -> stage-specific progress -> task controls
      |
      v
Deliver
  completion summary -> preview artifacts -> reveal output folder -> reuse
```

The navigation labels remain concise: `任务作战台`, `新建任务`, `平台与登录`,
`任务历史`, and `产物库`. A page must not repeat opaque internal IDs as its
primary heading.

## Creation Flow

### Source inspection

The form starts with a source URL and platform selector. Inspecting the source
returns a creator/series summary, supported work count, skipped work count, and
login state. The Create button remains unavailable until this result is current.
Validation errors explain whether the URL, platform, login, or source content
requires attention.

### Deliverable selection

Deliverables are selectable cards in a labelled group. Each card has a purpose,
an estimated shape, and a `查看示例` action:

| Deliverable | User-facing description | Template preview |
| --- | --- | --- |
| 逐作品 Markdown | One readable note per source work | title, source summary, transcript outline, distilled notes |
| 蒸馏 Skill | A reusable method assembled from the collection | overview, principles, workflow, prompts, cautions |
| RAG 分块 | Search-ready knowledge fragments | source metadata, chunk title, content, retrieval tags |

`查看示例` opens an accessible Dialog with tabs. Samples are static,
representative templates only. Previewing does not inspect, create, or write
user files.

### Destination selection

The Dashboard maintains one local default destination. The creation form shows
the selected default and a checkbox named `本次使用其他保存位置`.

When the checkbox is selected, the creator can either enter a directory or use
`选择文件夹`. The latter calls a local server endpoint that invokes the platform
folder chooser without a console window. On platforms where a native picker is
not available, direct validated entry remains available.

The server normalizes and validates a candidate directory before a job is
created: it must be writable, be a directory or have a creatable parent, and
must not resolve to a system root. The selected path becomes the private job
destination. When not selected, the current private default destination is
copied to the job configuration so later default changes do not move an
in-progress job.

The full destination is shown only in the local creation confirmation and the
authenticated Job Details/Artifacts views. It is never included in task list
records, SSE snapshots, worker JSONL, traces, or sanitized errors.

## Job and Work Presentation

### Job overview

Mission Control leads with:

- `创作者 · 系列或任务标题`;
- platform and work count;
- lifecycle summary such as `已完成 8/8`;
- current phase only when work is active;
- an estimated completion time only when a meaningful estimate exists.

The opaque job ID moves into a collapsible `技术信息` section with a copy action.
After completion, the four telemetry cells become a delivery summary: completed
time, generated artifacts, destination, and a primary `查看产物` action. It must
not say `估算中` or `仅下载时显示` when no work is active.

### Work cards

Each card uses `第 N 集 · 原始作品标题` as its heading. The stable source ID is
secondary metadata. Cards display only metrics that apply to their stage:

- Downloading: transferred bytes, known total, speed, and transfer ETA.
- Waiting for a resource: named resource and queue position when known.
- Transcribing, cleaning, or summarizing: named stage, elapsed time, and last
  durable checkpoint, without invented transfer speed.
- Completed: generated artifact types and `查看产物`.
- Failed: concise sanitized reason, recovery hint, and `重试此作品`.

The existing pause, resume, cancel, and retry controls remain task-scoped and
revision-protected. Buttons provide progress labels and disable only while the
same task command is pending.

## Artifact Delivery

The Artifact Library groups files by human-readable job and work title. Each
entry provides file type, display name, generated time, size, inline preview
when text is supported, and a `打开所在文件夹` action. Completion summary actions
link to filtered artifacts for the selected job.

The reveal action remains server-allowlisted. The browser never constructs or
submits a file path for an existing artifact.

## Data and API Boundaries

### Private server records

Add a small local workspace settings record for the default destination and
extend persisted job request metadata with:

- display title and creator name;
- selected output kinds;
- `destination_mode` (`default` or `override`);
- normalized private destination;
- user-created timestamp and completion timestamp.

Worker payloads receive only the resolved destination reference required to
write artifacts. This field is never emitted in an event.

### Browser-safe display contract

Extend job/task API and SSE snapshot contracts with safe display fields:

- job: `display_title`, `creator_name`, `platform`, output kinds, completion
  summary, and artifact counts;
- task: `display_title`, `part_number`, output state, elapsed time, and stage
  specific telemetry;
- artifact: existing opaque identifier plus display name, type, size, timestamp,
  and user-safe source title.

Expose destination only through a local-session-protected job-details endpoint,
not through the broad task stream. The endpoint returns it solely for the
currently displayed local job. No path is persisted in events or traces.

### Local settings and folder selection

- `GET/PUT /api/v1/settings/output-directory` reads or changes the private
  default destination after local-session, Origin, CSRF, and directory
  validation checks.
- `POST /api/v1/directories/choose` opens the native folder chooser locally and
  returns the selected directory only to the requesting local session.
- `POST /api/v1/directories/validate` validates direct entry before job creation.
- Job creation accepts `destination_mode` and, for override mode, a validated
  destination token rather than trusting arbitrary path text a second time.

Tokens are short-lived, session-bound, and cannot be replayed as artifact paths.

## Visual and Interaction System

Use the existing Fluent UI v9 foundation, deep local-operations theme, and
teal accent. The density target is a desktop workbench: compact enough for
multiple work cards, but with clear type hierarchy and 44px minimum action
targets.

- Keep one dark theme; do not add decorative gradients or competing accents.
- Use Cards for meaningful task groups, not every small label.
- Use Dialog for templates and destination confirmation, Drawer for task
  details, Tooltip for secondary technical IDs, and Field/helper text for form
explanations.
- Preserve visible focus rings, semantic headings, labelled checkbox groups,
  live status announcements, contrast-safe inputs, and mobile single-column
  collapse.
- Render loading, zero-result, login-required, validation-error, offline, and
  completed states explicitly.

## Failure Handling

- A destination that becomes unavailable after job creation pauses the affected
  write stage with a sanitized `保存位置不可用` state; it does not silently fall
  back to another directory.
- Native folder picker failures leave the manual entry path available.
- Job metadata absent from older imported series falls back to stable source ID
  and part number, while background-safe metadata repair enriches it on the
  next source inspection or import.
- Incomplete source titles use `第 N 集` rather than blank headings.

## Verification and Acceptance

1. A creator can inspect a source, understand each output via template preview,
   select default or per-job destination, create a job, and see a readable
   confirmation.
2. A created job and every work card show titles; technical identifiers are not
   primary labels.
3. Active tasks show only stage-appropriate progress. Completed jobs show a
   delivery summary and no pending ETA wording.
4. The default destination persists locally. A job override remains fixed after
   the default changes; invalid or unwritable destinations cannot create jobs.
5. Artifact list and completion actions open the correct allowlisted local
   output; no event, task snapshot, trace, or sanitized error contains an
   absolute path.
6. Tests cover creation validation, preview dialogs, labels/fallbacks, path
   validation/token expiry, settings persistence, accessible task controls, API
   session/CSRF enforcement, and responsive build output.
