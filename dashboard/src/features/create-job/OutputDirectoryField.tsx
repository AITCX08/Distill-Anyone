import { useEffect, useState } from "react";
import { Button, Checkbox, Field, Input, Text } from "@fluentui/react-components";

import { getJson, postJson } from "../../api/client";

export type OutputDirectorySelection = {
  destinationMode: "default" | "override";
  destinationToken?: string;
};

type DirectoryResponse = { directory: string };
type ValidationResponse = DirectoryResponse & { token: string; expires_at: string };
type ChooseResponse = { selected: boolean; directory?: string; token?: string; expires_at?: string };

type Props = { onChange: (selection: OutputDirectorySelection) => void };

function isValidationResponse(value: unknown): value is ValidationResponse {
  return typeof value === "object" && value !== null
    && "directory" in value && typeof value.directory === "string"
    && "token" in value && typeof value.token === "string";
}

function isChooseResponse(value: unknown): value is ChooseResponse {
  return typeof value === "object" && value !== null
    && "selected" in value && typeof value.selected === "boolean";
}

export function OutputDirectoryField({ onChange }: Props) {
  const [useOverride, setUseOverride] = useState(false);
  const [defaultDirectory, setDefaultDirectory] = useState<string | null>(null);
  const [directory, setDirectory] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState<"validate" | "choose" | null>(null);

  useEffect(() => {
    let active = true;
    void getJson<DirectoryResponse>("/api/v1/settings/output-directory")
      .then((result) => active && setDefaultDirectory(result.directory))
      .catch(() => active && setDefaultDirectory(null));
    return () => { active = false; };
  }, []);

  function switchMode(checked: boolean) {
    setUseOverride(checked);
    setToken(null);
    setStatus(null);
    onChange(checked ? { destinationMode: "override" } : { destinationMode: "default" });
  }

  async function validate() {
    if (!directory.trim()) return;
    setPending("validate");
    setStatus(null);
    setToken(null);
    try {
      const result = await postJson<unknown>("/api/v1/directories/validate", { directory: directory.trim() });
      if (!isValidationResponse(result)) throw new Error("invalid directory validation response");
      setDirectory(result.directory);
      setToken(result.token);
      setStatus("保存位置可用");
      onChange({ destinationMode: "override", destinationToken: result.token });
    } catch {
      setStatus("保存位置不可用，请修改后重新校验。");
      onChange({ destinationMode: "override" });
    } finally {
      setPending(null);
    }
  }

  async function choose() {
    setPending("choose");
    setStatus(null);
    try {
      const result = await postJson<unknown>("/api/v1/directories/choose", {});
      if (!isChooseResponse(result) || !result.selected) {
        setStatus("未选择新的保存位置");
        return;
      }
      if (!result.directory || !result.token) throw new Error("invalid directory choice response");
      setDirectory(result.directory);
      setToken(result.token);
      setStatus("保存位置可用");
      onChange({ destinationMode: "override", destinationToken: result.token });
    } catch {
      setStatus("无法打开本地文件夹选择器，请改为手动输入位置。");
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="output-directory-field" aria-label="保存位置">
      <Text as="h3" size={400}>保存位置</Text>
      {defaultDirectory ? <Text>默认保存位置：{defaultDirectory}</Text> : <Text>默认保存位置由本地引擎管理。</Text>}
      <Checkbox
        label="本次使用其他保存位置"
        checked={useOverride}
        onChange={(_, data) => switchMode(!!data.checked)}
      />
      {useOverride && <div className="output-directory-field__override">
        <Field label="本次保存位置">
          <Input
            aria-label="本次保存位置"
            value={directory}
            onChange={(_, data) => { setDirectory(data.value); setToken(null); setStatus(null); onChange({ destinationMode: "override" }); }}
            placeholder="选择或输入本次保存位置"
          />
        </Field>
        <Button appearance="secondary" onClick={() => void choose()} disabled={pending !== null}>
          {pending === "choose" ? "正在打开选择器…" : "选择文件夹"}
        </Button>
        <Button appearance="secondary" onClick={() => void validate()} disabled={!directory.trim() || pending !== null}>
          {pending === "validate" ? "正在校验…" : "校验位置"}
        </Button>
        {status && <Text role={token ? "status" : "alert"}>{status}</Text>}
      </div>}
    </section>
  );
}
