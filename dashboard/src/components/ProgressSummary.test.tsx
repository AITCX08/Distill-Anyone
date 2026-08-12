import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ProgressSummary } from "./ProgressSummary";

afterEach(cleanup);

describe("ProgressSummary", () => {
  it("shows a clamped percentage, stage, and readable task counts", () => {
    render(<ProgressSummary progress={0.72} stage="内容提取" counts={{ completed: 1, active: 1, queued: 1, total: 3 }} />);

    expect(screen.getByText("72%")).toBeVisible();
    expect(screen.getByText("内容提取")).toBeVisible();
    expect(screen.getByText("已完成")).toBeVisible();
    expect(screen.getByText("总任务")).toBeVisible();
    expect(screen.getByText("3")).toBeVisible();
  });
});
