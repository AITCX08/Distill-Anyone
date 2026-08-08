import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("renders Chinese navigation, live engine state, and keyboard-visible controls", () => {
    render(<AppShell><main>content</main></AppShell>);

    expect(screen.getByRole("navigation", { name: "主导航" })).toHaveTextContent("任务作战台");
    expect(screen.getByText("本地引擎在线")).toBeVisible();
    expect(screen.getByRole("link", { name: "新建任务" })).toBeVisible();
  });
});
