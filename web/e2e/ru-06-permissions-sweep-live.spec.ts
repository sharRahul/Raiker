/**
 * RU-06 — the live surface sweep: every Permissions family, opened in turn,
 * leads with its one-line summary, lists its permissions with a readable
 * label, overflows nothing at desktop or phone width, and logs no console
 * error. Against a running host (no model or key needed):
 *
 *   raiker-web --workspace <ws> --port 8765 --no-browser
 *
 * Live case (docs/architecture/WEB_APP_LIVE_TEST.md): RT-PERM-SWEEP-01.
 */
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { capturePath } from "./capture";
import { dismissFirstRunModelSetup, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "docs", "plans", "screenshots", "working", "ru-06");

const FAMILIES = [
  "Files",
  "Commands",
  "Web",
  "Messages and calendar",
  "Memory",
  "Git and GitHub",
  "Models",
  "Money",
  "Devices and home",
  "Other agents and plugins",
];

for (const width of [1440, 390]) {
  test(`RT-PERM-SWEEP-01 — every permission family at ${width}px`, async ({ page }) => {
    test.setTimeout(300_000);
    const errors: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    await page.setViewportSize({ width, height: 900 });
    await signInAsOwner(page, BASE);
    await dismissFirstRunModelSetup(page).catch(() => undefined);
    await page.goto(`${BASE}/#/capabilities`);
    const rail = page.getByRole("navigation", { name: "Permission categories" });
    await expect(rail).toBeVisible({ timeout: 60_000 });
    const present = (await rail.getByRole("button").allInnerTexts()).map((t) => t.split("\n")[0].trim());
    let visited = 0;
    for (const family of FAMILIES) {
      // A family with no permission on this runtime is not listed; it is not a failure.
      if (!present.includes(family)) continue;
      await rail.getByRole("button", { name: new RegExp(`^${family}`) }).click();
      const pane = page.locator(".category-pane");
      await expect(pane.locator(".family-summary")).toBeVisible({ timeout: 30_000 });
      await expect(pane.locator("article").first()).toBeVisible();
      for (const label of await pane.locator("article").evaluateAll((items) => items.map((i) => i.getAttribute("aria-label") ?? ""))) {
        expect(label, `${family}: a row without a label`).not.toBe("");
        expect(label, `${family}: a row named by its id`).not.toMatch(/_(runtime|execution|cap)$/);
      }
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `${family} overflows at ${width}px`).toBeLessThanOrEqual(1);
      await page.screenshot({ path: capturePath(join(SHOTS, `${width}-${family.replace(/\W+/g, "-").toLowerCase()}.png`)) });
      visited += 1;
    }
    expect(visited).toBeGreaterThanOrEqual(8);
    expect(errors, errors.join("\n")).toEqual([]);
  });
}
