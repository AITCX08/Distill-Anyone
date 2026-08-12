import type { ReactNode } from "react";

export type QueueTableProps<T> = {
  ariaLabel: string;
  items: readonly T[];
  getKey: (item: T) => string;
  renderTitle: (item: T) => ReactNode;
  renderMeta: (item: T) => ReactNode;
  renderStatus: (item: T) => ReactNode;
  renderProgress: (item: T) => ReactNode;
  renderStage: (item: T) => ReactNode;
  renderUpdated: (item: T) => ReactNode;
  renderActions: (item: T) => ReactNode;
};

export function QueueTable<T>({
  ariaLabel, items, getKey, renderTitle, renderMeta, renderStatus, renderProgress, renderStage, renderUpdated, renderActions,
}: QueueTableProps<T>) {
  return <div className="queue-table__scroll"><table className="queue-table" aria-label={ariaLabel}>
    <thead><tr><th scope="col">作品标题</th><th scope="col">状态</th><th scope="col">进度</th><th scope="col">阶段</th><th scope="col">更新时间</th><th scope="col">操作</th></tr></thead>
    <tbody>{items.map((item) => <tr key={getKey(item)}>
      <td data-label="作品标题"><strong>{renderTitle(item)}</strong><span className="queue-table__meta">{renderMeta(item)}</span></td>
      <td data-label="状态">{renderStatus(item)}</td><td data-label="进度">{renderProgress(item)}</td><td data-label="阶段">{renderStage(item)}</td><td data-label="更新时间">{renderUpdated(item)}</td><td data-label="操作">{renderActions(item)}</td>
    </tr>)}</tbody>
  </table></div>;
}
