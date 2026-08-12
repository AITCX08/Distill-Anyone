import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";

afterEach(cleanup);

describe("AppShell", () => {
  it("renders the unified workbench navigation, local engine state, and privacy footer", () => {
    render(<AppShell><main>content</main></AppShell>);

    expect(screen.getByText("DISTILL // EVERYTHING")).toBeVisible();
    expect(screen.getByText("本地内容蒸馏工作台")).toBeVisible();
    expect(screen.getByRole("navigation", { name: "主导航" })).toHaveTextContent("工作台");
    expect(screen.getByText("本地引擎在线")).toBeVisible();
    expect(screen.getByRole("link", { name: "创建任务" })).toBeVisible();
    expect(screen.getByRole("contentinfo")).toHaveTextContent("本地优先");
  });

  it("keeps creator workbench navigation readable on a narrow viewport", () => {
    render(<AppShell activeWorkspace="create"><main>内容</main></AppShell>);

    expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
    expect(screen.getByRole("link", { name: "创建任务" })).toHaveAttribute("aria-current", "page");
  });
});
