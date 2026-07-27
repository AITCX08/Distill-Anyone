import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const getJson = vi.hoisted(() => vi.fn());
const postJson = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", () => ({ getJson, postJson }));

import { PlatformsPage } from "./PlatformsPage";

describe("PlatformsPage", () => {
  it("guides QR scanning in external Chromium without showing credential data", async () => {
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

    expect(await screen.findByText("Scan in external Chromium")).toBeVisible();
    expect(screen.getByText("Scan the QR code in external Chromium. This dashboard never shows or stores QR or cookie data.")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Open Douyin login" }));
    await waitFor(() => expect(postJson).toHaveBeenCalledWith("/api/v1/platforms/douyin/login", {}));

    expect(screen.getByText("External Chromium is opening. Complete the scan there, then refresh platform status.")).toBeVisible();
  });
});
