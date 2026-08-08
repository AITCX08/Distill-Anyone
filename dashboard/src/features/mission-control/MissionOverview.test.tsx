import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MissionOverview } from "./MissionOverview";

describe("MissionOverview", () => {
  it("shows confirmed overview values and does not invent a missing throughput", () => {
    render(<MissionOverview snapshot={{
      job_id: "job-1", revision: 1, overall_progress: 0.5, coverage: 0.25,
      counts: { total: 4, active: 0, completed: 1, failed: 0, retry: 0, unsupported: 0, queued: 3, enumerated: 4 },
      eta_total_seconds: 60, eta_active_slowest_seconds: null, provisional_eta: false, active_items: [],
    }} />);

    expect(screen.getByText("50%")).toBeVisible();
    expect(screen.getByText("暂无活动任务")).toBeVisible();
    expect(screen.getByText("未知")).toBeVisible();
    expect(screen.queryByText("0.0 KB/秒")).not.toBeInTheDocument();
  });
});
