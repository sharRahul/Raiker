/**
 * The 2026-10-05 (third) round: quiet hours (DEC-21a), the notice dock on work
 * surfaces (BUG-317/320), damaged search indexes on the attention list
 * (BUG-322, DEC-24 step 6) and the routine doctor and run limit (DEC-12 steps 6
 * and 8), driven against a running `raiker-web`.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, served
 * with `RAIKER_LIVE_WORKSPACE` pointing at it. The harness
 * (`scripts/live_quiet_hours_harness.py`) files starting states through the
 * store — every notice it writes is decided by the owner's saved policy, as a
 * real one is. Anthropic is entered through the Connect dialog from
 * `RAIKER_LIVE_ANTHROPIC_KEY` and never written anywhere.
 */
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { horizontalBleed, settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_MODEL, LIVE_BASE, sendTurn, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-05-quiet-hours-round");
const REPO = join(import.meta.dirname, "..", "..");
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";

test.describe.configure({ mode: "serial" });
// The account's clock for this round: the browser proposes its zone to the
// server, so quiet hours are read in UTC like the times `utcClock` writes.
test.use({ timezoneId: "UTC" });

function watchFailures(page: Page): { failures: string[]; consoleErrors: string[] } {
  const failures: string[] = [];
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 500) {
      failures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  return { failures, consoleErrors };
}

function harness(...args: string[]): Record<string, unknown> {
  const out = execFileSync(PYTHON, [join(REPO, "scripts", "live_quiet_hours_harness.py"), WORKSPACE, ...args], {
    encoding: "utf-8",
  });
  return JSON.parse(out.trim()) as Record<string, unknown>;
}

/** `HH:MM` in UTC, `minutes` from now. */
function utcClock(minutes: number): string {
  const at = new Date(Date.now() + minutes * 60_000);
  return `${String(at.getUTCHours()).padStart(2, "0")}:${String(at.getUTCMinutes()).padStart(2, "0")}`;
}

/** Set quiet hours through Settings → Notifications and save, the way an owner does. */
async function setQuietHours(page: Page, start: string, end: string): Promise<void> {
  await page.goto(`${BASE}/#/settings?tab=notification`);
  await settled(page);
  const enabled = page.getByLabel("Use quiet hours");
  if (!(await enabled.isChecked())) await enabled.check();
  await page.getByLabel("Quiet hours start").fill(start);
  await page.getByLabel("Quiet hours end").fill(end);
  await page.getByLabel("Quiet hours end").blur();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 15_000 });
}

test("a real Anthropic answer, with nothing docked over the conversation", async ({ page }) => {
  test.setTimeout(300_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await useAnthropic(page);
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  await chooseModelForTurn(page, new RegExp(ANTHROPIC_MODEL.includes("haiku") ? "Haiku" : ".", "i"));
  await sendTurn(page, "Reply with exactly these words and nothing else: quiet round answered");
  await expect(page.getByText(/quiet round answered/i)).toHaveCount(2, { timeout: 120_000 });
  await capture(page, join(SHOTS, "01-chat-real-answer.png"));
  expect(seen.failures).toEqual([]);
});

test("BUG-320: on Chat a notice shows, then folds into the bell instead of covering the prompt", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  harness("notice", "task_finished");
  const dock = page.getByRole("region", { name: "Notifications" });
  await expect(dock).toBeVisible({ timeout: 45_000 });
  await capture(page, join(SHOTS, "02-chat-notice-shown.png"));
  await expect(dock).toBeHidden({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: /Notifications \(\d+ unread\)/ })).toBeVisible();
  await capture(page, join(SHOTS, "03-chat-notice-folded-into-bell.png"));
  // Elsewhere — not Tasks, which answers a finished-task notice itself and
  // marks it read (BUG-309) — the dock stays until read.
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  await expect(dock).toBeVisible({ timeout: 45_000 });
  await page.waitForTimeout(8_000);
  await expect(dock).toBeVisible();
  await dock.getByRole("button", { name: /^Dismiss/ }).click();
  expect(seen.failures).toEqual([]);
});

