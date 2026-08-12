import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const getJson = vi.hoisted(() => vi.fn());
const postJson = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", () => ({ getJson, postJson }));

import { CreateJobPage } from "./CreateJobPage";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("CreateJobPage", () => {
  it("groups source, delivery, and saving choices into clear creation sections", async () => {
    getJson.mockResolvedValueOnce({ directory: "D:/default" });

    render(<CreateJobPage />);

    expect(screen.getByRole("heading", { name: "来源与平台" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "交付内容" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "保存位置" })).toBeVisible();
    expect(screen.getByText("预检完成后会显示可处理内容，并允许创建任务。"))
      .toBeVisible();
  });

  it("explains every deliverable and opens its representative template", async () => {
    getJson.mockResolvedValueOnce({ directory: "D:/default" });

    render(<CreateJobPage />);

    expect(screen.getByText("逐作品 Markdown")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "查看 蒸馏 Skill 示例" }));
    expect(await screen.findByRole("dialog", { name: "蒸馏 Skill 示例" })).toHaveTextContent("工作流");
    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
  });

  it("requires a current preview before submitting that preview fingerprint", async () => {
    getJson.mockResolvedValueOnce({ directory: "D:/default" });
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
    await screen.findByText("Creator · 可处理 2 / 共 3 条 · 登录状态：configured");
    expect(create).toBeEnabled();

    fireEvent.click(create);
    await waitFor(() => expect(postJson).toHaveBeenLastCalledWith("/api/v1/jobs", {
      target: "https://space.bilibili.com/1",
      platform: "auto",
      outputs: ["episodes", "skill"],
      rag_chunks: false,
      preview_fingerprint: "preview-123",
      destination_mode: "default",
    }));
    expect(screen.getAllByRole("status").at(-1)).toHaveTextContent("任务已创建，可前往任务作战台查看执行进度");
  });
});
