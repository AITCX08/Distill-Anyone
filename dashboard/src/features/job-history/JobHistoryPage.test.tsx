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
        { source_id: "bilibili_BV1demo_p07", display_title: "知识提取", part_number: 7, processing_status: "failed", retryable: true, stage_progress: 0, overall_progress: 0, last_error: "未生成可用知识", completed_at: null, updated_at: "2026-07-27T09:00:00Z" },
        { source_id: "bilibili_BV1demo_p08", display_title: "收尾", part_number: 8, processing_status: "completed", retryable: false, stage_progress: 1, overall_progress: 1, last_error: null, completed_at: "2026-07-27T09:00:00Z", updated_at: "2026-07-27T09:00:00Z" },
      ])
      .mockResolvedValueOnce([
        { source_id: "retry-this", processing_status: "pending", retryable: false, stage_progress: 0, overall_progress: 0, last_error: null, updated_at: "2026-07-27T09:00:01Z" },
      ]);

    postJson.mockResolvedValue({ job_id: "job-1", status: "running", revision: 3 });
    render(<JobHistoryPage />);

    await screen.findByText("Failed creator");
    fireEvent.click(screen.getByRole("button", { name: "查看 Failed creator 的项目操作" }));

    expect(await screen.findByText(/第 7 集 · 知识提取/)).toBeVisible();
    expect(screen.getByText(/第 8 集 · 收尾/)).toBeVisible();
    expect(screen.getByText("BV1demo · 完成于 2026-07-27 09:00")).toBeVisible();
    expect(screen.queryByText("技术信息")).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "重试 bilibili_BV1demo_p07" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "重试 bilibili_BV1demo_p08" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "重试 bilibili_BV1demo_p07" }));
    await waitFor(() => expect(postJson).toHaveBeenCalledWith("/api/v1/jobs/job-1/items/bilibili_BV1demo_p07/retry", { expected_revision: 2 }));
  });

  it("reveals the private delivery location only after an explicit request", async () => {
    getJson
      .mockResolvedValueOnce([{
        job_id: "job-2", status: "completed", revision: 4, platform: "bilibili", creator_name: "课程作者",
        total_items: 1, completed_items: 1, failed_items: 0, unsupported_items: 0, updated_at: "2026-08-10T09:00:00Z",
      }])
      .mockResolvedValueOnce([
        { source_id: "bili-1", display_title: "开场", part_number: 1, processing_status: "completed", retryable: false, stage_progress: 1, overall_progress: 1, last_error: null, completed_at: "2026-08-10T09:00:00Z", updated_at: "2026-08-10T09:00:00Z" },
      ])
      .mockResolvedValueOnce({
        job_id: "job-2", display_title: "八集课程", creator_name: "课程作者", destination: "D:/deliveries/course", artifact_count: 1, completed_at: "2026-08-10T09:00:00Z",
      });
    postJson.mockResolvedValue(undefined);

    render(<JobHistoryPage />);

    await screen.findByText("课程作者");
    fireEvent.click(screen.getByRole("button", { name: "查看 课程作者 的项目操作" }));
    await screen.findByText(/第 1 集 · 开场/);
    expect(screen.queryByText("保存位置：D:/deliveries/course")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看交付详情" }));
    expect(await screen.findByText("保存位置：D:/deliveries/course")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "打开文件夹" }));
    await waitFor(() => expect(postJson).toHaveBeenCalledWith("/api/v1/jobs/job-2/reveal-output", {}));
  });
});
