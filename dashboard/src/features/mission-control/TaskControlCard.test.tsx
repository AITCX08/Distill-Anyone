import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MissionControlPage } from "./MissionControlPage";
import { TaskControlCard } from "./TaskControlCard";

const task = {
  task_id: "task-1",
  job_id: "job-1",
  source_id: "p01",
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
