import { Text } from "@fluentui/react-components";
import { useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import { QueueTable } from "../../components/QueueTable";
import { StatusPill, type StatusTone } from "../../components/StatusPill";
import { stageLabel } from "../../i18n/zh";
import { ActiveItemRow, type ActiveItem } from "./ActiveItemRow";
import { LiveTrace } from "./LiveTrace";
import { MissionControls, type MissionJob } from "./MissionControls";
import { MissionOverview } from "./MissionOverview";
import { SeriesRail } from "./SeriesRail";
import { TaskDetailDrawer } from "./TaskDetailDrawer";
import { TaskControlActions, taskHeading, taskMeta, type WorkerTask } from "./TaskControlCard";

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

function taskTone(task: WorkerTask): StatusTone {
  if (task.status === "completed") return "success";
  if (task.status === "failed" || task.status === "cancelled") return "danger";
  if (task.status === "paused" || task.status === "interrupted") return "warning";
  if (task.status === "queued") return "waiting";
  return "active";
}

function taskStatusLabel(task: WorkerTask): string {
  if (task.status === "completed") return "已完成";
  if (task.status === "failed") return "失败";
  if (task.status === "paused") return "已暂停";
  if (task.status === "queued") return "等待中";
  return "进行中";
}

function taskProgress(task: WorkerTask): string {
  if (task.status === "completed") return "100%";
  if (!task.transfer || task.transfer.total_bytes <= 0) return "处理中";
  return `${Math.round(task.transfer.completed_bytes / task.transfer.total_bytes * 100)}%`;
}

export function MissionControlPage({
  snapshot,
  job = null,
  traceEntries = [],
  onJobUpdated = () => undefined,
  tasks = [],
  onTaskUpdated = () => undefined,
  onViewArtifacts = () => { window.location.hash = "#artifacts"; },
}: {
  snapshot: ProgressSnapshot;
  job?: MissionJob | null;
  traceEntries?: readonly string[];
  onJobUpdated?: (job: MissionJob) => void;
  tasks?: readonly WorkerTask[];
  onTaskUpdated?: (task: WorkerTask) => void;
  onViewArtifacts?: (jobId: string) => void;
}) {
  const [selectedRowId, setSelectedRowId] = useState<number | null>(null);
  const [detailItem, setDetailItem] = useState<ActiveItem | null>(null);
  const paused = job?.status === "paused" || job?.status === "pause_requested";
  const completed = job?.status === "completed";
  const displayedSnapshot = paused
    ? { ...snapshot, active_items: [], counts: { ...snapshot.counts, active: 0 } }
    : snapshot;
  const activeRowId = displayedSnapshot.active_items[0]?.row_id ?? null;

  return (
    <section id="mission" className="mission-control" aria-label="任务执行台">
      <PageHeader title="工作台" description="在本地查看任务进度、控制执行，并交付结构化内容。" actions={<a className="mission-create-link" href="#create">创建任务</a>} />
      <MissionOverview snapshot={displayedSnapshot} job={job} jobStatus={job?.status} onViewArtifacts={onViewArtifacts} />
      {job && (job.read_only || job.job_id.startsWith("imported-series-")) && <SeriesRail
        total={displayedSnapshot.counts.total}
        completed={displayedSnapshot.counts.completed}
        active={displayedSnapshot.counts.active}
        failed={displayedSnapshot.counts.failed}
        selectedRowId={selectedRowId ?? activeRowId}
        onSelect={setSelectedRowId}
      />}
      <section className="mission-control__summary" aria-label="任务控制与状态">
        <Text>{completed
          ? "任务已完成，产物已准备就绪。"
          : paused
            ? "任务已暂停，恢复后将从最近检查点继续。"
            : `失败 ${snapshot.counts.failed} · 等待重试 ${snapshot.counts.retry} · 当前任务预计 ${formatDuration(snapshot.eta_active_slowest_seconds)}`}</Text>
        {job && <MissionControls
          job={job}
          retryableFailures={displayedSnapshot.counts.failed > 0 || displayedSnapshot.counts.retry > 0}
          onJobUpdated={onJobUpdated}
        />}
      </section>
      <section className="execution-queue" aria-label="作品执行队列">
        <div className="execution-queue__heading"><Text as="h2" size={500}>作品执行队列</Text><Text className="metric">活动 {displayedSnapshot.counts.active}</Text></div>
        {tasks.length > 0 && <QueueTable
          ariaLabel="作品执行队列"
          items={tasks}
          getKey={(task) => task.task_id}
          renderTitle={taskHeading}
          renderMeta={taskMeta}
          renderStatus={(task) => <StatusPill tone={taskTone(task)} label={taskStatusLabel(task)} />}
          renderProgress={taskProgress}
          renderStage={(task) => stageLabel(task.stage)}
          renderUpdated={(task) => task.completed_at ? "已完成" : "处理中"}
          renderActions={(task) => <TaskControlActions task={task} onTaskUpdated={onTaskUpdated} />}
        />}
        {tasks.length === 0 && displayedSnapshot.active_items.map((item) => (
          <ActiveItemRow key={item.source_id} item={item} onInspect={setDetailItem} />
        ))}
        {displayedSnapshot.active_items.length === 0 && tasks.length === 0 && <Text>{paused
          ? "任务已暂停；恢复后会在此显示执行进度。"
          : completed
            ? "所有作品均已完成，可前往产物库查看。"
            : <>当前没有正在执行的作品。<a href="#create">新建任务</a></>}</Text>}
      </section>
      <LiveTrace entries={traceEntries} />
      {detailItem && <TaskDetailDrawer
        item={detailItem}
        onClose={() => setDetailItem(null)}
        onViewArtifacts={job ? () => onViewArtifacts(job.job_id) : undefined}
      />}
    </section>
  );
}
