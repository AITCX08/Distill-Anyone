import { expect, test, type Page } from "@playwright/test";

type CreatePayload = {
  target: string;
  platform: string;
  outputs: string[];
  rag_chunks: boolean;
  preview_fingerprint?: string;
};

async function installWorkflowFixture(page: Page, received: { preview?: CreatePayload; create?: CreatePayload }) {
  await page.addInitScript(() => {
    class FixtureEventSource {
      addEventListener() {}
      close() {}
    }
    Object.defineProperty(window, "EventSource", { configurable: true, value: FixtureEventSource });
  });

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "GET" && (path === "/api/v1/platforms" || path === "/api/v1/jobs")) {
      return route.fulfill({ json: [] });
    }
    if (request.method() === "POST" && path === "/api/v1/jobs/preview") {
      received.preview = request.postDataJSON() as CreatePayload;
      return route.fulfill({ json: {
        fingerprint: "fixture-preview-fingerprint",
        platform: "bilibili",
        creator_id: "fixture-creator",
        creator_name: "Fixture creator",
        total_items: 4,
        processable_items: 3,
        skipped_items: 1,
        unsupported_items: 0,
        auth_status: "configured",
      } });
    }
    if (request.method() === "POST" && path === "/api/v1/jobs") {
      received.create = request.postDataJSON() as CreatePayload;
      return route.fulfill({ json: { job_id: "fixture-job", status: "queued", revision: 1 } });
    }
    return route.fulfill({ status: 404, json: { error: { code: "fixture_not_found" } } });
  });
}

test("creates only from a matching fixture preview without external data", async ({ page }) => {
  const received: { preview?: CreatePayload; create?: CreatePayload } = {};
  await installWorkflowFixture(page, received);

  await page.goto("/");
  await page.getByLabel("Creator URL").fill("https://fixture.invalid/creator");
  await expect(page.getByRole("button", { name: "Create mission" })).toBeDisabled();

  await page.getByRole("button", { name: "Inspect source" }).click();
  await expect(page.locator("#create [role='status']")).toContainText("Fixture creator");
  await page.getByRole("button", { name: "Create mission" }).click();
  await expect(page.getByText("Mission fixture-job accepted by the local engine.")).toBeVisible();

  expect(received.preview).toEqual({
    target: "https://fixture.invalid/creator",
    platform: "auto",
    outputs: ["episodes", "skill"],
    rag_chunks: false,
  });
  expect(received.create).toEqual({
    ...received.preview,
    preview_fingerprint: "fixture-preview-fingerprint",
  });
});
