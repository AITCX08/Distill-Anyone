import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ActiveItemRow } from "./ActiveItemRow";

describe("ActiveItemRow", () => {
  it("is memoized to avoid unrelated mission updates rerendering stable rows", () => {
    const component = ActiveItemRow as unknown as { $$typeof?: symbol };

    expect(component.$$typeof).toBe(Symbol.for("react.memo"));
  });

  it("shows an unknown file size without inventing a zero total", () => {
    render(<ActiveItemRow item={{
      source_id: "item-1", title: "第 1 集", row_id: 1, stage: "downloading", stage_progress: null,
      overall_progress: 0.1, completed_bytes: 1024, total_bytes: null, bytes_per_second: 1024,
      download_eta_seconds: null, audio_completed_seconds: 0, audio_total_seconds: null, asr_rtf: null,
    }} />);

    expect(screen.getByText("文件大小未知")).toBeVisible();
    expect(screen.queryByText("0.0 KB / 0.0 KB")).not.toBeInTheDocument();
  });
});
