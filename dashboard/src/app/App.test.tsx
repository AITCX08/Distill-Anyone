import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const stream = vi.hoisted(() => ({
  callback: undefined as undefined | ((event: { eventType: string; data: Record<string, unknown> }) => void),
  close: vi.fn(),
}));
const api = vi.hoisted(() => ({
  getJson: vi.fn(async () => []),
  postJson: vi.fn(),
}));

vi.mock("../api/events", () => ({
  subscribeToEvents: vi.fn((callback) => {
    stream.callback = callback;
    return { close: stream.close };
  }),
}));
vi.mock("../api/client", async (importOriginal) => ({
  ...await importOriginal<typeof import("../api/client")>(),
  getJson: api.getJson,
  postJson: api.postJson,
}));

import { App } from "./App";
import { subscribeToEvents } from "../api/events";

afterEach(() => {
  cleanup();
  stream.callback = undefined;
  stream.close.mockClear();
  vi.mocked(subscribeToEvents).mockClear();
  api.getJson.mockClear();
  api.postJson.mockClear();
  window.location.hash = "#mission";
});

describe("App", () => {
  it("renders only the workspace selected by the URL hash", () => {
    window.location.hash = "#create";

    render(<App />);

    expect(screen.getByRole("region", { name: "新建任务" })).toBeVisible();
    expect(screen.queryByRole("region", { name: "任务执行台" })).not.toBeInTheDocument();
  });

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

    expect(screen.getByText("正在等待服务端任务快照…")).toBeVisible();
  });

  it("shows controls only when the reconnect snapshot includes the matching server job state", () => {
    render(<App />);

    act(() => stream.callback?.({
      eventType: "snapshot",
      data: {
        jobs: [{ job_id: "job-1", status: "running", revision: 2 }],
        progress_snapshots: [{
          job_id: "job-1",
          revision: 2,
          overall_progress: 0.5,
          coverage: 0.25,
          counts: { total: 4, active: 1, completed: 1, failed: 0, retry: 0, unsupported: 0, queued: 2, enumerated: 4 },
          eta_total_seconds: 60,
          eta_active_slowest_seconds: 30,
          provisional_eta: false,
          active_items: [],
        }],
      },
    }));

    expect(screen.getByRole("button", { name: "暂停任务" })).toBeVisible();
  });

  it("renders a server trace line only for the active mission job", () => {
    render(<App />);

    act(() => stream.callback?.({
      eventType: "snapshot",
      data: {
        jobs: [],
        progress_snapshots: [{
          job_id: "job-1", revision: 2, overall_progress: 0.5, coverage: 0.25,
          counts: { total: 4, active: 1, completed: 1, failed: 0, retry: 0, unsupported: 0, queued: 2, enumerated: 4 },
          eta_total_seconds: 60, eta_active_slowest_seconds: 30, provisional_eta: false, active_items: [],
        }],
      },
    }));
    act(() => stream.callback?.({
      eventType: "trace.appended",
      data: { payload: { job_id: "job-1", line: "server trace: download started" } },
    }));

    expect(screen.getByText("server trace: download started")).toBeVisible();
  });
});
