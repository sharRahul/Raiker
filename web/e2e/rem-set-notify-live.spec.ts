/**
 * REM-SET-NOTIFY against a running `raiker-web` — two switches that say what
 * they reach, and the record they sit on.
 *
 * The page offered *In-app popups* and *Desktop alerts* under a heading reading
 * **Alerts**, and neither said what it governed. The first decided a banner
 * strip that was mounted on the MCP page and nowhere else, so an account-wide
 * preference decided whether a notice appeared on one destination the owner may
 * never open. The second's own sentence claimed it covered "approvals waiting
 * on you", which is narrower than what it does.
 *
 * Prerequisite: `raiker-web --workspace <ws> --port 8765 --no-browser`.
 * No model is needed — nothing here sends a turn.
 */
import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(
  import.meta.dirname,
  "..",
  "..",
  "docs",
  "screenshots",
  "2026-09-15-task-history",
);

test("notification settings name what each switch reaches", async ({ page }) => {
  test.setTimeout(180_000);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=notification`);

  const rail = page.getByRole("navigation", { name: "Settings sections" });
  await expect(rail).toBeVisible({ timeout: 30_000 });
  await rail.getByRole("button", { name: "Notifications" }).click();
  await expect(page.getByRole("heading", { name: "Notifications", level: 2 })).toBeVisible({
    timeout: 30_000,
  });

  // Each switch is named for what it reaches.
  await expect(page.getByLabel("Show unread notices inside Raiker")).toBeVisible();
  await expect(page.getByLabel("Alert me outside Raiker")).toBeVisible();
  // The heading that called both of them "alerts" and said nothing else is gone,
  // and so is the sentence that understated the desktop switch's scope.
  await expect(page.getByText("cover approvals waiting on you")).toHaveCount(0);

  // Muting is not deciding — said on the page, not only in the guide.
  await expect(
    page.getByText(/an approval nobody is alerted about still waits for you/i),
  ).toBeVisible();

  // The record survives both switches being off, and the page says where it is.
  const record = page.getByRole("link", { name: "Open notifications" });
  await expect(record).toBeVisible();
  expect(await record.getAttribute("href")).toBe("#/observe?tab=notifications");

  await capture(page, join(SHOTS, "settings-notifications.png"));
  expect(consoleErrors).toEqual([]);
});

test("a docked notice clears by being read", async ({ page }) => {
  // A docked notice nothing dismisses is a permanent obstruction — a worse
  // defect than the banner nobody could see. Opening it marks it read through
  // the same route the bell's Mark all read uses, so the strip, the bell's
  // count and the record cannot disagree.
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/home`);

  const strip = page.getByRole("region", { name: "Notifications" });
  const visible = await strip.isVisible().catch(() => false);
  test.skip(!visible, "This workspace has no unread notice to read, so there is nothing to clear.");

  const notice = strip.getByRole("button").first();
  const title = ((await notice.textContent()) ?? "").trim();
  await notice.click();
  // The same notice does not come back: the poll that follows the mark reads it
  // as read, which is what it now is.
  await expect(strip.getByRole("button", { name: title })).toHaveCount(0, { timeout: 30_000 });
});

test("Storage is not a Settings destination, by any route", async ({ page }) => {
  // REM-SET-STORAGE — `Storage.svelte` presented record counts as "Local usage"
  // and claimed everything stays on one machine. Neither establishes storage
  // bytes nor global privacy, and the module was unreachable: not in the rail,
  // not imported, not routed. It is deleted; this is the check that nothing was
  // quietly reaching it.
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings`);
  await expect(page.getByRole("heading", { name: "Settings", exact: true, level: 2 })).toBeVisible({
    timeout: 30_000,
  });
  const rail = page.getByRole("navigation", { name: "Settings sections" });
  await expect(rail.getByRole("button", { name: "Storage" })).toHaveCount(0);
  await page.goto(`${BASE}/#/settings?tab=storage`);
  // An unknown section falls back to the first one rather than rendering blank.
  await expect(page.getByRole("heading", { name: "Settings", exact: true, level: 2 })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("Everything stays on this machine")).toHaveCount(0);
});
