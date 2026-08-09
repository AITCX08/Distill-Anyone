import { useCallback, useEffect, useState } from "react";
import { subscribeToEvents } from "../../api/events";
import type { DashboardEvent } from "../../api/schema";
import { MAX_TRACE_ENTRIES } from "./LiveTrace";
import type { MissionJob } from "./MissionControls";
import type { ProgressSnapshot } from "./MissionControlPage";

const countKeys = ["total", "active", "completed", "failed", "retry", "unsupported", "queued", "enumerated"] as const;

export type MissionControlState = {
  snapshot: ProgressSnapshot;
  job: MissionJob | null;
  traceEntries: readonly string[];
};

export type MissionControlModel = MissionControlState & {
  updateJob: (job: MissionJob) => void;
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
    && isFiniteNumber(job.revision);
}

function jobFromSnapshot(data: Record<string, unknown>, jobId: string): MissionJob | null {
  if (!Array.isArray(data.jobs)) return null;
  return data.jobs.find((job): job is MissionJob => isMissionJob(job) && job.job_id === jobId) ?? null;
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

export function useMissionControl(): MissionControlModel | null {
  const [state, setState] = useState<MissionControlState | null>(null);

  useEffect(() => {
    const subscription = subscribeToEvents((event) => {
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

  return state ? { ...state, updateJob } : null;
}
