import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const getJson = vi.hoisted(() => vi.fn());
const postJson = vi.hoisted(() => vi.fn());

vi.mock("../../api/client", () => ({ getJson, postJson }));

import { OutputDirectoryField } from "./OutputDirectoryField";

describe("OutputDirectoryField", () => {
  it("sends an override token only after the directory is validated", async () => {
    getJson.mockResolvedValueOnce({ directory: "D:/default" });
    postJson.mockResolvedValueOnce({
      directory: "D:/notes", token: "validated-token", expires_at: "2026-08-10T00:05:00Z",
    });
    const onChange = vi.fn();

    render(<OutputDirectoryField onChange={onChange} />);

    await screen.findByText("默认保存位置：D:/default");
    expect(screen.getByText("不勾选时沿用默认位置；覆盖位置只影响本次任务。"))
      .toBeVisible();
    fireEvent.click(screen.getByRole("checkbox", { name: "本次使用其他保存位置" }));
    fireEvent.change(screen.getByLabelText("本次保存位置"), { target: { value: "D:/notes" } });
    fireEvent.click(screen.getByRole("button", { name: "校验位置" }));

    await screen.findByText("保存位置可用");
    expect(postJson).toHaveBeenCalledWith("/api/v1/directories/validate", { directory: "D:/notes" });
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith({
      destinationMode: "override", destinationToken: "validated-token",
    }));
  });
});
