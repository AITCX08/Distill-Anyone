type PartStatus = "已完成" | "失败" | "执行中" | "等待处理";

function statusFor(rowId: number, completed: number, active: number, failed: number): PartStatus {
  if (rowId <= completed) return "已完成";
  if (rowId <= completed + failed) return "失败";
  if (rowId <= completed + failed + active) return "执行中";
  return "等待处理";
}

export function SeriesRail({
  total,
  completed,
  active,
  failed,
  selectedRowId,
  onSelect,
}: {
  total: number;
  completed: number;
  active: number;
  failed: number;
  selectedRowId: number | null;
  onSelect: (rowId: number) => void;
}) {
  return <section className="series-rail" aria-label="系列进度">
    <div className="series-rail__heading"><span>作品轨道</span><span>{total} 集</span></div>
    <div className="series-rail__items">
      {Array.from({ length: total }, (_, index) => {
        const rowId = index + 1;
        const status = statusFor(rowId, completed, active, failed);
        return <button
          key={rowId}
          type="button"
          className="series-rail__item"
          data-status={status}
          aria-label={`第 ${rowId} 集，${status}`}
          aria-pressed={selectedRowId === rowId}
          onClick={() => onSelect(rowId)}
        >{rowId}</button>;
      })}
    </div>
  </section>;
}
