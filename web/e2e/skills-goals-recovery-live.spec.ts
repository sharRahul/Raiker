/** QUI-G06: real host with explicit response-failure injection; no provider needed. */
import { expect, test } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { capture } from "./capture";
test.setTimeout(120_000);
const failed = { status: 503, json: { detail: { reason_code: "injected_failure" } } };
test.beforeEach(async ({ page }) => { await signInAsOwner(page, BASE); });

test("RT-RECOVERY-01: Skills read recovers against the host", async ({ page }) => {
  await page.route("**/api/skills", r => r.request().method() === "GET" ? r.fulfill(failed) : r.continue());
  await page.goto(`${BASE}/#/connections?tab=advanced&kind=skills`);
  await expect(page.getByRole("alert").filter({ hasText: "Skills could not be read" })).toContainText("HTTP 503");
  await capture(page, "../../output/playwright/2026-11-09-recovery/skills-read.png");
  await page.unroute("**/api/skills");
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByText("Skills could not be read", { exact: false })).toHaveCount(0);
});

test("RT-RECOVERY-02: an uncertain skill build keeps the draft and check-first advice", async ({ page }) => {
  await page.goto(`${BASE}/#/connections?tab=advanced&kind=skills`);
  await page.getByRole("button", { name: "Add a skill", exact: true }).click();
  await page.getByRole("button", { name: /Write one here/ }).click();
  await page.getByLabel("Name", { exact: true }).fill("recovery-draft");
  await page.getByLabel("Description — what it does, and when it applies").fill("Draft retained after a lost response.");
  await page.getByLabel("Instructions", { exact: true }).fill("Keep these instructions.");
  await page.route("**/api/skills/build", r => r.fulfill(failed));
  await page.getByRole("button", { name: "Build and install", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("check the list before building again");
  await expect(page.getByLabel("Instructions", { exact: true })).toHaveValue("Keep these instructions.");
  await capture(page, "../../output/playwright/2026-11-09-recovery/skill-draft.png");
});

test("RT-RECOVERY-03: Goals read fails visibly", async ({ page }) => {
  await page.route("**/api/goals", r => r.fulfill(failed));
  await page.goto(`${BASE}/#/work?tab=goals`);
  await expect(page.getByText(/Goals could not be read/)).toContainText("Reopen Goals");
  await capture(page, "../../output/playwright/2026-11-09-recovery/goals-read.png");
});
