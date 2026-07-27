import { useState } from "react";
import { Button, Card, Checkbox, Field, Input, Select, Text } from "@fluentui/react-components";

import { DashboardRequestError, postJson } from "../../api/client";

type Output = "episodes" | "skill";

type Preview = {
  fingerprint: string;
  platform: string;
  creator_id: string;
  creator_name: string;
  total_items: number;
  processable_items: number;
  skipped_items: number;
  unsupported_items: number;
  auth_status: string;
};

type CreatedJob = { job_id: string; status: string; revision: number };

function isPreview(value: unknown): value is Preview {
  return typeof value === "object" && value !== null
    && "fingerprint" in value && typeof value.fingerprint === "string"
    && "creator_name" in value && typeof value.creator_name === "string"
    && "total_items" in value && typeof value.total_items === "number"
    && "processable_items" in value && typeof value.processable_items === "number";
}

function isCreatedJob(value: unknown): value is CreatedJob {
  return typeof value === "object" && value !== null
    && "job_id" in value && typeof value.job_id === "string"
    && "status" in value && typeof value.status === "string"
    && "revision" in value && typeof value.revision === "number";
}

function failureMessage(action: "preview" | "creation", error: unknown): string {
  if (error instanceof DashboardRequestError && error.code === "offline") {
    return `Local engine is offline. ${action === "preview" ? "Preview" : "Creation"} was not confirmed.`;
  }
  return `${action === "preview" ? "Preview" : "Creation"} was not confirmed by the local engine.`;
}

export function CreateJobPage() {
  const [target, setTarget] = useState("");
  const [platform, setPlatform] = useState("auto");
  const [outputs, setOutputs] = useState<Output[]>(["episodes", "skill"]);
  const [ragChunks, setRagChunks] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [created, setCreated] = useState<CreatedJob | null>(null);
  const [pending, setPending] = useState<"preview" | "create" | null>(null);
  const [error, setError] = useState<string | null>(null);

  function invalidatePreview() {
    setPreview(null);
    setCreated(null);
    setError(null);
  }

  function updateOutput(output: Output, checked: boolean) {
    invalidatePreview();
    setOutputs((current) => checked
      ? [...current, output]
      : current.filter((value) => value !== output));
  }

  async function inspectSource() {
    if (!target.trim() || outputs.length === 0) return;
    setPending("preview");
    setPreview(null);
    setCreated(null);
    setError(null);
    try {
      const result = await postJson<unknown>("/api/v1/jobs/preview", {
        target: target.trim(), platform, outputs, rag_chunks: ragChunks,
      });
      if (!isPreview(result)) throw new Error("invalid preview response");
      setPreview(result);
    } catch (reason) {
      setError(failureMessage("preview", reason));
    } finally {
      setPending(null);
    }
  }

  async function createMission() {
    if (!preview || created || pending || !target.trim()) return;
    setPending("create");
    setError(null);
    try {
      const result = await postJson<unknown>("/api/v1/jobs", {
        target: target.trim(),
        platform,
        outputs,
        rag_chunks: ragChunks,
        preview_fingerprint: preview.fingerprint,
      });
      if (!isCreatedJob(result)) throw new Error("invalid create response");
      setCreated(result);
    } catch (reason) {
      setError(failureMessage("creation", reason));
    } finally {
      setPending(null);
    }
  }

  return (
    <section id="create" aria-label="Create job">
      <Card>
        <Text as="h2" size={600}>Create mission</Text>
        <Text>Inspect the source first. Creation stays locked to that exact server preview.</Text>
        <Field label="Creator URL" required>
          <Input
            aria-label="Creator URL"
            value={target}
            onChange={(_, data) => { invalidatePreview(); setTarget(data.value); }}
            placeholder="https://space.bilibili.com/..."
          />
        </Field>
        <Field label="Platform">
          <Select value={platform} onChange={(_, data) => { invalidatePreview(); setPlatform(data.value); }}>
            <option value="auto">Auto detect</option>
            <option value="bilibili">Bilibili</option>
            <option value="douyin">Douyin</option>
          </Select>
        </Field>
        <Checkbox label="Episode markdown" checked={outputs.includes("episodes")} onChange={(_, data) => updateOutput("episodes", !!data.checked)} />
        <Checkbox label="Distilled skill" checked={outputs.includes("skill")} onChange={(_, data) => updateOutput("skill", !!data.checked)} />
        <Checkbox label="Generate RAG chunks" checked={ragChunks} onChange={(_, data) => { invalidatePreview(); setRagChunks(!!data.checked); }} />
        <div>
          <Button appearance="secondary" onClick={inspectSource} disabled={!target.trim() || outputs.length === 0 || pending !== null}>
            {pending === "preview" ? "Inspecting source..." : "Inspect source"}
          </Button>
          <Button appearance="primary" onClick={createMission} disabled={!preview || !!created || pending !== null}>
            {pending === "create" ? "Creating mission..." : "Create mission"}
          </Button>
        </div>
        {preview && <Text role="status" className="metric">
          {preview.creator_name} · {preview.processable_items} processable / {preview.total_items} total
        </Text>}
        {created && <Text role="status">Mission {created.job_id} accepted by the local engine.</Text>}
        {error && <Text role="alert">{error}</Text>}
      </Card>
    </section>
  );
}
