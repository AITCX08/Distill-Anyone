import { describe, expect, it } from "vitest";

import { snapshotTraceEntries } from "./useMissionControl";

describe("snapshotTraceEntries", () => {
  it("restores prior trace lines for the selected job", () => {
    expect(snapshotTraceEntries({
      traces: {
        "job-1": ["Paused at checkpoint."],
        "job-2": ["Other job."],
      },
    }, "job-1")).toEqual(["Paused at checkpoint."]);
  });
});
