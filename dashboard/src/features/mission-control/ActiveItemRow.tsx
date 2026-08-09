import { Button, Card, ProgressBar, Text } from "@fluentui/react-components";
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
  return value >= 1024 * 1024 ? `${(value / (1024 * 1024)).toFixed(1)} MB` : `${(value / 1024).toFixed(1)} KB`;
}

function formatDuration(value: number): string {
  const seconds = Math.round(value);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export const ActiveItemRow = memo(function ActiveItemRow({ item, onInspect }: { item: ActiveItem; onInspect?: (item: ActiveItem) => void }) {
  const downloading = item.stage === "downloading";
  const stageName = stageLabel(item.stage);

  return (
    <Card className="execution-row" aria-label={`${item.title || item.source_id} · ${stageName}`}>
      <div className="execution-row__identity">
        <Text as="h3">#{item.row_id} {item.title || item.source_id}</Text>
        <div><Text className="execution-row__stage">{stageName}</Text>{onInspect && <Button appearance="subtle" onClick={() => onInspect(item)}>查看详情</Button>}</div>
      </div>
      {downloading ? <>
        {item.total_bytes === null
          ? <Text className="execution-row__transfer"><span>文件大小未知</span><span>已传输 {formatBytes(item.completed_bytes)}</span><span>{formatBytes(item.bytes_per_second)}/秒</span></Text>
          : <Text>{formatBytes(item.completed_bytes)} / {formatBytes(item.total_bytes)}</Text>}
        <ProgressBar value={item.total_bytes ? item.completed_bytes / item.total_bytes : undefined} aria-label={`${item.title || item.source_id} 下载进度`} />
        <Text className="metric">{formatBytes(item.bytes_per_second)}/秒</Text>
        <Text>下载预计 {item.download_eta_seconds === null ? "未知" : formatDuration(item.download_eta_seconds)}</Text>
      </> : <>
        <Text>{`正在${stageName}，暂不显示下载速度`}</Text>
        <ProgressBar aria-label={`${item.title || item.source_id} ${stageName}进度`} />
      </>}
      {item.stage === "transcribing" && <Text>语音转写 {formatDuration(item.audio_completed_seconds)} / {item.audio_total_seconds === null ? "未知" : formatDuration(item.audio_total_seconds)} · 实时系数 {item.asr_rtf === null ? "未知" : `${item.asr_rtf.toFixed(2)}x`}</Text>}
      {item.stage_progress !== null && <ProgressBar value={item.stage_progress} aria-label={`${item.title || item.source_id} 阶段进度`} />}
    </Card>
  );
});
