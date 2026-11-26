/**
 * RU-09 — first run's *This machine* and *Posture* steps, on a workspace
 * nothing has touched (its own host, so the main live host is not used up):
 *
 *   raiker-web --workspace <fresh> --port 8767 --no-browser
 *
 * RAIKER_LIVE_FIRST_RUN_BASE names it. Live cases
 * (docs/architecture/WEB_APP_LIVE_TEST.md): RT-FIRSTRUN-01, RT-FIRSTRUN-02.
 */
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { capturePath } from "./capture";
import { OWNER_CREDENTIALS } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_FIRST_RUN_BASE ?? "http://127.0.0.1:8767";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "plans", "screenshots", "working");

test("RT-FIRSTRUN-01/02 — This machine lists what to set up; Posture is chosen and applied", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${BASE}/#/workbench`);
  const username = page.getByLabel("Username");
  await expect(username).toBeEnabled({ timeout: 60_000 });
  await username.fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(OWNER_CREDENTIALS.password);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  const title = page.locator("#setup-title");
  await expect(title).toBeVisible({ timeout: 60_000 });
  await expect(title).not.toHaveText(/Preparing/, { timeout: 30_000 });
  test.skip(!((await title.textContent()) ?? "").startsWith("Hi, I'm Raiker"), "Not a first run.");
  await page.getByLabel("Your name").fill("Rahul");
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  // RT-FIRSTRUN-01 — This machine: device checks, then what first run sets up.
  await expect(title).toHaveText(/What this computer can run/, { timeout: 30_000 });
  const facts = page.getByTestId("first-run-facts");
  for (const label of ["Command sandbox", "Search by meaning", "Backups", "Always-on host"]) {
    await expect(facts).toContainText(label, { timeout: 30_000 });
  }
  await expect(facts).toContainText("What is left stays listed on Health.");
  await facts.scrollIntoViewIfNeeded();
  await page.screenshot({ path: capturePath(join(SHOTS, "ru-09-this-machine.png")), fullPage: true });
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  await expect(title).toHaveText(/listen and answer aloud/, { timeout: 30_000 });
  await page.getByRole("radio", { name: "Not now", exact: true }).check();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(title).toHaveText("Where should I think?", { timeout: 30_000 });
  await page.getByRole("button", { name: /^Decide later/ }).click();

  // RT-FIRSTRUN-02 — Posture: Ask first chosen; Read-only applied on Continue.
  await expect(title).toHaveText("Here is how I'll work for you.", { timeout: 30_000 });
  const posture = page.getByTestId("first-run-posture");
  await expect(posture.getByRole("radio", { name: /^Ask first/ })).toBeChecked();
  await posture.getByRole("radio", { name: /^Read-only/ }).check();
  await page.screenshot({ path: capturePath(join(SHOTS, "ru-09-posture.png")), fullPage: true });
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(title).not.toHaveText("Here is how I'll work for you.", { timeout: 60_000 });

  await page.goto(`${BASE}/#/capabilities`);
  await expect(page.getByTestId("postures")).toContainText("Now: Read-only.", { timeout: 60_000 });
});
