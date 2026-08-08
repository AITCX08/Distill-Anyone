import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SeriesRail } from "./SeriesRail";

describe("SeriesRail", () => {
  it("renders one semantic control for every known series part", () => {
    const onSelect = vi.fn();
    render(<SeriesRail total={4} completed={2} active={1} failed={0} selectedRowId={3} onSelect={onSelect} />);

    expect(screen.getAllByRole("button", { name: /第 [1-4] 集/ })).toHaveLength(4);
    expect(screen.getByRole("button", { name: "第 3 集，执行中" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "第 4 集，等待处理" }));
    expect(onSelect).toHaveBeenCalledWith(4);
  });
});
