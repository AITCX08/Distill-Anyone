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
    return `本地引擎离线，${action === "preview" ? "预检" : "创建"}尚未确认。`;
  }
  return `本地引擎尚未确认${action === "preview" ? "预检" : "创建"}操作。`;
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
    <section id="create" aria-label="新建任务">
      <Card>
        <Text as="h2" size={600}>新建任务</Text>
        <Text>请先预检来源；创建操作将严格使用该次服务端预检结果。</Text>
        <Field label="创作者链接" required>
          <Input
            aria-label="创作者链接"
            value={target}
            onChange={(_, data) => { invalidatePreview(); setTarget(data.value); }}
            placeholder="https://space.bilibili.com/..."
          />
        </Field>
        <Field label="平台">
          <Select value={platform} onChange={(_, data) => { invalidatePreview(); setPlatform(data.value); }}>
            <option value="auto">自动识别</option>
            <option value="bilibili">哔哩哔哩</option>
            <option value="douyin">抖音</option>
          </Select>
        </Field>
        <Checkbox label="按作品生成 Markdown" checked={outputs.includes("episodes")} onChange={(_, data) => updateOutput("episodes", !!data.checked)} />
        <Checkbox label="生成蒸馏 Skill" checked={outputs.includes("skill")} onChange={(_, data) => updateOutput("skill", !!data.checked)} />
        <Checkbox label="生成 RAG 分块" checked={ragChunks} onChange={(_, data) => { invalidatePreview(); setRagChunks(!!data.checked); }} />
        <div>
          <Button appearance="secondary" onClick={inspectSource} disabled={!target.trim() || outputs.length === 0 || pending !== null}>
            {pending === "preview" ? "正在预检…" : "预检来源"}
          </Button>
          <Button appearance="primary" onClick={createMission} disabled={!preview || !!created || pending !== null}>
            {pending === "create" ? "正在创建…" : "创建任务"}
          </Button>
        </div>
        {preview && <Text role="status" className="metric">
          {preview.creator_name} · 可处理 {preview.processable_items} / 共 {preview.total_items} 条
        </Text>}
        {created && <Text role="status">任务 {created.job_id} 已由本地引擎接收。</Text>}
        {error && <Text role="alert">{error}</Text>}
      </Card>
    </section>
  );
}
