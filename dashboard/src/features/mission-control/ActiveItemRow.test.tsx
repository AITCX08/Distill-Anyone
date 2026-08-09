import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActiveItemRow } from "./ActiveItemRow";

const downloadingItem = {
  source_id: "item-1", title: "Episode 1", row_id: 1, stage: "downloading", stage_progress: null,
  overall_progress: 0.1, completed_bytes: 1024, total_bytes: null, bytes_per_second: 1024,
  download_eta_seconds: null, audio_completed_seconds: 0, audio_total_seconds: null, asr_rtf: null,
};

describe("ActiveItemRow", () => {
  it("is memoized to avoid unrelated mission updates rerendering stable rows", () => {
    const component = ActiveItemRow as unknown as { $$typeof?: symbol };
    expect(component.$$typeof).toBe(Symbol.for("react.memo"));
  });

  it("shows an unknown file size without inventing a zero total", () => {
    render(<ActiveItemRow item={downloadingItem} />);
    expect(screen.getByText("文件大小未知")).toBeVisible();
    expect(screen.queryByText("0.0 KB / 0.0 KB")).not.toBeInTheDocument();
  });

  it("does not render download telemetry while transcription is active", () => {
    const view = render(<ActiveItemRow item={{ ...downloadingItem, stage: "transcribing", bytes_per_second: 0 }} />);
    expect(screen.getByText("正在转写中，暂不显示下载速度")).toBeVisible();
    expect(within(view.container).queryByText("下载预计 未知")).not.toBeInTheDocument();
  });
});
