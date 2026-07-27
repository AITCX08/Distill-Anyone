import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardRequestError, postJson } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "distill_csrf=; Max-Age=0";
});

describe("postJson", () => {
  it("sends the local CSRF cookie with a same-origin job mutation", async () => {
    document.cookie = "distill_csrf=local-token";
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ job_id: "job-1" }) });
    vi.stubGlobal("fetch", fetchMock);

    await expect(postJson("/api/v1/jobs/job-1/pause", { expected_revision: 4 })).resolves.toEqual({ job_id: "job-1" });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/jobs/job-1/pause", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Distill-CSRF": "local-token" },
      body: JSON.stringify({ expected_revision: 4 }),
    });
  });

  it("reports a network interruption as an offline unconfirmed action", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network interrupted")));

    await expect(postJson("/api/v1/jobs/job-1/pause", { expected_revision: 4 })).rejects.toEqual(
      new DashboardRequestError(0, "offline"),
    );
  });
});
