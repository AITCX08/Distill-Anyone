import { useEffect, useState } from "react";
import { Button, Card, Select, Text } from "@fluentui/react-components";

import { getJson, postJson } from "../../api/client";
import type { JobSummary } from "../../api/schema";

type ArtifactSummary = {
  artifact_id: string;
  source_id: string;
  name: string;
  display_name: string;
};
type ArtifactContent = ArtifactSummary & { content: string };

function isJobSummary(value: unknown): value is JobSummary {
  return typeof value === "object" && value !== null
    && "job_id" in value && typeof value.job_id === "string"
    && "status" in value && typeof value.status === "string"
    && "revision" in value && typeof value.revision === "number"
    && "platform" in value && typeof value.platform === "string"
    && "creator_name" in value && typeof value.creator_name === "string"
    && "total_items" in value && typeof value.total_items === "number"
    && "completed_items" in value && typeof value.completed_items === "number"
    && "failed_items" in value && typeof value.failed_items === "number"
    && "unsupported_items" in value && typeof value.unsupported_items === "number"
    && "updated_at" in value && typeof value.updated_at === "string";
}

function isArtifactSummary(value: unknown): value is ArtifactSummary {
  return typeof value === "object" && value !== null
    && "artifact_id" in value && typeof value.artifact_id === "string" && value.artifact_id.length > 0
    && !value.artifact_id.includes("/") && !value.artifact_id.includes("\\")
    && "source_id" in value && typeof value.source_id === "string"
    && "name" in value && typeof value.name === "string"
    && "display_name" in value && typeof value.display_name === "string";
}

function isArtifactContent(value: unknown): value is ArtifactContent {
  return isArtifactSummary(value) && "content" in value && typeof value.content === "string";
}

export function ArtifactsPage() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactSummary[] | null>(null);
  const [content, setContent] = useState<ArtifactContent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  async function loadJobs() {
    setError(null);
    try {
      const result = await getJson<unknown>("/api/v1/jobs");
      if (!Array.isArray(result) || !result.every(isJobSummary)) throw new Error("invalid jobs response");
      setJobs(result);
      setSelectedJob((current) => result.some((job) => job.job_id === current) ? current : (result[0]?.job_id ?? null));
    } catch {
      setJobs(null);
      setError("无法加载任务历史，暂时不能浏览产物。");
    }
  }

  async function loadArtifacts(jobId: string) {
    setArtifacts(null);
    setContent(null);
    setError(null);
    setStatus(null);
    try {
      const result = await getJson<unknown>(`/api/v1/jobs/${encodeURIComponent(jobId)}/artifacts`);
      if (!Array.isArray(result) || !result.every(isArtifactSummary)) throw new Error("invalid artifacts response");
      setArtifacts(result);
    } catch {
      setArtifacts(null);
      setError("本地引擎尚未确认产物列表。");
    }
  }

  useEffect(() => { void loadJobs(); }, []);
  useEffect(() => { if (selectedJob) void loadArtifacts(selectedJob); }, [selectedJob]);

  async function previewArtifact(artifact: ArtifactSummary) {
    if (!selectedJob) return;
    setError(null);
    setStatus(null);
    try {
      const result = await getJson<unknown>(`/api/v1/jobs/${encodeURIComponent(selectedJob)}/artifacts/${encodeURIComponent(artifact.artifact_id)}`);
      if (!isArtifactContent(result)) throw new Error("invalid artifact content");
      setContent(result);
    } catch {
      setContent(null);
      setError("本地引擎尚未确认文本预览。");
    }
  }

  async function copyPreview() {
    if (!content) return;
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(content.content);
      setStatus("预览内容已复制到本地剪贴板。");
    } catch {
      setError("当前浏览器无法使用剪贴板复制功能。");
    }
  }

  async function revealArtifact(artifact: ArtifactSummary) {
    if (!selectedJob) return;
    setError(null);
    setStatus(null);
    try {
      await postJson<unknown>(`/api/v1/jobs/${encodeURIComponent(selectedJob)}/artifacts/${encodeURIComponent(artifact.artifact_id)}/reveal`, {});
      setStatus("已发送打开本地文件夹的请求。");
    } catch {
      setError("本地引擎尚未确认打开文件夹的请求。");
    }
  }

  return (
    <section id="artifacts" aria-label="产物库">
      <Card>
        <Text as="h2" size={600}>产物库</Text>
        <Text>文本预览为只读；打开文件夹仅允许已列出的产物，页面不会显示实际路径。</Text>
        {jobs?.length === 0 && <Text role="status">没有可浏览产物的任务。</Text>}
        {jobs && jobs.length > 0 && <Select aria-label="产物所属任务" value={selectedJob ?? ""} onChange={(_, data) => setSelectedJob(data.value)}>
          {jobs.map((job) => <option key={job.job_id} value={job.job_id}>{job.creator_name} · {job.job_id}</option>)}
        </Select>}
        {error && <Text role="alert">{error}</Text>}
        {status && <Text role="status">{status}</Text>}
        {artifacts?.length === 0 && <Text role="status">此任务暂无可安全预览的文本产物。</Text>}
        {artifacts?.map((artifact) => (
          <Card key={artifact.artifact_id}>
            <Text as="h3" size={500}>{artifact.display_name}</Text>
            <Text className="metric">{artifact.name} · {artifact.source_id}</Text>
            <Button appearance="secondary" onClick={() => void previewArtifact(artifact)}>预览 {artifact.display_name}</Button>
            <Button appearance="secondary" onClick={() => void revealArtifact(artifact)}>打开所在文件夹 {artifact.display_name}</Button>
          </Card>
        ))}
        {content && <Card>
          <Text as="h3" size={500}>预览 · {content.display_name}</Text>
          <pre>{content.content}</pre>
          <Button appearance="primary" onClick={() => void copyPreview()}>复制预览内容</Button>
        </Card>}
      </Card>
    </section>
  );
}
