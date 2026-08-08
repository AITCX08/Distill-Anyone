import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getJson = vi.hoisted(() => vi.fn());
const postJson = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", () => ({ getJson, postJson }));

import { JobHistoryPage } from "./JobHistoryPage";

describe("JobHistoryPage", () => {
  beforeEach(() => { getJson.mockReset(); postJson.mockReset(); });
  afterEach(cleanup);

  it("filters server job history by status without inventing rows", async () => {
    getJson.mockResolvedValueOnce([
      {
        job_id: "job-running", status: "running", revision: 3, platform: "douyin", creator_name: "Running creator",
        total_items: 4, completed_items: 1, failed_items: 0, unsupported_items: 0, updated_at: "2026-07-27T10:00:00Z",
      },
      {
        job_id: "job-failed", status: "failed", revision: 2, platform: "bilibili", creator_name: "Failed creator",
        total_items: 3, completed_items: 1, failed_items: 2, unsupported_items: 0, updated_at: "2026-07-27T09:00:00Z",
      },
    ]);

    render(<JobHistoryPage />);

    expect(await screen.findByText("Running creator")).toBeVisible();
    fireEvent.change(screen.getByLabelText("状态筛选"), { target: { value: "failed" } });

    expect(screen.getByText("Failed creator")).toBeVisible();
    expect(screen.queryByText("Running creator")).not.toBeInTheDocument();
    expect(screen.getByText("失败 2 / 共 3 条")).toBeVisible();
  });

  it("shows item retry only when the server marks that item retryable", async () => {
    getJson
      .mockResolvedValueOnce([{
        job_id: "job-1", status: "failed", revision: 2, platform: "bilibili", creator_name: "Failed creator",
        total_items: 2, completed_items: 0, failed_items: 2, unsupported_items: 0, updated_at: "2026-07-27T09:00:00Z",
      }])
      .mockResolvedValueOnce([
        { source_id: "retry-this", processing_status: "failed", retryable: true, stage_progress: 0, overall_progress: 0, last_error: null, updated_at: "2026-07-27T09:00:00Z" },
        { source_id: "do-not-retry", processing_status: "completed", retryable: false, stage_progress: 1, overall_progress: 1, last_error: null, updated_at: "2026-07-27T09:00:00Z" },
      ])
      .mockResolvedValueOnce([
        { source_id: "retry-this", processing_status: "pending", retryable: false, stage_progress: 0, overall_progress: 0, last_error: null, updated_at: "2026-07-27T09:00:01Z" },
      ]);

    postJson.mockResolvedValue({ job_id: "job-1", status: "running", revision: 3 });
    render(<JobHistoryPage />);

    await screen.findByText("Failed creator");
    fireEvent.click(screen.getByRole("button", { name: "查看 Failed creator 的项目操作" }));

    expect(await screen.findByRole("button", { name: "重试 retry-this" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "重试 do-not-retry" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "重试 retry-this" }));
    await waitFor(() => expect(postJson).toHaveBeenCalledWith("/api/v1/jobs/job-1/items/retry-this/retry", { expected_revision: 2 }));
  });
});
