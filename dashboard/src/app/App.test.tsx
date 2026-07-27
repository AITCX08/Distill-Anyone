import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const stream = vi.hoisted(() => ({
  callback: undefined as undefined | ((event: { eventType: string; data: Record<string, unknown> }) => void),
  close: vi.fn(),
}));

vi.mock("../api/events", () => ({
  subscribeToEvents: vi.fn((callback) => {
    stream.callback = callback;
    return { close: stream.close };
  }),
}));

import { App } from "./App";
import { subscribeToEvents } from "../api/events";

describe("App", () => {
  it("renders the latest server progress snapshot after an SSE reconnect", () => {
    render(<App />);

    expect(subscribeToEvents).toHaveBeenCalledOnce();

    act(() => stream.callback?.({
      eventType: "snapshot",
      data: {
        schema_version: 1,
        jobs: [],
        progress_snapshots: [{
          job_id: "job-1",
          revision: 2,
          overall_progress: 0.5,
          coverage: 0.25,
          counts: { total: 4, active: 1, completed: 1, failed: 0, retry: 0, unsupported: 0, queued: 2, enumerated: 4 },
          eta_total_seconds: 60,
          eta_active_slowest_seconds: 30,
          provisional_eta: false,
          active_items: [{
            source_id: "bili_1", title: "作品 A", row_id: 1, stage: "downloading", stage_progress: 0.5,
            overall_progress: 0.1, completed_bytes: 1024, total_bytes: 2048, bytes_per_second: 12288,
            download_eta_seconds: 1, audio_completed_seconds: 0, audio_total_seconds: null, asr_rtf: null,
          }],
        }],
      },
    }));

    expect(screen.getByText("1.0 KB / 2.0 KB")).toBeVisible();
  });

  it("ignores a malformed reconnect snapshot instead of rendering invented counters", () => {
    render(<App />);

    act(() => stream.callback?.({
      eventType: "snapshot",
      data: {
        progress_snapshots: [{
          job_id: "job-1",
          revision: 2,
          overall_progress: 0.5,
          coverage: 0.25,
          counts: {},
          active_items: [],
        }],
      },
    }));

    expect(screen.getByText("Waiting for server snapshot...")).toBeVisible();
  });
});
