import { Text } from "@fluentui/react-components";
import { useState } from "react";
import { ActiveItemRow, type ActiveItem } from "./ActiveItemRow";
import { LiveTrace } from "./LiveTrace";
import { MissionControls, type MissionJob } from "./MissionControls";
import { MissionOverview } from "./MissionOverview";
import { SeriesRail } from "./SeriesRail";

export type ProgressSnapshot = {
  job_id: string;
  revision: number;
  overall_progress: number;
  coverage: number;
  counts: {
    total: number;
    active: number;
    completed: number;
    failed: number;
    retry: number;
    unsupported: number;
    queued: number;
    enumerated: number;
  };
  eta_total_seconds: number | null;
  eta_active_slowest_seconds: number | null;
  provisional_eta: boolean;
  active_items: ActiveItem[];
};

function formatDuration(value: number | null): string {
  if (value === null) return "--:--";
  const seconds = Math.round(value);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function MissionControlPage({
  snapshot,
  job = null,
  traceEntries = [],
  onJobUpdated = () => undefined,
}: {
  snapshot: ProgressSnapshot;
  job?: MissionJob | null;
  traceEntries?: readonly string[];
  onJobUpdated?: (job: MissionJob) => void;
}) {
  const [selectedRowId, setSelectedRowId] = useState<number | null>(null);
  const activeRowId = snapshot.active_items[0]?.row_id ?? null;

  return (
    <section id="mission" className="mission-control" aria-label="任务执行台">
      <MissionOverview snapshot={snapshot} />
      {job?.read_only && <SeriesRail
        total={snapshot.counts.total}
        completed={snapshot.counts.completed}
        active={snapshot.counts.active}
        failed={snapshot.counts.failed}
        selectedRowId={selectedRowId ?? activeRowId}
        onSelect={setSelectedRowId}
      />}
      <section className="mission-control__summary" aria-label="任务控制与状态">
        <Text>失败 {snapshot.counts.failed} · 等待重试 {snapshot.counts.retry} · 当前任务预计 {formatDuration(snapshot.eta_active_slowest_seconds)}</Text>
        {job && <MissionControls
          job={job}
          retryableFailures={snapshot.counts.failed > 0 || snapshot.counts.retry > 0}
          onJobUpdated={onJobUpdated}
        />}
      </section>
      <section className="execution-queue" aria-label="作品执行队列">
        <div className="execution-queue__heading"><Text as="h2" size={500}>作品执行队列</Text><Text className="metric">活动 {snapshot.counts.active}</Text></div>
        {snapshot.active_items.map((item) => (
          <ActiveItemRow key={item.source_id} item={item} />
        ))}
        {snapshot.active_items.length === 0 && <Text>当前没有正在执行的作品。</Text>}
      </section>
      <LiveTrace entries={traceEntries} />
    </section>
  );
}
