import { afterEach, describe, expect, it, vi } from "vitest";
import { subscribeToEvents } from "./events";

class FakeEventSource {
  static latest: FakeEventSource | undefined;
  listeners = new Map<string, (event: MessageEvent<string>) => void>();
  close = vi.fn();
  constructor(public readonly url: string) { FakeEventSource.latest = this; }
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) { this.listeners.set(type, listener); }
}

afterEach(() => vi.unstubAllGlobals());

describe("subscribeToEvents", () => {
  it("consumes server snapshots and never invents client progress", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const received: unknown[] = [];
    const subscription = subscribeToEvents((event) => received.push(event));
    FakeEventSource.latest!.listeners.get("snapshot")!(new MessageEvent("snapshot", { data: '{"schema_version":1,"jobs":[]}' }));

    expect(FakeEventSource.latest!.url).toBe("/api/v1/events");
    expect(received).toEqual([{ eventType: "snapshot", data: { schema_version: 1, jobs: [] } }]);
    subscription.close();
    expect(FakeEventSource.latest!.close).toHaveBeenCalledOnce();
  });

  it("receives the server snapshot without synthesizing missing task metadata", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const received: unknown[] = [];
    subscribeToEvents((event) => received.push(event));

    FakeEventSource.latest!.listeners.get("snapshot")!(new MessageEvent("snapshot", {
      data: JSON.stringify({
        schema_version: 1,
        jobs: [],
        tasks: [{
          task_id: "task-1", job_id: "job-1", source_id: "bilibili_BV1_p01",
          display_title: "第 1 集", part_number: 1, delivery_state: "pending",
          status: "pending", stage: "queued", revision: 0, attempt: 0,
          checkpoint_revision: 0, updated_at: "2026-08-10T00:00:00Z",
        }],
      }),
    }));

    expect(received).toHaveLength(1);
  });
});
