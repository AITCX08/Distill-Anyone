import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TaskDetailDrawer } from "./TaskDetailDrawer";

const item = {
  source_id: "bili_BV1xx", title: "第 6 集", row_id: 6, stage: "transcribing", stage_progress: 0.5,
  overall_progress: 0.4, completed_bytes: 1024, total_bytes: 2048, bytes_per_second: 1024,
  download_eta_seconds: 10, audio_completed_seconds: 30, audio_total_seconds: 60, asr_rtf: 0.8,
};

describe("TaskDetailDrawer", () => {
  it("shows the selected task's actual server identifiers and supports closing", () => {
    const onClose = vi.fn();
    render(<TaskDetailDrawer item={item} onClose={onClose} />);

    expect(screen.getByRole("complementary", { name: "任务详情" })).toHaveTextContent("bili_BV1xx");
    expect(screen.getByText("转写中")).toBeVisible();
    screen.getByRole("button", { name: "关闭详情" }).click();
    expect(onClose).toHaveBeenCalledOnce();
  });
});
