export type StatusTone = "success" | "active" | "waiting" | "warning" | "danger";

export function StatusPill({ label, tone }: { label: string; tone: StatusTone }) {
  return <span className="status-pill" data-tone={tone}>{label}</span>;
}
