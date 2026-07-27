import { expect, test, type Page } from "@playwright/test";

const snapshot = {
  job_id: "fixture-job", revision: 2, overall_progress: 0.5, coverage: 0.25,
  counts: { total: 4, active: 1, completed: 1, failed: 0, retry: 0, unsupported: 0, queued: 2, enumerated: 4 },
  eta_total_seconds: 60, eta_active_slowest_seconds: 30, provisional_eta: false,
  active_items: [{
    source_id: "fixture_1", title: "Fixture work", row_id: 1, stage: "downloading", stage_progress: 0.5,
    overall_progress: 0.1, completed_bytes: 1024, total_bytes: 2048, bytes_per_second: 12288,
    download_eta_seconds: 1, audio_completed_seconds: 0, audio_total_seconds: null, asr_rtf: null,
  }],
};

type PlatformFixture = {
  name: string;
  item_types: string[];
  requires_browser: boolean;
  requires_auth: boolean;
  auth_status: string;
  auth_message: string;
};

async function installFixtures(page: Page, platforms: PlatformFixture[] = []) {
  await page.addInitScript((initialSnapshot) => {
    class FixtureEventSource {
      listeners = new Map();
      constructor() {
        setTimeout(() => this.listeners.get("snapshot")?.forEach((listener) => listener({
          data: JSON.stringify({ schema_version: 1, jobs: [{ job_id: initialSnapshot.job_id, status: "running", revision: 2 }], progress_snapshots: [initialSnapshot] }),
        })), 0);
      }
      addEventListener(type, listener) {
        this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
      }
      close() {}
    }
    Object.defineProperty(window, "EventSource", { configurable: true, value: FixtureEventSource });
  }, snapshot);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/platforms") return route.fulfill({ json: platforms });
    if (path === "/api/v1/jobs") return route.fulfill({ json: [] });
    return route.fulfill({ status: 404, json: { error: { code: "fixture_not_found" } } });
  });
}

test("recovers a fixture snapshot after reload and renders transfer metrics", async ({ page }) => {
  await installFixtures(page);

  await page.goto("/");
  await expect(page.getByLabel("Mission Control")).toBeVisible();
  await expect(page.getByText("1.0 KB / 2.0 KB")).toBeVisible();
  await expect(page.getByText("12.0 KB/s")).toBeVisible();
  await expect(page.getByText(/Overall ETA 01:00/)).toBeVisible();

  await page.reload();
  await expect(page.getByText("Transfer ETA 00:01")).toBeVisible();
});

test("uses external Chromium wording for fixture platform login", async ({ page }) => {
  await installFixtures(page, [{
    name: "douyin", item_types: ["video"], requires_browser: true, requires_auth: true,
    auth_status: "missing", auth_message: "Scan in external Chromium",
  }]);

  await page.goto("/");

  await expect(page.getByText("Scan the QR code in external Chromium. This dashboard never shows or stores QR or cookie data.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Open Douyin login" })).toBeVisible();
});
