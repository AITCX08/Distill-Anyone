import { ProgressBar, Text } from "@fluentui/react-components";

type Counts = { completed: number; active: number; queued: number; total: number };

function asPercent(progress: number): number {
  return Math.round(Math.min(1, Math.max(0, progress)) * 100);
}

export function ProgressSummary({ progress, stage, counts }: { progress: number; stage: string; counts: Counts }) {
  const percent = asPercent(progress);
  return <section className="progress-summary" aria-label="任务概览">
    <div className="progress-summary__progress"><strong>{percent}%</strong><Text>总体进度</Text></div>
    <div className="progress-summary__body">
      <div className="progress-summary__stage"><Text>当前阶段</Text><strong>{stage}</strong></div>
      <ProgressBar value={percent / 100} aria-label="总体进度" />
      <dl className="progress-summary__counts">
        <div><dt>已完成</dt><dd>{counts.completed}</dd></div>
        <div><dt>进行中</dt><dd>{counts.active}</dd></div>
        <div><dt>等待中</dt><dd>{counts.queued}</dd></div>
        <div><dt>总任务</dt><dd>{counts.total}</dd></div>
      </dl>
    </div>
  </section>;
}
