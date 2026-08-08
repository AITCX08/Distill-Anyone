import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardRequestError, postJson } from "../../api/client";
import { MissionControls } from "./MissionControls";

vi.mock("../../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/client")>()),
  postJson: vi.fn(),
}));

const serverJob = { job_id: "job-1", status: "running", revision: 4 } as const;

afterEach(() => vi.resetAllMocks());

describe("MissionControls", () => {
  it("sends pause with the server revision and waits for the confirmed response", async () => {
    const onJobUpdated = vi.fn();
    vi.mocked(postJson).mockResolvedValue({ ...serverJob, status: "pause_requested", revision: 5 });
    render(<MissionControls job={serverJob} retryableFailures={false} onJobUpdated={onJobUpdated} />);

    fireEvent.click(screen.getByRole("button", { name: "暂停任务" }));

    await waitFor(() => expect(postJson).toHaveBeenCalledWith(
      "/api/v1/jobs/job-1/pause", { expected_revision: 4 },
    ));
    await waitFor(() => expect(onJobUpdated).toHaveBeenCalledWith({ ...serverJob, status: "pause_requested", revision: 5 }));
  });

  it("shows a revision conflict without claiming the action completed", async () => {
    vi.mocked(postJson).mockRejectedValue(new DashboardRequestError(409, "revision_conflict"));
    render(<MissionControls job={{ ...serverJob, status: "paused" }} retryableFailures={false} onJobUpdated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "继续任务" }));

    expect(await screen.findByText("任务状态已变化，请等待下一次服务端刷新后再试。")).toBeVisible();
  });

  it("offers retry for server-reported failures and reports an offline action as unconfirmed", async () => {
    vi.mocked(postJson).mockRejectedValue(new DashboardRequestError(0, "offline"));
    render(<MissionControls job={serverJob} retryableFailures onJobUpdated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "重试失败项目" }));

    await waitFor(() => expect(postJson).toHaveBeenCalledWith(
      "/api/v1/jobs/job-1/retry-failed", { expected_revision: 4 },
    ));
    expect(await screen.findByText("连接已断开，操作尚未确认。")).toBeVisible();
  });

  it("does not accept a malformed successful action response", async () => {
    const onJobUpdated = vi.fn();
    vi.mocked(postJson).mockResolvedValue({ job_id: "job-1", status: "paused", revision: "not-a-number" });
    const view = render(<MissionControls job={serverJob} retryableFailures={false} onJobUpdated={onJobUpdated} />);

    fireEvent.click(within(view.container).getByRole("button", { name: "暂停任务" }));

    expect(await within(view.container).findByText("操作尚未确认，请查看下一次服务端刷新。")).toBeVisible();
    expect(onJobUpdated).not.toHaveBeenCalled();
  });

  it.each([["pause_requested", "正在暂停"], ["paused", "已暂停"]] as const)("announces the server %s state with a keyboard-labelled resume control", (status, label) => {
    const view = render(<MissionControls job={{ ...serverJob, status }} retryableFailures={false} onJobUpdated={vi.fn()} />);

    expect(within(view.container).getByText(`任务状态：${label}`)).toBeVisible();
    expect(within(view.container).getByRole("button", { name: "继续任务" })).toBeVisible();
  });
});
