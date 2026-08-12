import { Button, Text } from "@fluentui/react-components";

import { ProgressSummary } from "../../components/ProgressSummary";
import { stageLabel } from "../../i18n/zh";
import type { MissionJob } from "./MissionControls";
import type { ProgressSnapshot } from "./MissionControlPage";

function formatDuration(value: number | null): string {
  if (value === null) return "估算中";
  const seconds = Math.round(value);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function formatBytes(value: number): string {
  return value >= 1024 * 1024 ? `${(value / (1024 * 1024)).toFixed(1)} MB` : `${(value / 1024).toFixed(1)} KB`;
}

function headingFor(job: MissionJob | null | undefined): string {
  const names = [job?.creator_name, job?.display_title].filter((value): value is string => !!value?.trim());
  return names.join(" · ") || "当前蒸馏任务";
}

function formatCompletedAt(value: string | undefined): string {
  if (!value) return "已完成";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "已完成" : date.toLocaleString("zh-CN", { hour12: false });
}

export function MissionOverview({
  snapshot,
  job,
  jobStatus,
  onViewArtifacts,
  onRevealOutput,
}: {
  snapshot: ProgressSnapshot;
  job?: MissionJob | null;
  jobStatus?: string;
  onViewArtifacts?: (jobId: string) => void;
  onRevealOutput?: (jobId: string) => void;
}) {
  const active = snapshot.active_items[0] ?? null;
  const status = job?.status ?? jobStatus;
  const paused = status === "paused" || status === "pause_requested";
  const completed = status === "completed";
  const empty = !job && snapshot.counts.total === 0;
  const downloading = active?.stage === "downloading";
  const stage = paused ? "已暂停" : active ? stageLabel(active.stage) : empty ? "等待创建任务" : "暂无活动任务";
  const throughput = paused ? "已暂停" : downloading && active.bytes_per_second > 0 ? `${formatBytes(active.bytes_per_second)}/秒` : "仅下载时显示";

  if (completed) {
    return <section className="mission-overview mission-overview--completed" aria-label="任务交付摘要">
      <div className="mission-overview__title">
        <div><Text as="h2" size={600}>{headingFor(job)}</Text><Text>任务已完成，可查看已交付的本地内容。</Text></div>
        <Text className="metric">已完成 {snapshot.counts.completed}/{snapshot.counts.total}</Text>
      </div>
      <div className="mission-metrics">
        <div><Text>完成时间</Text><strong>{formatCompletedAt(job?.completed_at)}</strong></div>
        <div><Text>已生成产物</Text><strong>{job?.artifact_count ?? snapshot.counts.completed}</strong></div>
        <div><Text>保存位置</Text><strong>在任务详情中查看</strong></div>
      </div>
      <div className="mission-overview__actions">
        {job && <Button appearance="primary" onClick={() => onViewArtifacts?.(job.job_id)}>查看产物</Button>}
        {job && onRevealOutput && <Button appearance="secondary" onClick={() => onRevealOutput(job.job_id)}>打开保存位置</Button>}
      </div>
    </section>;
  }

  return <section className="mission-overview" aria-label="任务总览卡片">
    <div className="mission-overview__title">
      <div>
        <Text as="h2" size={600}>{empty ? "当前没有正在追踪的蒸馏任务" : headingFor(job)}</Text>
        <Text>{empty ? "创建任务后，这里会持续显示总体进度、执行阶段与任务数量。" : "当前任务概览"}</Text>
      </div>
      <Text className="metric">已完成 {snapshot.counts.completed}/{snapshot.counts.total}</Text>
    </div>
    <ProgressSummary progress={snapshot.overall_progress} stage={stage} counts={{ completed: snapshot.counts.completed, active: snapshot.counts.active, queued: snapshot.counts.queued, total: snapshot.counts.total }} />
    <div className="mission-metrics mission-metrics--telemetry">
      <div><Text>实时下载速度</Text><strong className="metric">{throughput}</strong></div>
      <div><Text>预计总剩余时间</Text><strong className="metric">{paused ? "恢复后估算" : formatDuration(snapshot.eta_total_seconds)}</strong></div>
    </div>
  </section>;
}
