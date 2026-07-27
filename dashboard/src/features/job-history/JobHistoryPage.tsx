import { useEffect, useMemo, useState } from "react";
import { Button, Card, Select, Text } from "@fluentui/react-components";

import { DashboardRequestError, getJson, postJson } from "../../api/client";
import type { JobItem, JobStatus, JobSummary } from "../../api/schema";

const statuses: readonly JobStatus[] = ["queued", "running", "pause_requested", "paused", "partial", "completed", "failed"];
type FilterStatus = "all" | JobStatus;

function isJobSummary(value: unknown): value is JobSummary {
  return typeof value === "object" && value !== null
    && "job_id" in value && typeof value.job_id === "string"
    && "status" in value && typeof value.status === "string" && statuses.includes(value.status as JobStatus)
    && "revision" in value && typeof value.revision === "number"
    && "platform" in value && typeof value.platform === "string"
    && "creator_name" in value && typeof value.creator_name === "string"
    && "total_items" in value && typeof value.total_items === "number"
    && "completed_items" in value && typeof value.completed_items === "number"
    && "failed_items" in value && typeof value.failed_items === "number"
    && "unsupported_items" in value && typeof value.unsupported_items === "number"
    && "updated_at" in value && typeof value.updated_at === "string";
}

function isJobItem(value: unknown): value is JobItem {
  return typeof value === "object" && value !== null
    && "source_id" in value && typeof value.source_id === "string"
    && "processing_status" in value && typeof value.processing_status === "string"
    && "retryable" in value && typeof value.retryable === "boolean"
    && "stage_progress" in value && typeof value.stage_progress === "number"
    && "overall_progress" in value && typeof value.overall_progress === "number"
    && "last_error" in value && (typeof value.last_error === "string" || value.last_error === null)
    && "updated_at" in value && typeof value.updated_at === "string";
}

function isJobUpdate(value: unknown): value is Pick<JobSummary, "job_id" | "status" | "revision"> {
  return typeof value === "object" && value !== null
    && "job_id" in value && typeof value.job_id === "string"
    && "status" in value && typeof value.status === "string" && statuses.includes(value.status as JobStatus)
    && "revision" in value && typeof value.revision === "number";
}

export function JobHistoryPage() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [loading, setLoading] = useState(false);
  const [itemsByJob, setItemsByJob] = useState<Record<string, JobItem[] | undefined>>({});
  const [itemsLoading, setItemsLoading] = useState<string | null>(null);
  const [retryingItem, setRetryingItem] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const result = await getJson<unknown>("/api/v1/jobs");
      if (!Array.isArray(result) || !result.every(isJobSummary)) throw new Error("invalid jobs response");
      setJobs(result);
    } catch {
      setJobs(null);
      setError("Job history is unavailable. Refresh to retry the local engine request.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function loadItems(jobId: string) {
    setItemsLoading(jobId);
    setError(null);
    try {
      const result = await getJson<unknown>(`/api/v1/jobs/${encodeURIComponent(jobId)}/items`);
      if (!Array.isArray(result) || !result.every(isJobItem)) throw new Error("invalid item response");
      setItemsByJob((current) => ({ ...current, [jobId]: result }));
    } catch {
      setError("Item actions were not confirmed by the local engine.");
    } finally {
      setItemsLoading(null);
    }
  }

  async function retryItem(job: JobSummary, item: JobItem) {
    if (!item.retryable) return;
    setRetryingItem(item.source_id);
    setError(null);
    setStatus(null);
    try {
      const result = await postJson<unknown>(
        `/api/v1/jobs/${encodeURIComponent(job.job_id)}/items/${encodeURIComponent(item.source_id)}/retry`,
        { expected_revision: job.revision },
      );
      if (!isJobUpdate(result)) throw new Error("invalid retry response");
      setJobs((current) => current?.map((candidate) => candidate.job_id === result.job_id
        ? { ...candidate, status: result.status as JobStatus, revision: result.revision }
        : candidate) ?? null);
      setStatus("Retry request confirmed by the local engine.");
      await loadItems(job.job_id);
    } catch (reason) {
      setError(reason instanceof DashboardRequestError && reason.code === "revision_conflict"
        ? "Retry was not confirmed because the job changed. Refresh history."
        : "Retry request was not confirmed by the local engine.");
    } finally {
      setRetryingItem(null);
    }
  }

  const visibleJobs = useMemo(
    () => jobs?.filter((job) => filter === "all" || job.status === filter) ?? [],
    [filter, jobs],
  );

  return (
    <section id="history" aria-label="Job history">
      <Card>
        <Text as="h2" size={600}>Job history</Text>
        <Select aria-label="Status filter" value={filter} onChange={(_, data) => setFilter(data.value as FilterStatus)}>
          <option value="all">All statuses</option>
          {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
        </Select>
        <Button appearance="secondary" onClick={refresh} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh history"}
        </Button>
        {error && <Text role="alert">{error}</Text>}
        {status && <Text role="status">{status}</Text>}
        {jobs?.length === 0 && <Text role="status">No jobs have been created yet.</Text>}
        {jobs !== null && jobs.length > 0 && visibleJobs.length === 0 && <Text role="status">No jobs match this status.</Text>}
        {visibleJobs.map((job) => (
          <Card key={job.job_id}>
            <Text as="h3" size={500}>{job.creator_name}</Text>
            <Text className="metric">{job.status} · {job.platform} · revision {job.revision}</Text>
            <Text>{job.failed_items} failed / {job.total_items} total</Text>
            <Button appearance="secondary" onClick={() => void loadItems(job.job_id)} disabled={itemsLoading === job.job_id}>
              {itemsLoading === job.job_id ? "Loading item actions..." : `Review item actions for ${job.creator_name}`}
            </Button>
            {itemsByJob[job.job_id]?.map((item) => (
              <div key={item.source_id}>
                <Text className="metric">{item.source_id} · {item.processing_status}</Text>
                {item.retryable && <Button
                  appearance="primary"
                  onClick={() => void retryItem(job, item)}
                  disabled={retryingItem !== null}
                >
                  {retryingItem === item.source_id ? `Retrying ${item.source_id}...` : `Retry ${item.source_id}`}
                </Button>}
              </div>
            ))}
          </Card>
        ))}
      </Card>
    </section>
  );
}
