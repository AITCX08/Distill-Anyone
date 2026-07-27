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
      setError("Artifacts are unavailable because job history could not be loaded.");
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
      setError("Artifact list was not confirmed by the local engine.");
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
      setError("Text preview was not confirmed by the local engine.");
    }
  }

  async function copyPreview() {
    if (!content) return;
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(content.content);
      setStatus("Preview copied to the local clipboard.");
    } catch {
      setError("Clipboard copy is unavailable in this browser.");
    }
  }

  async function revealArtifact(artifact: ArtifactSummary) {
    if (!selectedJob) return;
    setError(null);
    setStatus(null);
    try {
      await postJson<unknown>(`/api/v1/jobs/${encodeURIComponent(selectedJob)}/artifacts/${encodeURIComponent(artifact.artifact_id)}/reveal`, {});
      setStatus("Local folder reveal request sent.");
    } catch {
      setError("Local folder reveal was not confirmed by the local engine.");
    }
  }

  return (
    <section id="artifacts" aria-label="Artifacts">
      <Card>
        <Text as="h2" size={600}>Artifacts</Text>
        <Text>Text previews are read-only. Folder reveal uses an allowlisted artifact and never exposes its path.</Text>
        {jobs?.length === 0 && <Text role="status">No jobs are available for artifact browsing.</Text>}
        {jobs && jobs.length > 0 && <Select aria-label="Artifact job" value={selectedJob ?? ""} onChange={(_, data) => setSelectedJob(data.value)}>
          {jobs.map((job) => <option key={job.job_id} value={job.job_id}>{job.creator_name} · {job.job_id}</option>)}
        </Select>}
        {error && <Text role="alert">{error}</Text>}
        {status && <Text role="status">{status}</Text>}
        {artifacts?.length === 0 && <Text role="status">No safe text artifacts are available for this job.</Text>}
        {artifacts?.map((artifact) => (
          <Card key={artifact.artifact_id}>
            <Text as="h3" size={500}>{artifact.display_name}</Text>
            <Text className="metric">{artifact.name} · {artifact.source_id}</Text>
            <Button appearance="secondary" onClick={() => void previewArtifact(artifact)}>Preview {artifact.display_name}</Button>
            <Button appearance="secondary" onClick={() => void revealArtifact(artifact)}>Reveal {artifact.display_name}</Button>
          </Card>
        ))}
        {content && <Card>
          <Text as="h3" size={500}>Preview · {content.display_name}</Text>
          <pre>{content.content}</pre>
          <Button appearance="primary" onClick={() => void copyPreview()}>Copy preview</Button>
        </Card>}
      </Card>
    </section>
  );
}
