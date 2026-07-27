import { useEffect, useState } from "react";
import { subscribeToEvents } from "../../api/events";
import type { DashboardEvent } from "../../api/schema";
import type { ProgressSnapshot } from "./MissionControlPage";

const countKeys = ["total", "active", "completed", "failed", "retry", "unsupported", "queued", "enumerated"] as const;

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

export function useMissionControl(): ProgressSnapshot | null {
  const [snapshot, setSnapshot] = useState<ProgressSnapshot | null>(null);

  useEffect(() => {
    const subscription = subscribeToEvents((event) => {
      const nextSnapshot = snapshotFromEvent(event);
      if (nextSnapshot) setSnapshot(nextSnapshot);
    });
    return () => subscription.close();
  }, []);

  return snapshot;
}
