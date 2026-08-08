import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LiveTrace, shouldFollowLogTail } from "./LiveTrace";

describe("LiveTrace", () => {
  it("renders only the newest bounded server trace entries", () => {
    const entries = Array.from({ length: 101 }, (_, index) => `server trace ${index + 1}`);
    render(<LiveTrace entries={entries} />);
    const output = screen.getByText((_, element) => element?.tagName === "PRE");

    expect(output).not.toHaveTextContent(/server trace 1(?:\n|$)/);
    expect(output).toHaveTextContent("server trace 101");
  });

  it("bounds a single server trace line before rendering", () => {
    const view = render(<LiveTrace entries={["x".repeat(1001)]} />);
    const output = within(view.container).getByText((_, element) => element?.tagName === "PRE");

    expect(output.textContent).toHaveLength(1000);
  });

  it("uses a semantic log region for streamed server output", () => {
    const view = render(<LiveTrace entries={["download started"]} />);

    expect(within(view.container).getByRole("log")).toHaveTextContent("download started");
  });

  it("only follows new output when the reader is already near the tail", () => {
    expect(shouldFollowLogTail({ scrollHeight: 1_000, scrollTop: 776, clientHeight: 200 })).toBe(true);
    expect(shouldFollowLogTail({ scrollHeight: 1_000, scrollTop: 200, clientHeight: 200 })).toBe(false);
  });
});
