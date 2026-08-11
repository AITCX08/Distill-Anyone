import { useCallback, useEffect, useState } from "react";
import { subscribeToEvents } from "../../api/events";
import type { DashboardEvent } from "../../api/schema";
import { MAX_TRACE_ENTRIES } from "./LiveTrace";
import type { MissionJob } from "./MissionControls";
import type { ProgressSnapshot } from "./MissionControlPage";
import type { WorkerTask } from "./TaskControlCard";

const countKeys = ["total", "active", "completed", "failed", "retry", "unsupported", "queued", "enumerated"] as const;

export type MissionControlState = {
  snapshot: ProgressSnapshot;
  job: MissionJob | null;
  traceEntries: readonly string[];
  tasks: readonly WorkerTask[];
};

export type MissionControlModel = MissionControlState & {
  updateJob: (job: MissionJob) => void;
  updateTask: (task: WorkerTask) => void;
};

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isOptionalFiniteNumber(value: unknown): boolean {
  return value === null || isFiniteNumber(value);
}

function isProgressCounts(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return false;
  const counts = value as Record<string, unknown>;
  return countKeys.every((key) => isFiniteNumber(counts[key]));
}

function isActiveItem(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return typeof item.source_id === "string"
    && typeof item.title === "string"
    && isFiniteNumber(item.row_id)
    && typeof item.stage === "string"
    && isOptionalFiniteNumber(item.stage_progress)
    && isFiniteNumber(item.overall_progress)
    && isFiniteNumber(item.completed_bytes)
    && isOptionalFiniteNumber(item.total_bytes)
    && isFiniteNumber(item.bytes_per_second)
    && isOptionalFiniteNumber(item.download_eta_seconds)
    && isFiniteNumber(item.audio_completed_seconds)
    && isOptionalFiniteNumber(item.audio_total_seconds)
    && isOptionalFiniteNumber(item.asr_rtf);
}

function isProgressSnapshot(value: unknown): value is ProgressSnapshot {
  if (typeof value !== "object" || value === null) return false;
  const snapshot = value as Record<string, unknown>;
  return typeof snapshot.job_id === "string"
    && isFiniteNumber(snapshot.revision)
    && isFiniteNumber(snapshot.overall_progress)
    && isFiniteNumber(snapshot.coverage)
    && isProgressCounts(snapshot.counts)
    && isOptionalFiniteNumber(snapshot.eta_total_seconds)
    && isOptionalFiniteNumber(snapshot.eta_active_slowest_seconds)
    && typeof snapshot.provisional_eta === "boolean"
    && Array.isArray(snapshot.active_items)
    && snapshot.active_items.every(isActiveItem);
}

function isMissionJob(value: unknown): value is MissionJob {
  if (typeof value !== "object" || value === null) return false;
  const job = value as Record<string, unknown>;
  return typeof job.job_id === "string"
    && typeof job.status === "string"
    && isFiniteNumber(job.revision)
    && (job.display_title === undefined || typeof job.display_title === "string")
    && (job.creator_name === undefined || typeof job.creator_name === "string")
    && (job.platform === undefined || typeof job.platform === "string")
    && (job.artifact_count === undefined || isFiniteNumber(job.artifact_count))
    && (job.completed_at === undefined || typeof job.completed_at === "string");
}

function jobFromSnapshot(data: Record<string, unknown>, jobId: string): MissionJob | null {
  if (!Array.isArray(data.jobs)) return null;
  return data.jobs.find((job): job is MissionJob => isMissionJob(job) && job.job_id === jobId) ?? null;
}

function isWorkerTransfer(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return false;
  const transfer = value as Record<string, unknown>;
  return isFiniteNumber(transfer.completed_bytes)
    && isFiniteNumber(transfer.total_bytes)
    && isFiniteNumber(transfer.bytes_per_second);
}

