import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StatusPill } from "./StatusPill";

afterEach(cleanup);

describe("StatusPill", () => {
  it("renders an explicit status label instead of relying on color", () => {
    render(<StatusPill tone="active" label="进行中" />);

    expect(screen.getByText("进行中")).toBeVisible();
    expect(screen.getByText("进行中")).toHaveAttribute("data-tone", "active");
  });
});
