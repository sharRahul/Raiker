/**
 * QUI-G06: real host and owner session; inject a failed response only for the
 * operation under test. No model is used by these local Memory controls.
 */
import { expect, test } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { capture } from "./capture";

test("RT-MEM-RECOVERY-01: memory use failure offers a safe next step", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/memory?tab=controls`);
  const toggle = page.getByRole("switch", { name: "Incognito session" });
  await expect(toggle).toBeVisible();
  await page.route("**/api/memory/incognito", async route => {
    if (route.request().method() === "PUT") {
      await route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"injected failure"}' });
    } else await route.continue();
  });
  await toggle.click();
  await expect(page.getByRole("alert").filter({ hasText: "Could not update memory use" })).toContainText("Refresh Memory to check the current setting before trying again.");
  await capture(page, "../../docs/screenshots/2026-11-06-memory-recovery/memory-use-error.png");
});

test("RT-MEM-RECOVERY-02: export failure names download recovery", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/memory?tab=controls`);
  await page.getByText("Advanced memory management", { exact: true }).click();
  await page.route("**/api/memory/export", route => route.fulfill({
    status: 503, contentType: "application/json", body: '{"detail":"injected failure"}',
  }));
  await page.getByRole("button", { name: "Export memories" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Could not export memories" })).toContainText("download permissions");
  await capture(page, "../../docs/screenshots/2026-11-06-memory-recovery/export-error.png");
});