test("quiet hours: off by default, set by the owner, and in force on the server's clock", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=notification`);
  await settled(page);
  await expect(page.getByLabel("Use quiet hours")).not.toBeChecked();
  await setQuietHours(page, utcClock(-60), utcClock(60));
  await expect(page.getByTestId("quiet-now")).toContainText(/Quiet now, until \d\d:\d\d/, { timeout: 45_000 });
  await expect(page.getByLabel("Let security alerts through inside Raiker")).not.toBeChecked();
  await expect(page.getByLabel("Let security alerts through outside Raiker")).not.toBeChecked();
  await capture(page, join(SHOTS, "04-settings-quiet-hours-on.png"), page.locator("section.card").filter({ hasText: "Quiet hours" }).first());

  // The test notice takes the real path and is held like any other.
  await page.getByRole("button", { name: "Send a test notice" }).click();
  await expect(page.getByTestId("test-notice-result")).toContainText(/Sent and held: quiet hours are on until \d\d:\d\d/);
  await page.waitForTimeout(3_000);
  await expect(page.getByRole("region", { name: "Notifications" })).toBeHidden();
  await capture(page, join(SHOTS, "05-test-notice-held.png"));
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("quiet hours hold an approval notice and a routine failure; the record keeps both", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  const paused = harness("notice", "task_paused") as { in_app_presentation: string };
  const approval = harness("notice", "approval_pending") as { in_app_presentation: string };
  expect(paused.in_app_presentation).toBe("quiet_hours");
  expect(approval.in_app_presentation).toBe("quiet_hours");
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  await page.waitForTimeout(3_000);
  await expect(page.getByRole("region", { name: "Notifications" })).toBeHidden();
  await expect(page.getByRole("button", { name: /Notifications \(\d+ unread\)/ })).toBeVisible();
  await page.goto(`${BASE}/#/observe?tab=notifications`);
  await settled(page);
  await expect(page.getByText("A routine was paused").first()).toBeVisible();
  await capture(page, join(SHOTS, "06-record-keeps-held-notices.png"));
  expect(seen.failures).toEqual([]);
});

test("a critical exception lets containment through inside Raiker only, and only when chosen", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  const before = harness("notice", "capability_contained") as Record<string, string>;
  expect(before.in_app_presentation).toBe("quiet_hours");
  await page.goto(`${BASE}/#/settings?tab=notification`);
  await settled(page);
  await page.getByLabel("Let security alerts through inside Raiker").check();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 15_000 });
  const after = harness("notice", "capability_contained") as Record<string, string>;
  expect(after.in_app_presentation).toBe("critical_exception");
  expect(after.desktop_presentation).toBe("quiet_hours");
  // A routine failure is not a security event: still held.
  expect((harness("notice", "task_paused") as Record<string, string>).in_app_presentation).toBe("quiet_hours");
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  const dock = page.getByRole("region", { name: "Notifications" });
  await expect(dock).toContainText("Web access contained", { timeout: 45_000 });
  await capture(page, join(SHOTS, "07-critical-exception-through.png"));
  await dock.getByRole("button", { name: /^Dismiss/ }).click();
  expect(seen.failures).toEqual([]);
});

test("when quiet hours end: one summary of what still wants the owner, acknowledged once", async ({ page, context }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  // An interval that ended an hour ago; three notices written inside it.
  await setQuietHours(page, utcClock(-180), utcClock(-60));
  const held = harness("held") as { notices: { in_app_presentation: string }[] };
  expect(held.notices.map((row) => row.in_app_presentation)).toEqual(["quiet_hours", "quiet_hours", "quiet_hours"]);
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  const summary = page.getByTestId("quiet-summary");
  await expect(summary).toBeVisible({ timeout: 45_000 });
  await expect(summary).toContainText("While quiet hours were on");
  await expect(summary).toContainText("A routine was paused");
  // The approval it was about is no longer pending, so it is not listed.
  await expect(summary).not.toContainText("Approval needed");
  await capture(page, join(SHOTS, "08-quiet-hours-summary.png"));
  await summary.getByRole("button", { name: "Later" }).click();
  await expect(summary).toBeHidden();
  // A second tab, and a reload, do not offer it again.
  const second = await context.newPage();
  await second.goto(`${BASE}/#/home`);
  await settled(second);
  await second.waitForTimeout(4_000);
  await expect(second.getByTestId("quiet-summary")).toBeHidden();
  await second.close();
  await page.reload();
  await settled(page);
  await page.waitForTimeout(4_000);
  await expect(page.getByTestId("quiet-summary")).toBeHidden();
  const record = harness("show-notices") as { notices: { kind: string; read: number; summarised_at: string | null }[] };
  expect(record.notices.filter((row) => row.summarised_at !== null).length).toBeGreaterThan(0);
  expect(record.notices.filter((row) => row.summarised_at !== null).every((row) => !row.read)).toBe(true);
  expect(seen.failures).toEqual([]);
});

