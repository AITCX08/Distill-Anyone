import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OutputTemplateDialog } from "./OutputTemplateDialog";

describe("OutputTemplateDialog", () => {
  it("explains the selected deliverable with a readable representative template", () => {
    render(<OutputTemplateDialog output="skill" open onOpenChange={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "蒸馏 Skill 示例" })).toHaveTextContent("工作流");
    expect(screen.getByText(/适合沉淀可复用的创作方法/)).toBeVisible();
  });
});
