import { Button, Text } from "@fluentui/react-components";
import { useState } from "react";
import { DashboardRequestError, postJson } from "../../api/client";

export type MissionJob = {
  job_id: string;
  status: string;
  revision: number;
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
    return "Job changed on the server. Wait for the next snapshot before retrying.";
  }
  if (error instanceof DashboardRequestError && error.code === "offline") {
    return "Connection lost. Action was not confirmed.";
  }
  return "Action was not confirmed. Check the next server snapshot.";
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
    <div aria-label="Job controls">
      {canPause && <Button onClick={() => run("pause")} disabled={busyAction !== null}>Pause job</Button>}
      {canResume && <Button onClick={() => run("resume")} disabled={busyAction !== null}>Resume job</Button>}
      {retryableFailures && <Button onClick={() => run("retry-failed")} disabled={busyAction !== null}>Retry failed items</Button>}
      {message && <Text role="status">{message}</Text>}
    </div>
  );
}
