import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Button } from "@fluentui/react-components";

import { PageHeader } from "./PageHeader";

afterEach(cleanup);

describe("PageHeader", () => {
  it("renders a Chinese title, description, and optional action", () => {
    render(<PageHeader
      title="创建任务"
      description="预检来源后创建任务"
      actions={<Button>开始创建</Button>}
    />);

    expect(screen.getByRole("heading", { level: 1, name: "创建任务" })).toBeVisible();
    expect(screen.getByText("预检来源后创建任务")).toBeVisible();
    expect(screen.getByRole("button", { name: "开始创建" })).toBeVisible();
  });
});
