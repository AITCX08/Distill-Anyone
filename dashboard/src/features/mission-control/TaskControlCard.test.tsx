import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MissionControlPage } from "./MissionControlPage";
import { TaskControlCard } from "./TaskControlCard";

const task = {
  task_id: "task-1",
  job_id: "job-1",
  source_id: "p01",
  display_title: "第 1 集",
  part_number: 1,
  delivery_state: "pending" as const,
  status: "running",
  stage: "downloading",
  revision: 2,
  attempt: 0,
  checkpoint_revision: 1,
  updated_at: "2026-08-09T00:00:00Z",
  transfer: { completed_bytes: 25, total_bytes: 100, bytes_per_second: 25 },
};

const snapshot = {
  job_id: "job-1", revision: 1, overall_progress: 0, coverage: 0,
  counts: { total: 2, active: 2, completed: 0, failed: 0, retry: 0, unsupported: 0, queued: 0, enumerated: 2 },
  eta_total_seconds: null, eta_active_slowest_seconds: null, provisional_eta: true, active_items: [],
};

afterEach(cleanup);

describe("TaskControlCard", () => {
  it("shows the episode title, BVID, and completion time without technical details", () => {
    render(<TaskControlCard task={{
      ...task,
      source_id: "bilibili_BV18bLkztE7R_p01",
      display_title: "开场与概念",
      part_number: 1,
      status: "completed",
      stage: "completed",
      updated_at: "2026-08-10T00:41:59Z",
      completed_at: "2026-08-10T16:44:12Z",
    }} />);

    expect(screen.getByRole("heading", { name: "第 1 集 · 开场与概念" })).toBeVisible();
    expect(screen.getByText("BV18bLkztE7R · 完成于 2026-08-10 16:44")).toBeVisible();
    expect(screen.queryByText("技术信息")).not.toBeInTheDocument();
    expect(screen.queryByText(/检查点/)).not.toBeInTheDocument();
  });

  it("shows independent controls for two active tasks", () => {
    render(<MissionControlPage snapshot={snapshot} tasks={[task, { ...task, task_id: "task-2", source_id: "p02" }]} />);
    expect(screen.getAllByRole("button", { name: "暂停任务" })).toHaveLength(2);
  });

  it("shows bytes and speed only for a downloading task", () => {
    render(<TaskControlCard task={{ ...task, stage: "transcribing", transfer: undefined }} />);
    expect(screen.getByText("正在转写，暂不显示下载速度")).toBeVisible();
    expect(screen.queryByText(/KB\/秒/)).not.toBeInTheDocument();
  });
});
