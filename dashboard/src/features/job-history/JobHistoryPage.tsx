import { useEffect, useMemo, useState } from "react";
import { Button, Card, Select, Text } from "@fluentui/react-components";

import { getJson } from "../../api/client";
import type { JobStatus, JobSummary } from "../../api/schema";

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

export function JobHistoryPage() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        {jobs?.length === 0 && <Text role="status">No jobs have been created yet.</Text>}
        {jobs !== null && jobs.length > 0 && visibleJobs.length === 0 && <Text role="status">No jobs match this status.</Text>}
        {visibleJobs.map((job) => (
          <Card key={job.job_id}>
            <Text as="h3" size={500}>{job.creator_name}</Text>
            <Text className="metric">{job.status} · {job.platform} · revision {job.revision}</Text>
            <Text>{job.failed_items} failed / {job.total_items} total</Text>
          </Card>
        ))}
      </Card>
    </section>
  );
}
