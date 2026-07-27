import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LiveTrace } from "./LiveTrace";

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
});
