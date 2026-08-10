import { useState } from "react";
import { Button, Card, Field, Input, Select, Text } from "@fluentui/react-components";

import { DashboardRequestError, postJson } from "../../api/client";
import { OutputDirectoryField, type OutputDirectorySelection } from "./OutputDirectoryField";
import { OutputSelectionCard } from "./OutputSelectionCard";
import { OutputTemplateDialog } from "./OutputTemplateDialog";
import type { OutputTemplateKey } from "./OutputTemplates";

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
  const [directory, setDirectory] = useState<OutputDirectorySelection>({ destinationMode: "default" });
  const [templateOutput, setTemplateOutput] = useState<OutputTemplateKey | null>(null);
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
    setOutputs((current) => checked ? [...current, output] : current.filter((value) => value !== output));
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
    if (!preview || created || pending || !target.trim() || (directory.destinationMode === "override" && !directory.destinationToken)) return;
    setPending("create");
    setError(null);
    try {
      const result = await postJson<unknown>("/api/v1/jobs", {
        target: target.trim(),
        platform,
        outputs,
        rag_chunks: ragChunks,
        preview_fingerprint: preview.fingerprint,
        destination_mode: directory.destinationMode,
        ...(directory.destinationMode === "override" ? { destination_token: directory.destinationToken } : {}),
      });
      if (!isCreatedJob(result)) throw new Error("invalid create response");
      setCreated(result);
    } catch (reason) {
      setError(failureMessage("creation", reason));
    } finally {
      setPending(null);
    }
  }

  const cannotCreate = !preview || !!created || pending !== null
    || (directory.destinationMode === "override" && !directory.destinationToken);

  return (
    <section id="create" aria-label="新建任务">
      <Card className="create-job-card">
        <Text as="h2" size={600}>新建任务</Text>
        <Text>先预检来源，再选择要交付的内容和保存位置。创建后可在任务作战台跟踪全流程。</Text>
        <Field label="创作者链接" required>
          <Input aria-label="创作者链接" value={target} onChange={(_, data) => { invalidatePreview(); setTarget(data.value); }} placeholder="https://space.bilibili.com/..." />
        </Field>
        <Field label="平台">
          <Select value={platform} onChange={(_, data) => { invalidatePreview(); setPlatform(data.value); }}>
            <option value="auto">自动识别</option>
            <option value="bilibili">哔哩哔哩</option>
            <option value="douyin">抖音</option>
          </Select>
        </Field>
        <section className="output-selection" aria-label="选择交付内容">
          <Text as="h3" size={400}>选择交付内容</Text>
          <div className="output-selection__grid">
            <OutputSelectionCard output="episodes" checked={outputs.includes("episodes")} onCheckedChange={(checked) => updateOutput("episodes", checked)} onShowTemplate={() => setTemplateOutput("episodes")} />
            <OutputSelectionCard output="skill" checked={outputs.includes("skill")} onCheckedChange={(checked) => updateOutput("skill", checked)} onShowTemplate={() => setTemplateOutput("skill")} />
            <OutputSelectionCard output="rag" checked={ragChunks} onCheckedChange={(checked) => { invalidatePreview(); setRagChunks(checked); }} onShowTemplate={() => setTemplateOutput("rag")} />
          </div>
        </section>
        <OutputDirectoryField onChange={setDirectory} />
        <div className="create-job-card__actions">
          <Button appearance="secondary" onClick={() => void inspectSource()} disabled={!target.trim() || outputs.length === 0 || pending !== null}>{pending === "preview" ? "正在预检…" : "预检来源"}</Button>
          <Button appearance="primary" onClick={() => void createMission()} disabled={cannotCreate}>{pending === "create" ? "正在创建…" : "创建任务"}</Button>
        </div>
        {preview && <Text role="status" className="metric">{preview.creator_name} · 可处理 {preview.processable_items} / 共 {preview.total_items} 条 · 登录状态：{preview.auth_status}</Text>}
        {created && <Text role="status">任务已创建，可前往<a href="#mission">任务作战台</a>查看执行进度，或在<a href="#artifacts">产物库</a>查看交付内容。</Text>}
        {error && <Text role="alert">{error}</Text>}
      </Card>
      {templateOutput && <OutputTemplateDialog output={templateOutput} open onOpenChange={(open) => { if (!open) setTemplateOutput(null); }} />}
    </section>
  );
}
