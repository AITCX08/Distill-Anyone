import { Button, Text } from "@fluentui/react-components";
import { stageLabel } from "../../i18n/zh";
import type { ActiveItem } from "./ActiveItemRow";

export function TaskDetailDrawer({ item, onClose, onViewArtifacts }: { item: ActiveItem; onClose: () => void; onViewArtifacts?: () => void }) {
  return (
    <aside className="task-detail" aria-label="任务详情" aria-live="polite">
      <div className="task-detail__heading">
        <div><Text className="metric">作品 #{item.row_id}</Text><Text as="h2" size={400}>{item.title || item.source_id}</Text></div>
        <Button appearance="subtle" onClick={onClose} aria-label="关闭详情">关闭</Button>
      </div>
      <dl>
        <div><dt>当前阶段</dt><dd>{stageLabel(item.stage)}</dd></div>
        <div><dt>来源标识</dt><dd className="metric">{item.source_id}</dd></div>
        <div><dt>服务端阶段进度</dt><dd className="metric">{item.stage_progress === null ? "未知" : `${Math.round(item.stage_progress * 100)}%`}</dd></div>
        <div><dt>服务端总体进度</dt><dd className="metric">{Math.round(item.overall_progress * 100)}%</dd></div>
      </dl>
      {onViewArtifacts && <Button appearance="primary" onClick={onViewArtifacts}>查看本任务产物</Button>}
    </aside>
  );
}
