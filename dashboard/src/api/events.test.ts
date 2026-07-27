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
});
