import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useWorkspace } from "./useWorkspace";

describe("useWorkspace", () => {
  it("uses the mission workspace for an unknown hash", () => {
    window.location.hash = "#unknown";

    const view = renderHook(() => useWorkspace());

    expect(view.result.current).toBe("mission");
  });

  it("updates when the selected workspace hash changes", () => {
    window.location.hash = "#mission";
    const view = renderHook(() => useWorkspace());

    act(() => {
      window.location.hash = "#create";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });

    expect(view.result.current).toBe("create");
  });
});
