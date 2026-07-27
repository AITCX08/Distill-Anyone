import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const getJson = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", () => ({ getJson }));

import { JobHistoryPage } from "./JobHistoryPage";

describe("JobHistoryPage", () => {
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
    fireEvent.change(screen.getByLabelText("Status filter"), { target: { value: "failed" } });

    expect(screen.getByText("Failed creator")).toBeVisible();
    expect(screen.queryByText("Running creator")).not.toBeInTheDocument();
    expect(screen.getByText("2 failed / 3 total")).toBeVisible();
  });
});