function isWorkerTask(value: unknown): value is WorkerTask {
  if (typeof value !== "object" || value === null) return false;
  const task = value as Record<string, unknown>;
  return typeof task.task_id === "string"
    && typeof task.job_id === "string"
    && typeof task.source_id === "string"
    && typeof task.display_title === "string"
    && task.display_title.trim().length > 0
    && (task.part_number === null || (isFiniteNumber(task.part_number) && task.part_number >= 1))
    && (task.delivery_state === "pending" || task.delivery_state === "available" || task.delivery_state === "unavailable")
    && typeof task.status === "string"
    && typeof task.stage === "string"
    && isFiniteNumber(task.revision)
    && isFiniteNumber(task.attempt)
    && isFiniteNumber(task.checkpoint_revision)
    && typeof task.updated_at === "string"
    && (task.completed_at === undefined || typeof task.completed_at === "string")
    && (task.error === undefined || typeof task.error === "string")
    && (task.transfer === undefined || isWorkerTransfer(task.transfer));
}

function workerTasksFromSnapshot(data: Record<string, unknown>): readonly WorkerTask[] {
  return Array.isArray(data.tasks) ? data.tasks.filter(isWorkerTask) : [];
}

function workerSnapshot(tasks: readonly WorkerTask[]): ProgressSnapshot {
  const jobId = tasks[0].job_id;
  const jobTasks = tasks.filter((task) => task.job_id === jobId);
  const completed = jobTasks.filter((task) => task.status === "completed").length;
  const active = jobTasks.filter((task) => task.status === "running" || task.status === "pause_requested").length;
  const failed = jobTasks.filter((task) => task.status === "failed" || task.status === "cancelled").length;
  const retry = jobTasks.filter((task) => task.status === "interrupted").length;
  return {
    job_id: jobId,
    revision: Math.max(...jobTasks.map((task) => task.revision)),
    overall_progress: jobTasks.length === 0 ? 0 : completed / jobTasks.length,
    coverage: jobTasks.length === 0 ? 0 : completed / jobTasks.length,
    counts: {
      total: jobTasks.length,
      active,
      completed,
      failed,
      retry,
      unsupported: 0,
      queued: jobTasks.filter((task) => task.status === "pending").length,
      enumerated: jobTasks.length,
    },
    eta_total_seconds: null,
    eta_active_slowest_seconds: null,
    provisional_eta: true,
    active_items: [],
  };
}

function workerJob(tasks: readonly WorkerTask[]): MissionJob {
  const snapshot = workerSnapshot(tasks);
  const statuses = tasks.map((task) => task.status);
  const status = statuses.every((value) => value === "completed")
    ? "completed"
    : statuses.some((value) => value === "running" || value === "pause_requested")
      ? "running"
      : statuses.some((value) => value === "paused")
        ? "paused"
        : statuses.some((value) => value === "failed")
          ? "failed"
          : "queued";
  const latestUpdate = tasks.reduce((latest, task) => task.updated_at > latest ? task.updated_at : latest, tasks[0]?.updated_at ?? "");
  return {
    job_id: snapshot.job_id,
    status,
    revision: snapshot.revision,
    display_title: tasks[0]?.display_title,
    platform: tasks[0]?.source_id.startsWith("bilibili_") ? "bilibili" : undefined,
    artifact_count: tasks.filter((task) => task.delivery_state === "available").length,
    completed_at: status === "completed" ? latestUpdate : undefined,
    read_only: true,
  };
}

function workerTraceEntries(data: Record<string, unknown>, tasks: readonly WorkerTask[]): readonly string[] {
  if (typeof data.task_traces !== "object" || data.task_traces === null) return [];
  const traces = data.task_traces as Record<string, unknown>;
  return tasks.flatMap((task) => {
    const lines = traces[task.task_id];
    return Array.isArray(lines) && lines.every((line) => typeof line === "string")
      ? lines.map((line) => `${task.source_id}: ${line}`)
      : [];
  }).slice(-MAX_TRACE_ENTRIES);
}

