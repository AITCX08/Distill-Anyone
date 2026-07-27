import { Card, ProgressBar, Text } from "@fluentui/react-components";
import { memo } from "react";

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
    <Card aria-label={`${item.title || item.source_id} · ${item.stage}`}>
      <Text as="h3">#{item.row_id} {item.title || item.source_id}</Text>
      <Text>{item.stage}</Text>
      {item.total_bytes === null
        ? <Text>Unknown total · {formatBytes(item.completed_bytes)} · {formatBytes(item.bytes_per_second)}/s</Text>
        : <Text>{formatBytes(item.completed_bytes)} / {formatBytes(item.total_bytes)}</Text>}
      {item.total_bytes === null && <ProgressBar aria-label={`${item.title || item.source_id} transfer progress`} />}
      <Text className="metric">{formatBytes(item.bytes_per_second)}/s</Text>
      <Text>Transfer ETA {item.download_eta_seconds === null ? "unknown" : formatDuration(item.download_eta_seconds)}</Text>
      {item.stage === "transcribing" && (
        <Text>
          ASR {formatDuration(item.audio_completed_seconds)} / {item.audio_total_seconds === null ? "unknown" : formatDuration(item.audio_total_seconds)} · RTF {item.asr_rtf === null ? "unknown" : `${item.asr_rtf.toFixed(2)}x`}
        </Text>
      )}
      {item.stage_progress === null
        ? <Text>Stage progress estimating</Text>
        : <ProgressBar value={item.stage_progress} aria-label={`${item.title || item.source_id} stage progress`} />}
    </Card>
  );
});
