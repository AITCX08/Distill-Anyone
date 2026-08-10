import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getJson = vi.hoisted(() => vi.fn());
const postJson = vi.hoisted(() => vi.fn());
const writeText = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", () => ({ getJson, postJson }));

import { ArtifactsPage } from "./ArtifactsPage";

describe("ArtifactsPage", () => {
  beforeEach(() => {
    getJson.mockReset();
    postJson.mockReset();
    writeText.mockReset().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
  });

  it("previews, copies, and reveals only a server-listed text artifact", async () => {
    getJson.mockImplementation((path: string) => {
      if (path === "/api/v1/jobs") return Promise.resolve([{
        job_id: "job-1", status: "completed", revision: 2, platform: "bilibili", creator_name: "Creator",
        total_items: 1, completed_items: 1, failed_items: 0, unsupported_items: 0, updated_at: "2026-07-27T10:00:00Z",
      }]);
      if (path === "/api/v1/jobs/job-1/details") return Promise.resolve({
        job_id: "job-1", display_title: "量化两年", creator_name: "Creator", destination: "D:/deliveries",
        artifact_count: 1, completed_at: "2026-08-10T00:00:00Z",
      });
      if (path === "/api/v1/jobs/job-1/artifacts") return Promise.resolve([{
        artifact_id: "artifact-123", source_id: "bili_1", name: "episode", display_name: "episode.md",
        display_title: "开场与概念", kind: "episode", size_bytes: 2048, created_at: "2026-08-10T00:00:00Z",
      }]);
      if (path === "/api/v1/jobs/job-1/artifacts/artifact-123") return Promise.resolve({
        artifact_id: "artifact-123", source_id: "bili_1", name: "episode", display_name: "episode.md",
        display_title: "开场与概念", kind: "episode", size_bytes: 2048, created_at: "2026-08-10T00:00:00Z", content: "# Safe episode",
      });
      return Promise.reject(new Error(`unexpected request: ${path}`));
    });
    postJson.mockResolvedValue(null);

    render(<ArtifactsPage />);

    expect(await screen.findByText("episode.md")).toBeVisible();
    expect(await screen.findByRole("option", { name: "Creator · 量化两年" })).toBeVisible();
    expect(screen.getByText("D:/deliveries")).toBeVisible();
    expect(screen.getByText(/开场与概念 · episode · 2.0 KB/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "预览 episode.md" }));
    expect(await screen.findByText("# Safe episode")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "复制预览内容" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("# Safe episode"));

    fireEvent.click(screen.getByRole("button", { name: "打开任务保存位置" }));
    await waitFor(() => expect(postJson).toHaveBeenCalledWith("/api/v1/jobs/job-1/reveal-output", {}));

    fireEvent.click(screen.getByRole("button", { name: "打开所在文件夹 episode.md" }));
    await waitFor(() => expect(postJson).toHaveBeenCalledWith("/api/v1/jobs/job-1/artifacts/artifact-123/reveal", {}));
    expect(screen.queryByText(/C:\\|Users\\|AppData/)).not.toBeInTheDocument();
  });
});
