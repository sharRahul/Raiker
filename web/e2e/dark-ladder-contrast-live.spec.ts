/** 2026-11-07 dark ladder: WCAG AA text contrast on every destination, both themes,
 * plus the surface ladder, interaction states and composer edge, against a running host.
 * Dark screenshots of every destination are kept for visual review.
 */
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { DESTINATIONS } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { capture } from "./capture";

const SHOTS = "../../output/playwright/2026-11-07-dark-ladder";
const REPORT = resolve(import.meta.dirname, "../../output/playwright/2026-11-07-dark-ladder/contrast.json");
test.describe.configure({ mode: "serial" });

async function theme(page: Page, choice: "light" | "dark") {
  await page.evaluate((value) => {
    localStorage.setItem("raiker.theme", value);
    document.documentElement.dataset.theme = value;
  }, choice);
}

async function settle(page: Page, route: string) {
  await page.goto(`${BASE}/#/${route}`);
  await expect(page.locator("main#main")).toBeVisible({ timeout: 30_000 });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(400);
}

test("RT-DARK-01: every destination meets WCAG AA text contrast in dark and light", async ({ page }) => {
  test.setTimeout(900_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const findings: Record<string, { theme: string; route: string; target: string; summary: string }[]> = { dark: [], light: [] };
  for (const choice of ["dark", "light"] as const) {
    await theme(page, choice);
    for (const { route, name } of DESTINATIONS) {
      await settle(page, route);
      const result = await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze();
      for (const violation of result.violations) {
        for (const node of violation.nodes) {
          findings[choice].push({ theme: choice, route, target: node.target.join(" "), summary: (node.failureSummary ?? "").split("\n").slice(1, 2).join(" ").trim() });
        }
      }
      if (choice === "dark") await capture(page, `${SHOTS}/${name}.png`);
    }
  }
  mkdirSync(resolve(REPORT, ".."), { recursive: true });
  writeFileSync(REPORT, JSON.stringify(findings, null, 2));
  expect(findings.dark, JSON.stringify(findings.dark.slice(0, 12), null, 2)).toEqual([]);
  expect(findings.light, JSON.stringify(findings.light.slice(0, 12), null, 2)).toEqual([]);
});

test("RT-DARK-02: the ladder, selection, hover, focus and composer edge are distinguishable", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await theme(page, "dark");
  await settle(page, "new-chat");
  const colours = await page.evaluate(() => {
    const bg = (selector: string) => getComputedStyle(document.querySelector(selector) as Element).backgroundColor;
    return {
      body: getComputedStyle(document.body).backgroundColor,
      sidebar: bg(".sidebar"),
      selected: bg(".nav-link.active"),
      composerEdge: getComputedStyle(document.querySelector(".composer-card") as Element).borderTopColor,
    };
  });
  expect(colours.sidebar).not.toBe(colours.body);
  expect(colours.selected).not.toBe(colours.sidebar);
  expect(colours.composerEdge).toBe("rgb(90, 100, 116)");
  const link = page.locator(".nav-link").filter({ hasText: "Build" }).first();
  const before = await link.evaluate((el) => getComputedStyle(el).backgroundColor);
  await link.hover();
  await expect.poll(() => link.evaluate((el) => getComputedStyle(el).backgroundColor)).not.toBe(before);
  await page.keyboard.press("Tab");
  await page.locator(".nav-link").first().focus();
  const outline = await page.locator(".nav-link").first().evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe("none");
  const send = page.getByRole("group", { name: "Message composer" }).getByRole("button", { name: "Send", exact: true });
  expect(await send.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(224, 182, 74)");
  await capture(page, `${SHOTS}/02-states-chat.png`);
});
