import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const postJson = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", () => ({ postJson }));

import { CreateJobPage } from "./CreateJobPage";

describe("CreateJobPage", () => {
  it("requires a current preview before submitting that preview fingerprint", async () => {
    postJson
      .mockResolvedValueOnce({
        fingerprint: "preview-123",
        platform: "bilibili",
        creator_id: "creator-1",
        creator_name: "Creator",
        total_items: 3,
        processable_items: 2,
        skipped_items: 0,
        unsupported_items: 1,
        auth_status: "configured",
      })
      .mockResolvedValueOnce({ job_id: "job-1", status: "queued", revision: 0 });

    render(<CreateJobPage />);

    const target = screen.getByLabelText("创作者链接");
    const create = screen.getByRole("button", { name: "创建任务" });
    fireEvent.change(target, { target: { value: "https://space.bilibili.com/1" } });

    expect(create).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "预检来源" }));
    await screen.findByText("Creator · 可处理 2 / 共 3 条");
    expect(create).toBeEnabled();

    fireEvent.click(create);
    await waitFor(() => expect(postJson).toHaveBeenLastCalledWith("/api/v1/jobs", {
      target: "https://space.bilibili.com/1",
      platform: "auto",
      outputs: ["episodes", "skill"],
      rag_chunks: false,
      preview_fingerprint: "preview-123",
    }));
    expect(screen.getByText("任务 job-1 已由本地引擎接收。")).toBeVisible();
  });
});
