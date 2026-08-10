import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MissionOverview } from "./MissionOverview";

afterEach(cleanup);

describe("MissionOverview", () => {
  it("uses a series title instead of a job identifier in the completed overview", () => {
    render(<MissionOverview
      snapshot={{
        job_id: "job-internal-1", revision: 1, overall_progress: 1, coverage: 1,
        counts: { total: 8, active: 0, completed: 8, failed: 0, retry: 0, unsupported: 0, queued: 0, enumerated: 8 },
        eta_total_seconds: null, eta_active_slowest_seconds: null, provisional_eta: false, active_items: [],
      }}
      job={{
        job_id: "job-internal-1", status: "completed", revision: 1,
        display_title: "天纪四柱命卦", creator_name: "倪海厦", artifact_count: 16,
        completed_at: "2026-08-10T00:00:00Z",
      }}
      onViewArtifacts={() => undefined}
    />);

    expect(screen.getByRole("heading", { name: "倪海厦 · 天纪四柱命卦" })).toBeVisible();
    expect(screen.getByText("已完成 8/8")).toBeVisible();
    expect(screen.queryByText("估算中")).not.toBeInTheDocument();
    expect(screen.queryByText("job-internal-1")).not.toBeInTheDocument();
  });

  it("shows confirmed overview values and explains when download telemetry is unavailable", () => {
    render(<MissionOverview snapshot={{
      job_id: "job-1", revision: 1, overall_progress: 0.5, coverage: 0.25,
      counts: { total: 4, active: 0, completed: 1, failed: 0, retry: 0, unsupported: 0, queued: 3, enumerated: 4 },
      eta_total_seconds: 60, eta_active_slowest_seconds: null, provisional_eta: false, active_items: [],
    }} />);

    expect(screen.getByText("50%")).toBeVisible();
    expect(screen.getByText("暂无活动任务")).toBeVisible();
    expect(screen.getByText("仅下载时显示")).toBeVisible();
    expect(screen.queryByText("0.0 KB/秒")).not.toBeInTheDocument();
  });
});
