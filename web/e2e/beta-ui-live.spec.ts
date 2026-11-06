/**
 * Beta-plan UX evidence. This deliberately needs no model key: the badge and
 * the status vocabulary must be honest before a provider is configured.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../output/playwright/beta-ui";

test("RT-BETA-UX-01 — beta feedback and standard runtime status are reachable", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);

  await page.goto(`${BASE}/#/home`);
  const badge = page.getByRole("link", { name: "Beta — send feedback" });
  await expect(badge).toBeVisible({ timeout: 30_000 });
  await expect(badge).toHaveAttribute("href", "#/settings?tab=general#beta-feedback");
  await capture(page, `${SHOTS}/beta-badge-home.png`, badge);

  await page.goto(`${BASE}/#/settings?tab=runtime`);
  await expect(page.getByRole("heading", { name: "Runtime configuration" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Raiker runtime/)).toContainText(/Ready|Working|Needs you|Unavailable|Failed/);
  await capture(page, `${SHOTS}/runtime-status.png`);
});
