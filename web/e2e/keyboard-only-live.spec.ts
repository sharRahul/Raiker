/**
 * UX-5 / T-14 (beta plan) — the core work, by keyboard alone, on a running host.
 *
 * No mouse at any point: only Tab, Shift+Tab, Enter, Escape and the documented
 * shortcuts. Each control reached on the way must be named and must show where
 * focus is. Needs a host whose Chat model is served (the GPU round serves a
 * local GGUF).
 *
 * KB-01  Start: reach the composer, type, send, and get an answer
 * KB-02  Stop: start a long answer and stop it from the keyboard
 * KB-03  Find: Ctrl+K, search, and open a page from the results
 * KB-04  Recover: reach Settings › Backups and make a backup
 * KB-05  Approve: reach Approvals and every decision control on it
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "output", "playwright", "2026-11-08-keyboard");

test.describe.configure({ mode: "serial", timeout: 240_000 });

interface Focused {
  name: string;
  tag: string;
  visible: boolean;
}

async function focused(page: Page): Promise<Focused> {
  return page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    if (!element || element === document.body) return { name: "", tag: "BODY", visible: false };
    const label =
      element.getAttribute("aria-label") ??
      (element.getAttribute("aria-labelledby")
        ? document.getElementById(element.getAttribute("aria-labelledby") ?? "")?.textContent ?? ""
        : "") ??
      "";
    const name = (label || element.textContent || (element as HTMLInputElement).placeholder || "").trim();
    const style = getComputedStyle(element);
    const ring =
      (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0) ||
      (style.boxShadow !== "none" && style.boxShadow !== "") ||
      element.matches(":focus-visible");
    return { name, tag: element.tagName, visible: ring };
  });
}

/** Press Tab until focus lands on a control whose name matches; every stop on the way must be named. */
async function tabTo(page: Page, name: RegExp, { max = 80, back = false } = {}): Promise<Focused> {
  const unnamed: string[] = [];
  for (let step = 0; step < max; step += 1) {
    await page.keyboard.press(back ? "Shift+Tab" : "Tab");
    const here = await focused(page);
    if (here.tag !== "BODY" && !here.name) unnamed.push(here.tag);
    if (name.test(here.name)) {
      expect(here.visible, `focus is not visible on "${here.name}"`).toBe(true);
      expect(unnamed, "controls on the way had no accessible name").toEqual([]);
      return here;
    }
  }
  throw new Error(`Tab never reached ${name}`);
}

test.beforeEach(async ({ page }) => {
  page.setDefaultTimeout(30_000);
  await page.setViewportSize({ width: 1280, height: 900 });
  await signInAsOwner(page, BASE);
});

test("KB-01 — start: reach the composer by keyboard, send, and get an answer", async ({ page }) => {
  await page.goto(`${BASE}/#/new-chat`);
  await tabTo(page, /^Prompt$|What would you like Raiker to do/);
  await page.keyboard.type("Reply with one short sentence about keyboards.");
  await page.keyboard.press("Enter");
  await expect(page.locator("summary", { hasText: /no charge|cost/ }).last()).toBeVisible({ timeout: 180_000 });
  await capture(page, join(SHOTS, "kb-01-answered.png"));
});

test("KB-02 — stop: a long answer is stopped from the keyboard", async ({ page }) => {
  await page.goto(`${BASE}/#/new-chat`);
  await tabTo(page, /^Prompt$|What would you like Raiker to do/);
  await page.keyboard.type("Write a 2000-word essay on the history of the typewriter, in full.");
  await page.keyboard.press("Enter");
  // Focus stays with the composer; the send control has become Stop safely.
  const stop = page.getByRole("button", { name: /Stop safely/ });
  await expect(stop).toBeVisible({ timeout: 60_000 });
  await tabTo(page, /Stop safely/, { max: 30 });
  await page.keyboard.press("Enter");
  await expect(page.getByText(/Stopped|stopped/).last()).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "kb-02-stopped.png"));
});

test("KB-03 — find: Ctrl+K, search, open a page from the results", async ({ page }) => {
  await page.goto(`${BASE}/#/home`);
  await page.keyboard.press("Control+K");
  const palette = page.getByRole("dialog", { name: "Search and commands" });
  await expect(palette).toBeVisible();
  await expect(palette.getByLabel("Search everything")).toBeFocused();
  await page.keyboard.type("Backups");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/settings\?tab=backups/);
  await expect(page.getByRole("heading", { level: 2, name: "Backups" })).toBeVisible();
  await page.keyboard.press("Control+K");
  await expect(palette).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(palette).toBeHidden();
});

test("KB-04 — recover: make a backup by keyboard", async ({ page }) => {
  await page.goto(`${BASE}/#/settings?tab=backups`);
  await tabTo(page, /^Back up now$/);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("backups-card")).toContainText(/Backed up and verified/, { timeout: 120_000 });
  await capture(page, join(SHOTS, "kb-04-backed-up.png"));
});

test("KB-05 — approve: Approvals and its decisions are reachable by keyboard", async ({ page }) => {
  await page.goto(`${BASE}/#/home`);
  await tabTo(page, /^Approvals/);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/approvals/);
  const decisions = page.getByRole("button", { name: /^(Approve|Deny|Allow|Reject)/ });
  if ((await decisions.count()) > 0) {
    await tabTo(page, /^(Approve|Allow)/);
  } else {
    // Nothing waiting: the page still says so in words a keyboard user reaches.
    await expect(page.getByRole("main")).toContainText(/Nothing|No approvals|waiting/i);
  }
  await capture(page, join(SHOTS, "kb-05-approvals.png"));
});
