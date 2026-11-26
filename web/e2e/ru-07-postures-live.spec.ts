/**
 * RU-07 — the three postures on Permissions, against a running host on a fresh
 * workspace (no model or key needed):
 *
 *   raiker-web --workspace <ws> --port 8765 --no-browser
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md): RT-POSTURE-01, RT-POSTURE-02.
 */
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { capturePath } from "./capture";
import { dismissFirstRunModelSetup, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "docs", "plans", "screenshots", "working");

test("RT-POSTURE-01/02 — postures read, apply Read-only, and return to Ask first", async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signInAsOwner(page, BASE);
  await dismissFirstRunModelSetup(page).catch(() => undefined);
  await page.goto(`${BASE}/#/capabilities`);
  const panel = page.getByTestId("postures");
  await expect(panel).toBeVisible({ timeout: 60_000 });
  // A rerun may find the posture a failed run left; start from Ask first.
  if (!(await panel.textContent())?.includes("Now: Ask first.")) {
    await panel.getByRole("radio", { name: /^Ask first/ }).check();
    await panel.getByRole("button", { name: "Apply" }).click();
    await expect(panel).toContainText("Now: Ask first.", { timeout: 60_000 });
  }

  // RT-POSTURE-01 — a fresh workspace has no enforced sandbox, so that posture is closed.
  const sandboxNote = panel.getByText(/stays on Ask first/);
  const sandboxRadio = panel.getByRole("radio", { name: /Work in the sandbox/ });
  const readiness = await (await page.request.get(`${BASE}/api/command-sandbox`)).json();
  if (readiness.enforced !== true) await expect(sandboxRadio).toBeDisabled();
  if (await sandboxNote.isVisible()) await expect(sandboxRadio).toBeDisabled();
  await page.screenshot({ path: capturePath(join(SHOTS, "ru-07-postures.png")) });

  // RT-POSTURE-02 — Read-only applies through the mode routes, then Ask first undoes it.
  await panel.getByRole("radio", { name: /Read-only/ }).check();
  await expect(panel).toContainText(/This changes \d+ permissions?/);
  await panel.getByRole("button", { name: "Apply" }).click();
  await expect(panel).toContainText("Now: Read-only.", { timeout: 60_000 });
  await page.screenshot({ path: capturePath(join(SHOTS, "ru-07-read-only.png")) });
  await panel.getByRole("radio", { name: /^Ask first/ }).check();
  await panel.getByRole("button", { name: "Apply" }).click();
  await expect(panel).toContainText("Now: Ask first.", { timeout: 60_000 });
});
