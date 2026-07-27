import { Card, ProgressBar, Text } from "@fluentui/react-components";

type ActiveItem = {
  source_id: string;
  title: string;
  row_id: number;
  stage: string;
  stage_progress: number | null;
  overall_progress: number;
  completed_bytes: number;
  total_bytes: number | null;
  bytes_per_second: number;
  download_eta_seconds: number | null;
  audio_completed_seconds: number;
  audio_total_seconds: number | null;
  asr_rtf: number | null;
};

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

function formatBytes(value: number): string {
  return value >= 1024 * 1024
    ? `${(value / (1024 * 1024)).toFixed(1)} MB`
    : `${(value / 1024).toFixed(1)} KB`;
}

function formatDuration(value: number | null): string {
  if (value === null) return "--:--";
  const seconds = Math.round(value);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function MissionControlPage({ snapshot }: { snapshot: ProgressSnapshot }) {
  return (
    <section id="mission" aria-label="Mission Control">
      <Card>
        <Text as="h2" size={600}>Mission Control</Text>
        <Text className="metric">Job {snapshot.job_id} · Active {snapshot.counts.active}/{snapshot.counts.total}</Text>
        <ProgressBar value={snapshot.overall_progress} aria-label="Overall progress" />
        <Text>Completed {snapshot.counts.completed}/{snapshot.counts.total} · Failed {snapshot.counts.failed} · Retry {snapshot.counts.retry}</Text>
        <Text className="metric">
          Overall ETA {formatDuration(snapshot.eta_total_seconds)} · Slowest active ETA {formatDuration(snapshot.eta_active_slowest_seconds)}
        </Text>
      </Card>

      <div>
        {snapshot.active_items.map((item) => (
          <Card key={item.source_id}>
            <Text as="h3">#{item.row_id} {item.title || item.source_id}</Text>
            <Text>{item.stage}</Text>
            {item.total_bytes === null
              ? <Text>Unknown total · {formatBytes(item.completed_bytes)} · {formatBytes(item.bytes_per_second)}/s</Text>
              : <Text>{formatBytes(item.completed_bytes)} / {formatBytes(item.total_bytes)}</Text>}
            <Text className="metric">{formatBytes(item.bytes_per_second)}/s</Text>
            {item.stage_progress === null
              ? <Text>Stage progress estimating</Text>
              : <ProgressBar value={item.stage_progress} aria-label={`${item.title || item.source_id} stage progress`} />}
          </Card>
        ))}
      </div>
    </section>
  );
}
