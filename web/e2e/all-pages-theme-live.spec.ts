import { expect, test } from "@playwright/test";
import { DESTINATIONS, hubReachability } from "./destinations";
import { signInAsOwner } from "./hosted-provider";

// The list is derived from the app's own nav registry rather than copied here.
// This file's copy had drifted: it swept two routes that no longer exist
// (Channels moved to Messaging, and `observe?tab=diagnostics` is an alias onto
// Overview) and missed twenty that do — Design, Messaging, the Guide, all six
// Models tabs and all ten Settings sections were never checked in either theme.
// `destinations.ts` says why that keeps happening and what stops it.
const routes = DESTINATIONS.map((destination) => destination.route);


test("every application page renders in explicit light and dark themes", async ({ page }) => {
  test.setTimeout(180_000);
  const hub = hubReachability(page);
  const errors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(error.message));

  await signInAsOwner(page, "http://127.0.0.1:8765");
  await expect(page.locator("main#main")).toBeVisible({ timeout: 15_000 });

  const observed = new Map<string, { light: string; dark: string }>();
  for (const theme of ["light", "dark"] as const) {
    await page.evaluate((choice) => {
      localStorage.setItem("raiker.theme", choice);
      document.documentElement.dataset.theme = choice;
    }, theme);
    for (const route of routes) {
      await page.goto(`http://127.0.0.1:8765/#/${route}`);
      await expect(page.locator("main#main")).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      const palette = await page.evaluate(() => {
        const style = getComputedStyle(document.documentElement);
        return `${style.colorScheme}|${style.getPropertyValue("--bg").trim()}|${style.getPropertyValue("--surface").trim()}|${style.getPropertyValue("--text-1").trim()}`;
      });
      expect(palette.startsWith(`${theme}|`)).toBe(true);
      const previous = observed.get(route) ?? { light: "", dark: "" };
      previous[theme] = palette;
      observed.set(route, previous);
    }
  }

  for (const route of routes) expect(observed.get(route)?.light).not.toBe(observed.get(route)?.dark);
  expect(hub.filter(errors)).toEqual([]);
});
