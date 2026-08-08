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
    getJson
      .mockResolvedValueOnce([{
        job_id: "job-1", status: "completed", revision: 2, platform: "bilibili", creator_name: "Creator",
        total_items: 1, completed_items: 1, failed_items: 0, unsupported_items: 0, updated_at: "2026-07-27T10:00:00Z",
      }])
      .mockResolvedValueOnce([{ artifact_id: "artifact-123", source_id: "bili_1", name: "episode", display_name: "episode.md" }])
      .mockResolvedValueOnce({ artifact_id: "artifact-123", source_id: "bili_1", name: "episode", display_name: "episode.md", content: "# Safe episode" });
    postJson.mockResolvedValueOnce(null);

    render(<ArtifactsPage />);

    expect(await screen.findByText("episode.md")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "预览 episode.md" }));
    expect(await screen.findByText("# Safe episode")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "复制预览内容" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("# Safe episode"));

    fireEvent.click(screen.getByRole("button", { name: "打开所在文件夹 episode.md" }));
    await waitFor(() => expect(postJson).toHaveBeenCalledWith("/api/v1/jobs/job-1/artifacts/artifact-123/reveal", {}));
    expect(screen.queryByText(/C:\\|Users\\|AppData/)).not.toBeInTheDocument();
  });
});