export function snapshotTraceEntries(data: Record<string, unknown>, jobId: string): readonly string[] {
  if (typeof data.traces !== "object" || data.traces === null) return [];
  const lines = (data.traces as Record<string, unknown>)[jobId];
  return Array.isArray(lines) && lines.every((line) => typeof line === "string")
    ? lines.slice(-MAX_TRACE_ENTRIES) as string[]
    : [];
}

function traceFromEvent(event: DashboardEvent): { jobId: string; line: string } | null {
  if (event.eventType !== "trace.appended") return null;
  const payload = event.data.payload;
  if (typeof payload !== "object" || payload === null) return null;
  const trace = payload as Record<string, unknown>;
  return typeof trace.job_id === "string" && typeof trace.line === "string"
    ? { jobId: trace.job_id, line: trace.line }
    : null;
}

function snapshotFromEvent(event: DashboardEvent): ProgressSnapshot | null {
  if (event.eventType === "snapshot") {
    const snapshots = event.data.progress_snapshots;
    if (!Array.isArray(snapshots)) return null;
    return snapshots.find(isProgressSnapshot) ?? null;
  }

  const payload = event.data.payload;
  if (typeof payload !== "object" || payload === null) return null;
  const snapshot = (payload as Record<string, unknown>).snapshot;
  return isProgressSnapshot(snapshot) ? snapshot : null;
}

function workerModelFromSnapshot(event: DashboardEvent): MissionControlState | null {
  if (event.eventType !== "snapshot") return null;
  const tasks = workerTasksFromSnapshot(event.data);
  if (tasks.length === 0) return null;
  const jobId = tasks[0].job_id;
  const jobTasks = tasks.filter((task) => task.job_id === jobId);
  return {
    snapshot: workerSnapshot(jobTasks),
    job: workerJob(jobTasks),
    traceEntries: workerTraceEntries(event.data, jobTasks),
    tasks: jobTasks,
  };
}

export function useMissionControl(): MissionControlModel | null {
  const [state, setState] = useState<MissionControlState | null>(null);

  useEffect(() => {
    const subscription = subscribeToEvents((event) => {
      const workerModel = workerModelFromSnapshot(event);
      if (workerModel) {
        setState(workerModel);
        return;
      }
      const nextSnapshot = snapshotFromEvent(event);
      if (nextSnapshot) {
        const isReconnectSnapshot = Array.isArray(event.data.progress_snapshots);
        setState((current) => ({
          snapshot: nextSnapshot,
          job: isReconnectSnapshot
            ? jobFromSnapshot(event.data, nextSnapshot.job_id)
            : current?.snapshot.job_id === nextSnapshot.job_id ? current.job : null,
          traceEntries: isReconnectSnapshot
            ? snapshotTraceEntries(event.data, nextSnapshot.job_id)
            : current?.snapshot.job_id === nextSnapshot.job_id ? current.traceEntries : [],
          tasks: [],
        }));
        return;
      }
      const payload = event.data.payload;
      if (event.eventType === "job.updated" && isMissionJob(payload)) {
        setState((current) => current?.snapshot.job_id === payload.job_id
          ? { ...current, job: payload }
          : current);
      }
      const trace = traceFromEvent(event);
      if (trace) {
        setState((current) => current?.snapshot.job_id === trace.jobId
          ? { ...current, traceEntries: [...current.traceEntries, trace.line].slice(-MAX_TRACE_ENTRIES) }
          : current);
      }
    });
    return () => subscription.close();
  }, []);

  const updateJob = useCallback((job: MissionJob) => {
    setState((current) => current?.snapshot.job_id === job.job_id ? { ...current, job } : current);
  }, []);

  const updateTask = useCallback((task: WorkerTask) => {
    setState((current) => {
      if (!current || current.tasks.length === 0 || current.snapshot.job_id !== task.job_id) return current;
      const tasks = current.tasks.map((existing) => existing.task_id === task.task_id ? task : existing);
      return { ...current, tasks, snapshot: workerSnapshot(tasks), job: workerJob(tasks) };
    });
  }, []);

  return state ? { ...state, updateJob, updateTask } : null;
}
