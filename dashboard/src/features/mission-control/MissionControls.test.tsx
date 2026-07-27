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

    fireEvent.click(screen.getByRole("button", { name: "Pause job" }));

    await waitFor(() => expect(postJson).toHaveBeenCalledWith(
      "/api/v1/jobs/job-1/pause", { expected_revision: 4 },
    ));
    await waitFor(() => expect(onJobUpdated).toHaveBeenCalledWith({ ...serverJob, status: "pause_requested", revision: 5 }));
  });

  it("shows a revision conflict without claiming the action completed", async () => {
    vi.mocked(postJson).mockRejectedValue(new DashboardRequestError(409, "revision_conflict"));
    render(<MissionControls job={{ ...serverJob, status: "paused" }} retryableFailures={false} onJobUpdated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Resume job" }));

    expect(await screen.findByText("Job changed on the server. Wait for the next snapshot before retrying.")).toBeVisible();
  });

  it("offers retry for server-reported failures and reports an offline action as unconfirmed", async () => {
    vi.mocked(postJson).mockRejectedValue(new DashboardRequestError(0, "offline"));
    render(<MissionControls job={serverJob} retryableFailures onJobUpdated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Retry failed items" }));

    await waitFor(() => expect(postJson).toHaveBeenCalledWith(
      "/api/v1/jobs/job-1/retry-failed", { expected_revision: 4 },
    ));
    expect(await screen.findByText("Connection lost. Action was not confirmed.")).toBeVisible();
  });

  it("does not accept a malformed successful action response", async () => {
    const onJobUpdated = vi.fn();
    vi.mocked(postJson).mockResolvedValue({ job_id: "job-1", status: "paused", revision: "not-a-number" });
    const view = render(<MissionControls job={serverJob} retryableFailures={false} onJobUpdated={onJobUpdated} />);

    fireEvent.click(within(view.container).getByRole("button", { name: "Pause job" }));

    expect(await within(view.container).findByText("Action was not confirmed. Check the next server snapshot.")).toBeVisible();
    expect(onJobUpdated).not.toHaveBeenCalled();
  });

  it.each(["pause_requested", "paused"])("announces the server %s state with a keyboard-labelled resume control", (status) => {
    const view = render(<MissionControls job={{ ...serverJob, status }} retryableFailures={false} onJobUpdated={vi.fn()} />);

    expect(within(view.container).getByText(`Job status: ${status}`)).toBeVisible();
    expect(within(view.container).getByRole("button", { name: "Resume job" })).toBeVisible();
  });
});
