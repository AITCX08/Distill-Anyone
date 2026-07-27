import type { DashboardEvent } from "./schema";

export interface EventSubscription { close(): void; }
const eventTypes = ["snapshot", "job.updated", "item.updated", "trace.appended"] as const;

export function subscribeToEvents(onEvent: (event: DashboardEvent) => void): EventSubscription {
  const source = new EventSource("/api/v1/events");
  for (const eventType of eventTypes) {
    source.addEventListener(eventType, (message) => {
      try { onEvent({ eventType, data: JSON.parse((message as MessageEvent<string>).data) }); }
      catch { /* malformed server events are ignored until the reconnect snapshot */ }
    });
  }
  return { close: () => source.close() };
}
