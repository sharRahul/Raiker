/** Read-only whole-product review; optional provider reads are real host reads. */
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { VISUAL_DESTINATIONS, horizontalBleed, settled } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const stage = process.env.RAIKER_SHARED_UI_STAGE ?? "after";
for (const size of [{ width: 1440, height: 900, theme: "light" }, { width: 1280, height: 800, theme: "dark" }] as const) {
  test(`RT-SHARED-UI-${size.theme}: every page and nested model/settings source at ${size.width}`, async ({ page }) => {
    test.setTimeout(900_000);
    await page.setViewportSize(size);
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await signInAsOwner(page, BASE);
    await page.evaluate(theme => {
      localStorage.setItem("raiker.theme", theme);
      document.documentElement.dataset.theme = theme;
    }, size.theme);
    const observations: Array<Record<string, unknown>> = [];
    const root = resolve(import.meta.dirname, `../../output/playwright/2026-11-06-shared-ui/${stage}/${size.theme}`);
    mkdirSync(root, { recursive: true });
    for (const { route, name } of VISUAL_DESTINATIONS) {
      await test.step(route, async () => {
        await page.goto(`${BASE}/#/${route}`);
        const main = page.locator("main#main");
        await expect(main).toBeVisible({ timeout: 30_000 });
        await settled(page, { timeout: 30_000 });
        await expect(page.locator("html")).toHaveAttribute("data-theme", size.theme);
        const dialog = page.getByRole("dialog");
        if (await dialog.count()) {
          await expect(dialog).toBeVisible();
          expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 2)).toBe(true);
          await captureElement(dialog, `${root}/${name}.png`);
        } else await capture(page, `${root}/${name}.png`);
        const bleed = await horizontalBleed(page);
        expect.soft(bleed, route).toEqual([]);
        const panelLinks = await page.getByRole("tab", { selected: true }).evaluateAll(tabs => tabs.map(tab => {
          const id = tab.getAttribute("aria-controls");
          return { name: tab.textContent?.trim(), id, exists: !id || document.getElementById(id) !== null };
        }));
        // Older hubs may carry their own semantics; the new nested model sections
        // must resolve their tab's actual controlled element.
        if (stage === "after") expect(panelLinks.every(link => link.exists)).toBe(true);
        observations.push({ route, actual_route: new URL(page.url()).hash, bleed, panelLinks });
        writeFileSync(`${root}/observations.json`, JSON.stringify(observations, null, 2));
      });
    }
    expect(errors).toEqual([]);
    expect(observations).toHaveLength(VISUAL_DESTINATIONS.length);
  });
}


test("RT-SHARED-UI-dialog: short window scrolls form content and keeps Close/focus reachable", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1280, height: 320 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=security`);
  const row = page.locator(".setting-row").filter({ has: page.getByRole("heading", { name: "Password", exact: true }) });
  const change = row.getByRole("button", { name: "Change", exact: true });
  await change.click();
  const dialog = page.getByRole("dialog", { name: "Change password", exact: true });
  await expect(dialog).toBeVisible();
  const close = dialog.getByRole("button", { name: "Close", exact: true });
  const content = dialog.locator(".form-body");
  expect(await content.evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true);
  await content.evaluate(element => { element.scrollTop = element.scrollHeight; });
  await expect(close).toBeInViewport();
  const bounds = await dialog.boundingBox();
  expect(bounds!.y).toBeGreaterThanOrEqual(0);
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(320);
  const root = resolve(import.meta.dirname, "../../output/playwright/2026-11-06-shared-ui/after");
  await captureElement(dialog, `${root}/password-short-window.png`);
  await close.focus();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(change).toBeFocused();
});
