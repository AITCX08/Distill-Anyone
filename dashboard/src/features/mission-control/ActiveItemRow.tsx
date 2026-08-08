import { Card, ProgressBar, Text } from "@fluentui/react-components";
import { memo } from "react";
import { stageLabel } from "../../i18n/zh";

export type ActiveItem = {
  source_id: string;
  title: string;
  row_id: number;
  stage: string;
  stage_progress: number | null;
  overall_progress: number;
  completed_bytes: number;
  total_bytes: number | null;
  bytes_per_second: number;
  download_eta_seconds: number | null;
  audio_completed_seconds: number;
  audio_total_seconds: number | null;
  asr_rtf: number | null;
};

function formatBytes(value: number): string {
  return value >= 1024 * 1024
    ? `${(value / (1024 * 1024)).toFixed(1)} MB`
    : `${(value / 1024).toFixed(1)} KB`;
}

function formatDuration(value: number): string {
  const seconds = Math.round(value);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export const ActiveItemRow = memo(function ActiveItemRow({ item }: { item: ActiveItem }) {
  return (
    <Card aria-label={`${item.title || item.source_id} · ${stageLabel(item.stage)}`}>
      <Text as="h3">#{item.row_id} {item.title || item.source_id}</Text>
      <Text>{stageLabel(item.stage)}</Text>
      {item.total_bytes === null
        ? <Text>文件大小未知 · 已传输 {formatBytes(item.completed_bytes)} · {formatBytes(item.bytes_per_second)}/秒</Text>
        : <Text>{formatBytes(item.completed_bytes)} / {formatBytes(item.total_bytes)}</Text>}
      {item.total_bytes === null && <ProgressBar aria-label={`${item.title || item.source_id} 传输进度`} />}
      <Text className="metric">{formatBytes(item.bytes_per_second)}/秒</Text>
      <Text>下载预计 {item.download_eta_seconds === null ? "未知" : formatDuration(item.download_eta_seconds)}</Text>
      {item.stage === "transcribing" && (
        <Text>
          语音转写 {formatDuration(item.audio_completed_seconds)} / {item.audio_total_seconds === null ? "未知" : formatDuration(item.audio_total_seconds)} · 实时系数 {item.asr_rtf === null ? "未知" : `${item.asr_rtf.toFixed(2)}x`}
        </Text>
      )}
      {item.stage_progress === null
        ? <Text>正在估算本阶段进度</Text>
        : <ProgressBar value={item.stage_progress} aria-label={`${item.title || item.source_id} 阶段进度`} />}
    </Card>
  );
});
