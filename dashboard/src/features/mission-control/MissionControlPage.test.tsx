import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MissionControlPage } from "./MissionControlPage";

afterEach(cleanup);

const snapshot = {
  job_id: "job-1",
  revision: 1,
  overall_progress: 0.5,
  coverage: 0.25,
  counts: { total: 4, active: 1, completed: 1, failed: 0, retry: 0, unsupported: 0, queued: 2, enumerated: 4 },
  eta_total_seconds: 60,
  eta_active_slowest_seconds: 30,
  provisional_eta: false,
  active_items: [{
    source_id: "douyin_1",
    title: "Work A",
    row_id: 1,
    stage: "downloading",
    stage_progress: 0.5,
    overall_progress: 0.1,
    completed_bytes: 1024,
    total_bytes: 2048,
    bytes_per_second: 12288,
    download_eta_seconds: 1,
    audio_completed_seconds: 0,
    audio_total_seconds: null,
    asr_rtf: null,
  }],
};

describe("MissionControlPage", () => {
  it("offers a clear creation action when no work is active", () => {
    render(<MissionControlPage snapshot={{
      ...snapshot,
      active_items: [],
      counts: { ...snapshot.counts, active: 0 },
    }} />);

    expect(screen.getByRole("link", { name: "新建任务" })).toHaveAttribute("href", "#create");
  });

  it("renders server transfer values with readable overall and active ETA labels", () => {
    render(<MissionControlPage snapshot={snapshot} />);

    expect(screen.getByText("1.0 KB / 2.0 KB")).toBeVisible();
    expect(screen.getAllByText("12.0 KB/秒")).toHaveLength(2);
    expect(screen.getByText("预计总剩余时间")).toBeVisible();
    expect(screen.getByText("01:00")).toBeVisible();
    expect(screen.getByText(/当前任务预计 00:30/)).toBeVisible();
  });

  it("renders the server supplied per-item download ETA", () => {
    const view = render(<MissionControlPage snapshot={snapshot} />);

    expect(within(view.container).getByText("下载预计 00:01")).toBeVisible();
  });

  it("renders the server supplied ASR duration and RTF", () => {
    const view = render(<MissionControlPage snapshot={{
      ...snapshot,
      active_items: [{
        ...snapshot.active_items[0],
        stage: "transcribing",
        audio_completed_seconds: 15,
        audio_total_seconds: 30,
        asr_rtf: 0.75,
      }],
    }} />);

    expect(within(view.container).getByText(/语音转写 00:15/)).toBeVisible();
  });

  it("preserves a source row across a server stage transition", () => {
    const view = render(<MissionControlPage snapshot={snapshot} />);
    const initialRow = within(view.container).getByRole("group", { name: "Work A · 下载中" });

    view.rerender(<MissionControlPage snapshot={{
      ...snapshot,
      revision: 2,
      active_items: [{ ...snapshot.active_items[0], stage: "transcribing" }],
    }} />);

    expect(within(view.container).getByRole("group", { name: "Work A · 转写中" })).toBe(initialRow);
  });

  it("uses an indeterminate transfer indicator when the server total is unknown", () => {
    const view = render(<MissionControlPage snapshot={{
      ...snapshot,
      active_items: [{ ...snapshot.active_items[0], total_bytes: null, stage_progress: null }],
    }} />);

    expect(within(view.container).getByRole("progressbar", { name: "Work A 下载进度" })).toBeVisible();
  });

  it("explains paused telemetry instead of displaying unknown download values", () => {
    render(<MissionControlPage
      snapshot={{ ...snapshot, active_items: [], counts: { ...snapshot.counts, active: 0 } }}
      job={{ job_id: "job-1", status: "paused", revision: 1 }}
    />);

    expect(screen.getAllByText("已暂停")).not.toHaveLength(0);
    expect(screen.getByText("恢复后估算")).toBeVisible();
    expect(screen.queryByText("未知")).not.toBeInTheDocument();
  });
});
