import { expect, test } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { capture } from "./capture";
const failed = { status: 503, json: { detail: { reason_code: "injected_failure" } } };
const SHOTS = "../../output/playwright/2026-11-09-beta-recovery";
test.setTimeout(120_000);
test.beforeEach(async ({ page }) => { await signInAsOwner(page, BASE); });

test("RT-BETA-REC-01: Messaging distinguishes a failed read and recovers", async ({ page }) => {
  await page.route("**/api/channels", r => r.fulfill(failed));
  await page.goto(`${BASE}/#/connections?tab=channels`);
  await expect(page.getByRole("alert")).toContainText("Messaging profiles could not be read");
  await capture(page, `${SHOTS}/messaging-read.png`);
  await page.unroute("**/api/channels");
  await page.getByRole("button", { name: "Retry messaging" }).click();
  await expect(page.getByRole("button", { name: "Add channel" })).toBeVisible();
});

test("RT-BETA-REC-02: a pairing failure retains sender input", async ({ page }) => {
  await page.goto(`${BASE}/#/connections?tab=channels`);
  await page.getByRole("button", { name: "Add channel", exact: true }).click();
  await page.getByRole("button", { name: /Webhooks/ }).click();
  await page.getByLabel("Allowed senders", { exact: true }).fill("beta-owner");
  await page.route("**/api/channels/pairings", r => r.fulfill(failed));
  await page.getByRole("button", { name: "Pair", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText("Check the profile before pairing again");
  await expect(page.getByLabel("Allowed senders", { exact: true })).toHaveValue("beta-owner");
  await capture(page, `${SHOTS}/pairing-draft.png`);
});

test("RT-BETA-REC-03: Design history read can be retried", async ({ page }) => {
  await page.route("**/api/images", r => r.fulfill(failed));
  await page.goto(`${BASE}/#/design`);
  await expect(page.getByRole("alert").filter({ hasText: "Retry Design" })).toContainText("Image history could not be read");
  await capture(page, `${SHOTS}/design-history.png`);
  await page.unroute("**/api/images");
  await page.getByRole("button", { name: "Retry Design", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry Design", exact: true })).toHaveCount(0);
});

test("RT-BETA-REC-04: Design names unavailable models and retries", async ({ page }) => {
  await page.route("**/api/models", r => r.fulfill(failed));
  await page.goto(`${BASE}/#/design`);
  await expect(page.getByRole("alert").filter({ hasText: "Retry Design" })).toContainText("Image models could not be read");
  await capture(page, `${SHOTS}/design-models.png`);
  await page.unroute("**/api/models");
  await page.getByRole("button", { name: "Retry Design", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry Design", exact: true })).toHaveCount(0);
});
