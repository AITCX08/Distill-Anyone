import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { QueueTable } from "./QueueTable";

afterEach(cleanup);

describe("QueueTable", () => {
  it("renders a human-readable title and second-line source metadata", () => {
    const item = { id: "item-1", title: "公开视频：知识整理", meta: "BV1xx · 完成于 2026-08-12 10:15" };
    render(<QueueTable
      ariaLabel="作品执行队列"
      items={[item]}
      getKey={(value) => value.id}
      renderTitle={(value) => value.title}
      renderMeta={(value) => value.meta}
      renderStatus={() => "已完成"}
      renderProgress={() => "100%"}
      renderStage={() => "已交付"}
      renderUpdated={() => "今天 10:15"}
      renderActions={() => "查看"}
    />);

    expect(screen.getByRole("table", { name: "作品执行队列" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "作品标题" })).toBeVisible();
    expect(screen.getByText(item.title)).toBeVisible();
    expect(screen.getByText(item.meta)).toBeVisible();
  });
});
