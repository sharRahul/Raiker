/**
 * QUI-G06: running host + real owner UI. Fault injection is limited to the
 * target endpoint; Activity cases supply a synthetic job to avoid downloads.
 * No provider credentials or model inference are needed.
 */
import { expect, test } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { captureElement } from "./capture";

const SETTINGS = `${BASE}/#/settings?tab=advanced&kind=models`;
const fail = { status: 503, contentType: "application/json", body: '{"detail":{"reason_code":"injected_failure"}}' };
const shots = "../../output/playwright/2026-11-06-model-recovery";
test.describe.configure({ mode: "serial", timeout: 120_000 });

test("RT-MODEL-RECOVERY-01: library read failure offers recovery on a phone", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/model-library", route => route.fulfill(fail));
  await page.goto(SETTINGS);
  const alert = page.getByRole("alert").filter({ hasText: "Could not load the local model library" });
  await expect(alert).toContainText("Reopen this panel");
  await expect(page.getByText("Loading your model library…", { exact: true })).toHaveCount(0);
  await captureElement(alert.locator(".."), `${shots}/library-read-phone.png`);
});

test("RT-MODEL-RECOVERY-02: scan failure retains its recovery step", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.route("**/api/model-library/rescan", route => route.fulfill(fail));
  await page.goto(SETTINGS);
  await page.getByRole("button", { name: "Scan now", exact: true }).click();
  const alert = page.getByRole("alert").filter({ hasText: "Could not scan the approved model folders" });
  await expect(alert).toContainText("Choose Scan now");
  await captureElement(alert.locator(".."), `${shots}/library-scan.png`);
});

for (const action of ["retry", "cancel", "inspect", "clear"] as const) {
  test(`RT-MODEL-RECOVERY-${{ retry: "03", cancel: "04", inspect: "05", clear: "06" }[action]}: ${action} failure is visible`, async ({ page }) => {
    await signInAsOwner(page, BASE);
    await page.route("**/api/model-operations", route => route.fulfill({
      contentType: "application/json", body: JSON.stringify({ items: [{
        operation_id: "mop_recovery_ui", kind: "download", target: "Recovery test job",
        state: action === "cancel" ? "running" : "failed",
        phase: action === "cancel" ? "downloading" : "failed",
        progress_percent: null, retryable: true, partial_files_present: action === "inspect",
      }] }),
    }));
    await page.route("**/api/model-operations/mop_recovery_ui**", route => route.fulfill(fail));
    await page.goto(SETTINGS);
    const job = page.getByRole("article").filter({ hasText: "Recovery test job" });
    if (action === "retry" || action === "cancel") {
      await job.getByRole("button", { name: action === "retry" ? "Retry" : "Cancel", exact: true }).click();
    } else {
      await job.getByRole("button", { name: /More actions for/ }).click();
      await page.getByRole("menuitem", { name: action === "inspect" ? "Delete partial files" : "Clear record" }).click();
    }
    const message = {
      retry: "Could not retry the model job", cancel: "Could not cancel the model job",
      inspect: "Could not inspect the model job", clear: "Could not clear the model job record",
    }[action];
    const alert = page.getByRole("alert").filter({ hasText: message });
    await expect(alert).toBeVisible();
    if (action === "retry") {
      // A successful list refresh must not erase the action's error.
      await expect.poll(() => page.getByRole("article").filter({ hasText: "Recovery test job" }).count()).toBe(1);
      await expect(alert).toContainText("before retrying again");
    }
    if (action === "inspect") await expect(page.getByRole("alertdialog")).toHaveCount(0);
    await captureElement(alert.locator(".."), `${shots}/activity-${action}.png`);
  });
}
