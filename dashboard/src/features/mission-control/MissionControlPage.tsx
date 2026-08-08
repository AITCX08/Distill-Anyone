import { Card, ProgressBar, Text } from "@fluentui/react-components";
import { ActiveItemRow, type ActiveItem } from "./ActiveItemRow";
import { LiveTrace } from "./LiveTrace";
import { MissionControls, type MissionJob } from "./MissionControls";

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
  return (
    <section id="mission" aria-label="任务执行台">
      <Card>
        <Text as="h2" size={600}>任务执行台</Text>
        <Text className="metric">任务 {snapshot.job_id} · 进行中 {snapshot.counts.active}/{snapshot.counts.total}</Text>
        <ProgressBar value={snapshot.overall_progress} aria-label="总体进度" />
        <Text>已完成 {snapshot.counts.completed}/{snapshot.counts.total} · 失败 {snapshot.counts.failed} · 等待重试 {snapshot.counts.retry}</Text>
        <Text className="metric">
          预计总剩余时间 {formatDuration(snapshot.eta_total_seconds)} · 当前任务预计 {formatDuration(snapshot.eta_active_slowest_seconds)}
        </Text>
        {job && <MissionControls
          job={job}
          retryableFailures={snapshot.counts.failed > 0 || snapshot.counts.retry > 0}
          onJobUpdated={onJobUpdated}
        />}
      </Card>

      <div>
        {snapshot.active_items.map((item) => (
          <ActiveItemRow key={item.source_id} item={item} />
        ))}
      </div>
      <LiveTrace entries={traceEntries} />
    </section>
  );
}
