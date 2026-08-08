import { Button, Text } from "@fluentui/react-components";
import { useState } from "react";
import { DashboardRequestError, postJson } from "../../api/client";
import { jobStatusLabel } from "../../i18n/zh";

export type MissionJob = {
  job_id: string;
  status: string;
  revision: number;
  read_only?: boolean;
};

type Action = "pause" | "resume" | "retry-failed";

const jobStatuses = new Set(["created", "queued", "running", "pause_requested", "paused", "partial", "completed", "failed"]);

function isConfirmedJob(value: unknown, expectedJobId: string): value is MissionJob {
  if (typeof value !== "object" || value === null) return false;
  const job = value as Record<string, unknown>;
  return job.job_id === expectedJobId
    && typeof job.status === "string"
    && jobStatuses.has(job.status)
    && typeof job.revision === "number"
    && Number.isFinite(job.revision)
    && job.revision >= 0;
}

function actionPath(jobId: string, action: Action): string {
  return `/api/v1/jobs/${encodeURIComponent(jobId)}/${action}`;
}

function errorMessage(error: unknown): string {
  if (error instanceof DashboardRequestError && error.status === 409 && error.code === "revision_conflict") {
    return "任务状态已变化，请等待下一次服务端刷新后再试。";
  }
  if (error instanceof DashboardRequestError && error.code === "offline") {
    return "连接已断开，操作尚未确认。";
  }
  return "操作尚未确认，请查看下一次服务端刷新。";
}

export function MissionControls({
  job,
  retryableFailures,
  onJobUpdated,
}: {
  job: MissionJob;
  retryableFailures: boolean;
  onJobUpdated: (job: MissionJob) => void;
}) {
  const [busyAction, setBusyAction] = useState<Action | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function run(action: Action) {
    setBusyAction(action);
    setMessage(null);
    try {
      const updated = await postJson<unknown>(actionPath(job.job_id, action), { expected_revision: job.revision });
      if (!isConfirmedJob(updated, job.job_id)) throw new DashboardRequestError(200, "invalid_response");
      onJobUpdated(updated);
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusyAction(null);
    }
  }

  const canPause = job.status === "queued" || job.status === "running";
  const canResume = job.status === "pause_requested" || job.status === "paused" || job.status === "partial" || job.status === "failed";

  return (
    <div aria-label="任务控制">
      <Text role="status">任务状态：{jobStatusLabel(job.status)}</Text>
      {job.read_only && <Text role="status">此任务由外部进程执行，仅供监控。</Text>}
      {!job.read_only && canPause && <Button onClick={() => run("pause")} disabled={busyAction !== null}>暂停任务</Button>}
      {!job.read_only && canResume && <Button onClick={() => run("resume")} disabled={busyAction !== null}>继续任务</Button>}
      {!job.read_only && retryableFailures && <Button onClick={() => run("retry-failed")} disabled={busyAction !== null}>重试失败项目</Button>}
      {message && <Text role="status">{message}</Text>}
    </div>
  );
}