test("a muted category is recorded and does not interrupt; decisions offer no switch", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=notification`);
  await settled(page);
  // The previous scenario left quiet hours on: wait for the saved state to
  // arrive before changing it, rather than editing the defaults it replaces.
  await expect(page.getByLabel("Use quiet hours")).toBeChecked({ timeout: 15_000 });
  await page.getByLabel("Use quiet hours").uncheck();
  await page.getByLabel("Extensions and MCP servers").uncheck();
  // Re-runnable: on a workspace where both are already saved, nothing is dirty.
  const save = page.getByRole("button", { name: "Save changes" });
  if (await save.isVisible()) {
    await save.click();
    await expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 15_000 });
  }
  const interrupts = page.locator("section.card").filter({ hasText: "What interrupts you" });
  await expect(interrupts.getByRole("checkbox")).toHaveCount(3);
  await expect(interrupts.getByLabel(/approval|decision/i)).toHaveCount(0);
  await capture(page, join(SHOTS, "09-interrupt-categories.png"), page.locator("section.card").filter({ hasText: "What interrupts you" }));
  const muted = harness("notice", "mcp_tools_held") as Record<string, string>;
  expect(muted.in_app_presentation).toBe("muted");
  const shown = harness("notice", "task_finished") as Record<string, string>;
  expect(shown.in_app_presentation).toBe("interrupt");
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  const dock = page.getByRole("region", { name: "Notifications" });
  await expect(dock).toContainText("Background task finished", { timeout: 45_000 });
  await expect(dock).not.toContainText("An MCP server changed its tools");
  await dock.getByRole("button", { name: /^Dismiss/ }).click();
  expect(seen.failures).toEqual([]);
});

test("BUG-322: a damaged search index is on the attention list and its link opens the repair", async ({ page }) => {
  // The host checks on its first tick and every five minutes after.
  test.setTimeout(480_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  execFileSync(PYTHON, [join(REPO, "scripts", "live_readiness_harness.py"), WORKSPACE, "damage-index"], { encoding: "utf-8" });
  await page.goto(`${BASE}/#/observe?tab=overview`);
  await settled(page);
  const attention = page.locator("section.attention");
  await expect(async () => {
    await page.reload();
    await settled(page);
    await expect(attention).toContainText("Conversation search is damaged", { timeout: 5_000 });
  }).toPass({ timeout: 420_000, intervals: [15_000] });
  await capture(page, join(SHOTS, "10-attention-damaged-index.png"), attention);
  await attention.getByRole("link", { name: "Rebuild it" }).click();
  await expect(page.locator("details#runtime-health-detail")).toHaveAttribute("open", "");
  await expect(page.getByTestId("damaged-text-indexes")).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "11-repair-opened-in-place.png"));
  await page.getByRole("button", { name: "Rebuild search indexes" }).click();
  await expect(page.getByText(/every search index passes its check/)).toBeVisible({ timeout: 60_000 });
  await page.goto(`${BASE}/#/observe?tab=overview`);
  await settled(page);
  await expect(attention).not.toContainText("Conversation search is damaged");
  // And the owner was told in words — once per time it was found damaged, not
  // once per five-minute check.
  await page.goto(`${BASE}/#/observe?tab=notifications`);
  await settled(page);
  await expect(page.getByText("Conversation search needs repairing").first()).toBeVisible();
  expect(seen.failures).toEqual([]);
});

test("DEC-24 step 6: damaged vectors are named and removed, the memories untouched", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  const damaged = harness("damage-vectors") as { damaged_vectors: string[] };
  expect(damaged.damaged_vectors.length).toBe(2);
  await page.goto(`${BASE}/#/observe?tab=overview&repair=indexes`);
  await settled(page);
  const notice = page.getByTestId("damaged-vectors");
  await expect(notice).toContainText("2 stored vectors could not be read", { timeout: 30_000 });
  await capture(page, join(SHOTS, "12-damaged-vectors-named.png"), page.locator("section.card").filter({ hasText: "Memory integrity" }));
  await page.getByRole("button", { name: "Remove damaged vectors" }).click();
  await expect(page.getByText(/Removed 2 damaged vectors/)).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "13-damaged-vectors-removed.png"), page.locator("section.card").filter({ hasText: "Memory integrity" }));
  // The memories are untouched, and now waiting to be indexed again.
  const after = harness("memories") as { texts: string[]; waiting_to_be_indexed: number };
  expect(after.texts).toContain("The release train leaves on Thursdays.");
  expect(after.texts).toContain("Staging is rebuilt every Monday.");
  expect(after.waiting_to_be_indexed).toBeGreaterThanOrEqual(2);
  expect(seen.failures).toEqual([]);
});

test("DEC-12 steps 6 and 8: Will it run? and a routine's own run limit", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  harness("routine");
  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  const card = page.locator("article.task").filter({ hasText: "Morning dependency digest" }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  await card.getByRole("button", { name: "Will it run?" }).click();
  const panel = card.getByTestId("routine-check");
  await expect(panel).toContainText("The scheduler");
  await expect(panel).toContainText("Its model");
  await expect(panel).toContainText(/Each run is stopped after 60 minutes/);
  await capture(page, join(SHOTS, "14-routine-doctor.png"), card);
  await panel.getByLabel("Run limit in minutes").fill("30");
  await panel.getByRole("button", { name: "Save limit" }).click();
  await expect(panel).toContainText("Each run now stops after 30 minutes.");
  await expect(panel).toContainText(/Each run is stopped after 30 minutes/, { timeout: 15_000 });
  await page.reload();
  await settled(page);
  const again = page.locator("article.task").filter({ hasText: "Morning dependency digest" }).first();
  await again.getByRole("button", { name: "Will it run?" }).click();
  await expect(again.getByLabel("Run limit in minutes")).toHaveValue("30");
  await page.setViewportSize({ width: 390, height: 844 });
  await settled(page);
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "15-routine-doctor-390.png"));
  expect(seen.failures).toEqual([]);
});

test("Settings → Notifications at 390 wide, in the dark theme, without bleeding", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark" });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=notification`);
  await settled(page);
  await page.getByLabel("Use quiet hours").check();
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "16-settings-notifications-390-dark.png"));
  await page.getByRole("button", { name: "Discard changes" }).click();
});
