import { Button, Card, ProgressBar, Text } from "@fluentui/react-components";
import { useState } from "react";

import { DashboardRequestError, postJson } from "../../api/client";
import type { WorkerTask } from "../../api/schema";
import { stageLabel } from "../../i18n/zh";

export type { WorkerTask } from "../../api/schema";

type Action = "pause" | "resume" | "cancel";

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

export function TaskControlCard({ task, onTaskUpdated }: { task: WorkerTask; onTaskUpdated?: (task: WorkerTask) => void }) {
  const [busy, setBusy] = useState<Action | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const downloading = task.stage === "downloading";
  const canPause = task.status === "running";
  const canResume = task.status === "paused" || task.status === "interrupted";
  const canCancel = task.status === "running" || task.status === "pause_requested";

  async function command(action: Action) {
    setBusy(action);
    setMessage(null);
    try {
      const updated = await postJson<WorkerTask>(pathFor(task, action), {
        expected_revision: task.revision,
        command_id: newCommandId(),
      });
      onTaskUpdated?.(updated);
    } catch (error) {
      setMessage(error instanceof DashboardRequestError && error.code === "revision_conflict"
        ? "任务状态已更新，请等待服务端刷新。"
        : "操作未确认，请检查连接后重试。");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="execution-row" aria-label={`${task.source_id} · ${stageLabel(task.stage)}`}>
      <div className="execution-row__identity">
        <Text as="h3">作品 {task.source_id}</Text>
        <Text className="execution-row__stage">{stageLabel(task.stage)}</Text>
      </div>
      {downloading && task.transfer ? <>
        <Text>{formatBytes(task.transfer.completed_bytes)} / {formatBytes(task.transfer.total_bytes)}</Text>
        <ProgressBar value={task.transfer.total_bytes > 0 ? task.transfer.completed_bytes / task.transfer.total_bytes : undefined} />
        <Text className="metric">{formatBytes(task.transfer.bytes_per_second)}/秒</Text>
      </> : <Text>正在{stageLabel(task.stage).replace(/中$/, "")}，暂不显示下载速度</Text>}
      <Text className="metric">检查点 #{task.checkpoint_revision} · 已尝试 {task.attempt} 次</Text>
      <div>
        {canPause && <Button onClick={() => command("pause")} disabled={busy !== null}>暂停任务</Button>}
        {canResume && <Button onClick={() => command("resume")} disabled={busy !== null}>继续任务</Button>}
        {canCancel && <Button onClick={() => command("cancel")} disabled={busy !== null}>取消任务</Button>}
      </div>
      {message && <Text role="status">{message}</Text>}
    </Card>
  );
}
