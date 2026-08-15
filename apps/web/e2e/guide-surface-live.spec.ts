import { expect, test } from "@playwright/test";
import { join } from "node:path";

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
const PASSWORD = "Review-provider-matrix-1!";

test("the guide opens from the sidebar and from a deep link", async ({ page }) => {
  test.setTimeout(300_000);
  const consoleErrors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });

  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 60_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker" }).click();
  }
  for (const name of ["Skip for now", "Decide later", "Balanced", "Set up later", "Open Workbench"]) {
    const b = page.getByRole("button", { name, exact: true });
    if (await b.isVisible().catch(() => false)) await b.click();
  }

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
  await page.screenshot({ path: join(SHOTS, "guide-surface.png"), fullPage: true });

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
