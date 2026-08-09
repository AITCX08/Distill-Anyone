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

export function MissionOverview({ snapshot, jobStatus }: { snapshot: ProgressSnapshot; jobStatus?: string }) {
  const active = snapshot.active_items[0] ?? null;
  const percent = Math.round(snapshot.overall_progress * 100);
  const paused = jobStatus === "paused" || jobStatus === "pause_requested";
  const downloading = active?.stage === "downloading";
  const stage = paused ? "已暂停" : active ? stageLabel(active.stage) : "暂无活动任务";
  const throughput = paused ? "暂停中" : downloading && active.bytes_per_second > 0 ? `${formatBytes(active.bytes_per_second)}/秒` : "仅下载时显示";
  const eta = paused ? "恢复后估算" : snapshot.eta_total_seconds === null ? "估算中" : formatDuration(snapshot.eta_total_seconds);

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
      <div><Text>当前阶段</Text><strong>{stage}</strong></div>
      <div><Text>实时下载速度</Text><strong className="metric">{throughput}</strong></div>
      <div><Text>预计总剩余时间</Text><strong className="metric">{eta}</strong></div>
    </div>
  </section>;
}
