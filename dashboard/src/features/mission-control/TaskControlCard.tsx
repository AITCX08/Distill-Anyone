import { Button, Card, ProgressBar, Text } from "@fluentui/react-components";
import { useState } from "react";

import { DashboardRequestError, postJson } from "../../api/client";
import type { WorkerTask } from "../../api/schema";
import { stageLabel } from "../../i18n/zh";

export type { WorkerTask } from "../../api/schema";

type Action = "pause" | "resume" | "cancel" | "retry";

function formatBytes(value: number): string {
  return value >= 1024 * 1024 ? `${(value / (1024 * 1024)).toFixed(1)} MB` : `${(value / 1024).toFixed(1)} KB`;
}

function newCommandId(): string {
  return typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `cmd_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function pathFor(task: WorkerTask, action: Action): string {
  return `/api/v1/tasks/${encodeURIComponent(task.task_id)}/${action}`;
}

export function taskHeading(task: WorkerTask): string {
  return task.part_number ? `第 ${task.part_number} 集 · ${task.display_title}` : task.display_title;
}

function sourceBvid(sourceId: string): string | null {
  return /^bilibili_(BV[0-9A-Za-z]+)_p\d+$/i.exec(sourceId)?.[1] ?? null;
}

function compactDateTime(value: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(value);
  return match ? `${match[1]} ${match[2]}` : value;
}

export function taskMeta(task: WorkerTask): string {
  const source = sourceBvid(task.source_id) ?? `来源编号 ${task.source_id}`;
  const timestamp = compactDateTime(task.completed_at ?? task.updated_at);
  return task.status === "completed"
    ? `${source} · 完成于 ${timestamp}`
    : `${source} · 最后更新 ${timestamp}`;
}

export function TaskControlActions({ task, onTaskUpdated }: { task: WorkerTask; onTaskUpdated?: (task: WorkerTask) => void }) {
  const [busy, setBusy] = useState<Action | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const canPause = task.status === "running";
  const canResume = task.status === "paused" || task.status === "interrupted";
  const canCancel = task.status === "running" || task.status === "pause_requested";
  const canRetry = task.status === "failed" || task.status === "interrupted" || task.status === "cancelled";

  async function command(action: Action) {
    setBusy(action);
    setMessage(null);
    try {
      const updated = await postJson<Partial<WorkerTask>>(pathFor(task, action), {
        expected_revision: task.revision,
        command_id: newCommandId(),
      });
      onTaskUpdated?.({ ...task, ...updated });
    } catch (error) {
      setMessage(error instanceof DashboardRequestError && error.code === "revision_conflict"
        ? "任务状态已更新，请等待服务端刷新。"
        : "操作未确认，请检查连接后重试。");
    } finally {
      setBusy(null);
    }
  }

  return <div className="task-control-actions">
    {canPause && <Button onClick={() => void command("pause")} disabled={busy !== null}>暂停任务</Button>}{canResume && <Button onClick={() => void command("resume")} disabled={busy !== null}>继续任务</Button>}{canCancel && <Button onClick={() => void command("cancel")} disabled={busy !== null}>取消任务</Button>}{canRetry && <Button onClick={() => void command("retry")} disabled={busy !== null}>重试任务</Button>}
    {message && <Text role="status">{message}</Text>}
  </div>;
}

export function TaskControlCard({ task, onTaskUpdated }: { task: WorkerTask; onTaskUpdated?: (task: WorkerTask) => void }) {
  const transfer = task.transfer;
  const downloading = task.stage === "downloading" && transfer !== undefined;
  return <Card className="execution-row" aria-label={`${taskHeading(task)} · ${stageLabel(task.stage)}`}>
    <div className="execution-row__identity"><Text as="h3">{taskHeading(task)}</Text><Text className="metric">{task.delivery_state === "available" ? "产物可用" : task.delivery_state === "unavailable" ? "交付不可用" : "处理中"}</Text></div>
    <Text className="metric execution-row__meta">{taskMeta(task)}</Text>
    {downloading && transfer ? <><Text>{formatBytes(transfer.completed_bytes)} / {formatBytes(transfer.total_bytes)}</Text><ProgressBar value={transfer.total_bytes > 0 ? transfer.completed_bytes / transfer.total_bytes : undefined} /><Text className="metric">{formatBytes(transfer.bytes_per_second)}/秒</Text></> : task.status !== "completed" && <Text>正在{stageLabel(task.stage).replace("中", "")}，暂不显示下载速度</Text>}
    {task.error && <Text role="status">失败原因：{task.error}</Text>}
    <TaskControlActions task={task} onTaskUpdated={onTaskUpdated} />
  </Card>;
}
