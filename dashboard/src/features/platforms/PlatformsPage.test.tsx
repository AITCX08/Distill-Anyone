import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const getJson = vi.hoisted(() => vi.fn());
const postJson = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", () => ({ getJson, postJson }));

import { PlatformsPage } from "./PlatformsPage";

describe("PlatformsPage", () => {
  it("uses Chinese guidance without exposing credential data", async () => {
    getJson.mockResolvedValueOnce([{
      name: "douyin",
      item_types: ["video"],
      requires_browser: true,
      requires_auth: true,
      auth_status: "missing",
      auth_message: "Scan in external Chromium",
    }]);
    postJson.mockResolvedValueOnce({ operation_id: "op-1", platform: "douyin", status: "opening_browser" });

    render(<PlatformsPage />);

    expect(await screen.findByText("请在浏览器中扫码登录")).toBeVisible();
    expect(screen.getByText("登录状态由本地引擎管理；凭据始终仅保存在本机，不会显示在页面上。")).toBeVisible();

    expect(screen.getByText("未登录 · 视频")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "登录 抖音" }));
    await waitFor(() => expect(postJson).toHaveBeenCalledWith("/api/v1/platforms/douyin/login", {}));

    expect(screen.getByText("登录流程已启动。完成扫码或确认后，刷新平台状态。")).toBeVisible();
  });
});
