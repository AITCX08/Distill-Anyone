import { ProgressBar, Text } from "@fluentui/react-components";

import { stageLabel } from "../../i18n/zh";
import type { ProgressSnapshot } from "./MissionControlPage";

function formatDuration(value: number | null): string {
  if (value === null) return "未知";
  const seconds = Math.round(value);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function formatBytes(value: number): string {
  return value >= 1024 * 1024 ? `${(value / (1024 * 1024)).toFixed(1)} MB` : `${(value / 1024).toFixed(1)} KB`;
}

export function MissionOverview({ snapshot }: { snapshot: ProgressSnapshot }) {
  const active = snapshot.active_items[0] ?? null;
  const percent = Math.round(snapshot.overall_progress * 100);
  const throughput = active && active.bytes_per_second > 0 ? `${formatBytes(active.bytes_per_second)}/秒` : "未知";

  return <section className="mission-overview" aria-label="任务概览">
    <div className="mission-overview__title">
      <div>
        <Text className="metric">任务 {snapshot.job_id}</Text>
        <Text as="h2" size={600}>当前任务概览</Text>
      </div>
      <Text className="metric">已完成 {snapshot.counts.completed}/{snapshot.counts.total}</Text>
    </div>
    <ProgressBar value={snapshot.overall_progress} aria-label="总体进度" />
    <div className="mission-metrics">
      <div><Text>总体进度</Text><strong>{percent}%</strong></div>
      <div><Text>当前阶段</Text><strong>{active ? stageLabel(active.stage) : "暂无活动任务"}</strong></div>
      <div><Text>实时吞吐</Text><strong className="metric">{throughput}</strong></div>
      <div><Text>预计总剩余时间</Text><strong className="metric">{formatDuration(snapshot.eta_total_seconds)}</strong></div>
    </div>
  </section>;
}
