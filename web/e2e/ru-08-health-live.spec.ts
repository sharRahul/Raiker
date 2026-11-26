/**
 * RU-08 — Diagnostics lists this machine's readiness, each check with its fix,
 * against a running host (any fresh workspace; no model or key is needed):
 *
 *   raiker-web --workspace <ws> --port 8765 --no-browser
 *
 * Live case (docs/architecture/WEB_APP_LIVE_TEST.md): RT-HEALTH-01.
 */
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { capturePath } from "./capture";
import { dismissFirstRunModelSetup, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "docs", "plans", "screenshots", "working");

test("RT-HEALTH-01 — Diagnostics lists this machine's checks with their fixes", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signInAsOwner(page, BASE);
  await dismissFirstRunModelSetup(page).catch(() => undefined);
  await page.goto(`${BASE}/#/observe?tab=overview`);
  const card = page.getByTestId("machine-readiness");
  // The section remembers being open; open it only when it is closed.
  await expect(page.getByText("Health, in detail").first()).toBeVisible({ timeout: 60_000 });
  if (!(await card.isVisible())) {
    await page.getByRole("group").filter({ hasText: "Health, in detail" }).first().getByText("Health, in detail").click();
  }
  await expect(card.getByRole("heading", { name: "This machine" })).toBeVisible({ timeout: 60_000 });
  await expect(card).toContainText(/Every mandatory requirement is met|mandatory requirements? (is|are) not met/);
  await card.getByText(/checks? pass/).click();
  await expect(card).toContainText("Operating system");
  await expect(card).toContainText("Free storage");
  // RT-HEALTH-02/03 — what first run sets up (RT-HEALTH-03: the model and disk-and-memory facts), each with the page that fixes it.
  const facts = card.getByTestId("health-facts");
  for (const label of ["Model", "Disk and memory", "Command sandbox", "Backups", "Search by meaning", "Voice", "Updates", "Always-on host"]) {
    await expect(facts).toContainText(label, { timeout: 30_000 });
  }
  await expect(facts).not.toContainText("not read");
  await card.scrollIntoViewIfNeeded();
  await expect(card).toBeVisible();
  await card.scrollIntoViewIfNeeded();
  await page.screenshot({ path: capturePath(join(SHOTS, "ru-08-this-machine-card.png")) });
});
