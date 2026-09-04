import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { signInAsOwner } from "./hosted-provider";

/**
 * BUG-208 slice A: the guide is reachable from inside the product.
 *
 * Before this, `docs/guide/` could only be read from a repository checkout, so
 * a page header explaining what a project *is* had nowhere to move to. This
 * asserts the destination exists — from the sidebar, and from a deep link — and
 * that a page renders as Markdown rather than as its source.
 */

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");

test("the guide opens from the sidebar and from a deep link", async ({ page }) => {
  test.setTimeout(300_000);
  const consoleErrors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });

  // BUG-248 — the shared sign-in, which finishes the wizard from whichever of
  // its five stages a used workspace resumes on. The copy this replaced clicked
  // "Skip for now", a control that no longer exists anywhere in the app, and
  // then assumed the remaining stages came in a fixed order.
  await signInAsOwner(page, BASE);

  // Reachable the way an owner would reach it: a sidebar destination.
  await page.getByRole("link", { name: "Guide" }).click();
  await expect(page.getByRole("region", { name: "Guide" })).toBeVisible({ timeout: 60_000 });

  const sections = page.locator(".guide-sections button");
  await expect(sections.first()).toBeVisible({ timeout: 60_000 });
  const titles = await sections.locator("strong").allTextContents();
  console.log(`GUIDE SECTIONS (${titles.length}): ${titles.join(" | ")}`);
  expect(titles.length).toBeGreaterThanOrEqual(7);

  // Rendered, not raw: a heading element rather than a line beginning with "#".
  const page1 = page.locator(".guide-page");
  await expect(page1.locator("h1, h2").first()).toBeVisible({ timeout: 60_000 });
  const body = await page1.innerText();
  expect(body).not.toMatch(/^\s*#\s/m);
  await capture(page, join(SHOTS, "guide-surface.png"));

  // A deep link opens the section it names, which is what a contextual
  // "Learn more" from another surface will rely on.
  await page.goto(`${BASE}/#/guide?section=troubleshooting`);
  await expect(page.locator(".guide-sections button.active strong")).toHaveText(
    /Troubleshooting/i,
    { timeout: 60_000 },
  );
  console.log(`DEEP LINK OK · CONSOLE ERRORS: ${consoleErrors.length}`);
  expect(consoleErrors).toEqual([]);
});
