import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Composer-bugs-review-password-1!";

test.describe.configure({ mode: "serial" });
let page: Page;

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 20_000 });
  const confirm = page.getByLabel("Confirm password");
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 20_000 });
});

test.afterAll(async () => await page?.close());

test("refined surfaces read correctly in both themes", async () => {
  test.setTimeout(90_000);
  for (const theme of ["light", "dark"] as const) {
    await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
    await page.goto(`${BASE}/#/workbench`);
    await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible();
    await page.waitForTimeout(250);
    await capture(page, join(SHOTS, `133-visual-refresh-workbench-${theme}.png`));

    await page.goto(`${BASE}/#/models?tab=pricing`);
    await expect(page.getByRole("heading", { name: "Pricing" })).toBeVisible();
    await page.waitForTimeout(250);
    await capture(page, join(SHOTS, `134-visual-refresh-models-${theme}.png`));
  }
});
