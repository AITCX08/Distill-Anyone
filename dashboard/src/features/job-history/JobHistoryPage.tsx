import { useEffect, useMemo, useState } from "react";
import { Button, Card, Select, Text } from "@fluentui/react-components";

import { DashboardRequestError, getJson, postJson } from "../../api/client";
import type { JobItem, JobStatus, JobSummary } from "../../api/schema";
import { jobStatusLabel, platformLabel, stageLabel } from "../../i18n/zh";

const statuses: readonly JobStatus[] = ["queued", "running", "pause_requested", "paused", "partial", "completed", "failed"];
type FilterStatus = "all" | JobStatus;
type JobDetails = { job_id: string; display_title: string; creator_name: string; destination: string; artifact_count: number; completed_at: string | null };

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
    && "display_title" in value && typeof value.display_title === "string"
    && "part_number" in value && (typeof value.part_number === "number" || value.part_number === null)
    && "processing_status" in value && typeof value.processing_status === "string"
    && "retryable" in value && typeof value.retryable === "boolean"
    && "stage_progress" in value && typeof value.stage_progress === "number"
    && "overall_progress" in value && typeof value.overall_progress === "number"
    && "last_error" in value && (typeof value.last_error === "string" || value.last_error === null)
    && "completed_at" in value && (typeof value.completed_at === "string" || value.completed_at === null)
    && "updated_at" in value && typeof value.updated_at === "string";
}

function isJobDetails(value: unknown): value is JobDetails {
  return typeof value === "object" && value !== null
    && "job_id" in value && typeof value.job_id === "string"
    && "display_title" in value && typeof value.display_title === "string"
    && "creator_name" in value && typeof value.creator_name === "string"
    && "destination" in value && typeof value.destination === "string"
    && "artifact_count" in value && typeof value.artifact_count === "number"
    && "completed_at" in value && (typeof value.completed_at === "string" || value.completed_at === null);
}

function itemHeading(item: JobItem): string {
  return item.part_number === null ? item.display_title : `第 ${item.part_number} 集 · ${item.display_title}`;
}

function sourceBvid(sourceId: string): string | null {
  return /^bilibili_(BV[0-9A-Za-z]+)_p\d+$/i.exec(sourceId)?.[1] ?? null;
}

function compactDateTime(value: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(value);
  return match ? `${match[1]} ${match[2]}` : value;
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
  const [detailsByJob, setDetailsByJob] = useState<Record<string, JobDetails | undefined>>({});
  const [detailsLoading, setDetailsLoading] = useState<string | null>(null);
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
      setError("任务历史暂不可用，请刷新后重试连接本地引擎。");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetails(jobId: string) {
    setDetailsLoading(jobId);
    setError(null);
    try {
      const result = await getJson<unknown>(`/api/v1/jobs/${encodeURIComponent(jobId)}/details`);
      if (!isJobDetails(result)) throw new Error("invalid job details response");
      setDetailsByJob((current) => ({ ...current, [jobId]: result }));
    } catch {
      setError("暂时无法读取本地交付位置。");
    } finally {
      setDetailsLoading(null);
    }
  }

  async function revealOutput(jobId: string) {
    setError(null);
    try {
      await postJson(`/api/v1/jobs/${encodeURIComponent(jobId)}/reveal-output`, {});
    } catch {
      setError("无法打开本地保存位置。");
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
      setError("本地引擎尚未确认项目操作。");
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
      setStatus("本地引擎已确认重试请求。");
      await loadItems(job.job_id);
    } catch (reason) {
      setError(reason instanceof DashboardRequestError && reason.code === "revision_conflict"
        ? "任务状态已经变化，重试未确认；请刷新任务历史。"
        : "本地引擎尚未确认重试请求。");
    } finally {
      setRetryingItem(null);
    }
  }

  const visibleJobs = useMemo(
    () => jobs?.filter((job) => filter === "all" || job.status === filter) ?? [],
    [filter, jobs],
  );

  return (
    <section id="history" aria-label="任务历史">
      <Card>
        <Text as="h2" size={600}>任务历史</Text>
        <Select aria-label="状态筛选" value={filter} onChange={(_, data) => setFilter(data.value as FilterStatus)}>
          <option value="all">全部状态</option>
          {statuses.map((status) => <option key={status} value={status}>{jobStatusLabel(status)}</option>)}
        </Select>
        <Button appearance="secondary" onClick={refresh} disabled={loading}>
          {loading ? "正在刷新…" : "刷新历史"}
        </Button>
        {error && <Text role="alert">{error}</Text>}
        {status && <Text role="status">{status}</Text>}
        {jobs?.length === 0 && <Text role="status">尚未创建任务。</Text>}
        {jobs !== null && jobs.length > 0 && visibleJobs.length === 0 && <Text role="status">没有符合该状态的任务。</Text>}
        {visibleJobs.map((job) => (
          <Card key={job.job_id}>
            <Text as="h3" size={500}>{job.creator_name}</Text>
            <Text className="metric">{jobStatusLabel(job.status)} · {platformLabel(job.platform)} · 版本 {job.revision}</Text>
            <Text>失败 {job.failed_items} / 共 {job.total_items} 条</Text>
            <Button appearance="secondary" onClick={() => void loadItems(job.job_id)} disabled={itemsLoading === job.job_id}>
              {itemsLoading === job.job_id ? "正在加载项目操作…" : `查看 ${job.creator_name} 的项目操作`}
            </Button>
            <Button appearance="secondary" onClick={() => void loadDetails(job.job_id)} disabled={detailsLoading === job.job_id}>
              {detailsLoading === job.job_id ? "正在读取交付详情…" : "查看交付详情"}
            </Button>
            {detailsByJob[job.job_id] && <div>
              <Text>保存位置：{detailsByJob[job.job_id]?.destination}</Text>
              <Button appearance="secondary" onClick={() => void revealOutput(job.job_id)}>打开文件夹</Button>
            </div>}
            {itemsByJob[job.job_id]?.map((item) => (
              <div key={item.source_id}>
                <Text className="metric">{itemHeading(item)} · {stageLabel(item.processing_status)}</Text>
                <Text className="metric">
                  {sourceBvid(item.source_id) ?? `来源编号 ${item.source_id}`} · {item.completed_at
                    ? `完成于 ${compactDateTime(item.completed_at)}`
                    : `最后更新 ${compactDateTime(item.updated_at)}`}
                </Text>
                {item.last_error && <Text role="status">失败原因：{item.last_error}</Text>}
                {item.retryable && <Button
                  appearance="primary"
                  onClick={() => void retryItem(job, item)}
                  disabled={retryingItem !== null}
                >
                  {retryingItem === item.source_id ? `正在重试 ${item.source_id}…` : `重试 ${item.source_id}`}
                </Button>}
              </div>
            ))}
          </Card>
        ))}
      </Card>
    </section>
  );
}
