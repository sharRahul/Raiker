/**
 * The 2026-10-05 (fourth) round: backups and restore (DEC-24 step 5), the
 * snapshot before an upgrade (DEC-17 step 8), settings saved from a stale page
 * (13.2 #6), notice deduplication and the record's account of each notice
 * (DEC-21), the scheduler's queue (DEC-24 step 1), a routine's tool-call limit
 * (DEC-12 step 6) and the screenshot manifest (DEC-19 step 5), driven against a
 * running `raiker-web`.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, served
 * with `RAIKER_LIVE_WORKSPACE` pointing at it. Harnesses:
 * `scripts/live_backup_harness.py` and `scripts/live_quiet_hours_harness.py`.
 * Anthropic is entered through the Connect dialog from
 * `RAIKER_LIVE_ANTHROPIC_KEY` and never written anywhere.
 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { horizontalBleed, settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_MODEL, LIVE_BASE, sendTurn, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-05-backups-round");
const REPO = join(import.meta.dirname, "..", "..");
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";

test.describe.configure({ mode: "serial" });
test.use({ timezoneId: "UTC" });

function watchFailures(page: Page): { failures: string[] } {
  const failures: string[] = [];
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 500) {
      failures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  return { failures };
}

function harness(script: string, ...args: string[]): Record<string, unknown> {
  const out = execFileSync(PYTHON, [join(REPO, "scripts", script), WORKSPACE, ...args], { encoding: "utf-8" });
  return JSON.parse(out.trim()) as Record<string, unknown>;
}

function utcClock(minutes: number): string {
  const at = new Date(Date.now() + minutes * 60_000);
  return `${String(at.getUTCHours()).padStart(2, "0")}:${String(at.getUTCMinutes()).padStart(2, "0")}`;
}

async function openNotificationSettings(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/settings?tab=notification`);
  await settled(page);
  // Wait for the saved values, not the defaults the page renders first.
  await page.waitForResponse((response) => response.url().endsWith("/api/settings")).catch(() => undefined);
  await page.waitForTimeout(1_500);
}

async function save(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Save changes" }).click();
}

test("a real Anthropic answer, so there is something to back up", async ({ page }) => {
  test.setTimeout(300_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await useAnthropic(page);
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  await chooseModelForTurn(page, new RegExp(ANTHROPIC_MODEL.includes("haiku") ? "Haiku" : ".", "i"));
  await sendTurn(page, "Reply with exactly these words and nothing else: backup round answered");
  await expect(page.getByText(/backup round answered/i)).toHaveCount(2, { timeout: 120_000 });
  await capture(page, join(SHOTS, "01-chat-real-answer.png"));
  expect(seen.failures).toEqual([]);
});

test("Back up now, verify it, and restore it to a separate folder", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=account`);
  await settled(page);
  const card = page.getByTestId("backups-card");
  await expect(card).toContainText("No backups yet.");
  await card.getByRole("button", { name: "Back up now" }).click();
  await expect(card).toContainText(/Backed up and verified — /, { timeout: 60_000 });
  await expect(card.getByTestId("backup-state").first()).toHaveText("Verified");
  await expect(card).toContainText("Not included: checkpoints, build artifacts, the audit log, folders you attached to projects");
  await capture(page, join(SHOTS, "02-account-backup-verified.png"), card);
  await card.getByRole("button", { name: "Verify" }).first().click();
  await expect(card).toContainText("Verified: it opens with this workspace's key and passes its integrity check.");
  await card.getByRole("button", { name: "Restore to a new folder" }).first().click();
  const restored = card.getByTestId("backup-restored");
  await expect(restored).toContainText("Your running workspace was not changed", { timeout: 60_000 });
  await capture(page, join(SHOTS, "03-backup-restored-separately.png"), card);
  const path = (await restored.locator("code").textContent())?.match(/--workspace "([^"]+)"/)?.[1] ?? "";
  expect(path).toContain(".raiker/restores/bkp_");
  const opened = harness("live_backup_harness.py", "restored", path) as { sessions: number; principals: number };
  expect(opened.sessions).toBeGreaterThan(0);
  expect(opened.principals).toBeGreaterThan(0);
  expect(seen.failures).toEqual([]);
});

test("a backup whose file changed is Damaged, offers no restore, and can be removed", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=account`);
  await settled(page);
  const card = page.getByTestId("backups-card");
  await card.getByRole("button", { name: "Back up now" }).click();
  await expect(card).toContainText(/Backed up and verified/, { timeout: 60_000 });
  const listing = await page.evaluate(async () => (await fetch("/api/backups", { credentials: "same-origin" })).json());
  const newest = (listing as { backups: { backup_id: string }[] }).backups[0].backup_id;
  harness("live_backup_harness.py", "tamper", newest);
  const row = card.locator("li").first();
  await row.getByRole("button", { name: "Verify" }).click();
  await expect(row.getByTestId("backup-state")).toHaveText(/^Damaged — .*checksum/);
  await expect(row.getByRole("button", { name: "Restore to a new folder" })).toBeDisabled();
  await capture(page, join(SHOTS, "04-backup-damaged-no-restore.png"), card);
  await row.getByRole("button", { name: /^Remove backup/ }).click();
  await expect(card).toContainText("Backup removed.");
});

test("an upgrade takes its own verified snapshot first", async ({ page }) => {
  test.setTimeout(120_000);
  const upgraded = harness("live_backup_harness.py", "upgrade") as { pre_migration_backups: number };
  // The harness's own open, and the running host's next request, may both see
  // the pending migration before either records it; each takes a snapshot.
  expect(upgraded.pre_migration_backups).toBeGreaterThanOrEqual(1);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=account`);
  await settled(page);
  const card = page.getByTestId("backups-card");
  const row = card.locator("li").filter({ hasText: "Before an update" }).first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await expect(row.getByTestId("backup-state")).toHaveText("Verified");
  await capture(page, join(SHOTS, "05-pre-migration-snapshot.png"), card);
});

test("settings saved from a stale page: kept where nobody else changed it, refused where somebody did", async ({ browser }) => {
  test.setTimeout(180_000);
  const context = await browser.newContext({ timezoneId: "UTC" });
  const a = await context.newPage();
  const b = await context.newPage();
  await signInAsOwner(a, BASE);
  await openNotificationSettings(a);
  await openNotificationSettings(b);
  // B turns off one kind of interrupt and saves.
  await b.getByLabel("Background work finished or paused").uncheck();
  await save(b);
  await expect(b.getByText(/All changes saved/)).toBeVisible({ timeout: 15_000 });
  // A, still holding the old page, changes a different setting.
  await a.getByLabel("Extensions and MCP servers").uncheck();
  await save(a);
  await expect(a.getByText(/All changes saved\. One setting changed elsewhere since this page opened was kept as it was\./)).toBeVisible({ timeout: 15_000 });
  await expect(a.getByLabel("Background work finished or paused")).not.toBeChecked();
  await capture(a, join(SHOTS, "06-settings-merged-from-stale-page.png"));
  // B, stale about Extensions, sets quiet hours from 21:00 — a key nobody else
  // touched — and its save keeps A's change rather than putting it back.
  await b.getByLabel("Use quiet hours").check();
  await b.getByLabel("Quiet hours start").fill("21:00");
  await save(b);
  await expect(b.getByText(/One setting changed elsewhere since this page opened was kept/)).toBeVisible({ timeout: 15_000 });
  // A, stale about quiet hours, wants them to start at 23:00: the same key,
  // changed elsewhere to something else. Refused, and A's edit is kept.
  await a.getByLabel("Use quiet hours").check();
  await a.getByLabel("Quiet hours start").fill("23:00");
  await save(a);
  await expect(a.getByRole("alert")).toContainText("also changed somewhere else", { timeout: 15_000 });
  await expect(a.getByLabel("Quiet hours start")).toHaveValue("23:00");
  await capture(a, join(SHOTS, "07-settings-conflict-refused.png"));
  await a.getByRole("button", { name: /Show the newer settings/ }).click();
  await expect(a.getByLabel("Quiet hours start")).toHaveValue("21:00");
  // Leave quiet hours off and every kind interrupting for the rest of the round.
  await a.getByLabel("Use quiet hours").uncheck();
  await a.getByLabel("Background work finished or paused").check();
  await a.getByLabel("Extensions and MCP servers").check();
  await save(a);
  await expect(a.getByText(/All changes saved/)).toBeVisible({ timeout: 15_000 });
  await context.close();
});

test("a finding raised three times is one notice, counted", async ({ page }) => {
  test.setTimeout(120_000);
  const raised = harness("live_backup_harness.py", "repeat", "3") as { distinct: number; repeat_count: number[] };
  expect(raised.distinct).toBe(1);
  expect(raised.repeat_count).toEqual([2]);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/observe?tab=notifications`);
  await settled(page);
  const row = page.locator("ul.notifications li").filter({ hasText: "Web access was refused three times" });
  await expect(row).toHaveCount(1);
  await expect(row.getByTestId("notice-repeats")).toHaveText("raised 2 more times");
  await capture(page, join(SHOTS, "08-record-repeat-counted.png"));
});

test("the record says a notice was held for quiet hours, or not shown because its kind is off", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await openNotificationSettings(page);
  const enabled = page.getByLabel("Use quiet hours");
  if (!(await enabled.isChecked())) await enabled.check();
  await page.getByLabel("Quiet hours start").fill(utcClock(-60));
  await page.getByLabel("Quiet hours end").fill(utcClock(60));
  await page.getByLabel("Extensions and MCP servers").uncheck();
  await save(page);
  await expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 15_000 });
  harness("live_quiet_hours_harness.py", "notice", "task_paused");
  await page.getByLabel("Use quiet hours").uncheck();
  await save(page);
  await expect(page.getByText(/All changes saved/)).toBeVisible({ timeout: 15_000 });
  harness("live_quiet_hours_harness.py", "notice", "mcp_tools_held");
  await page.goto(`${BASE}/#/observe?tab=notifications`);
  await settled(page);
  const held = page.locator("ul.notifications li").filter({ hasText: "A routine was paused" }).first();
  await expect(held.getByTestId("notice-presentation")).toHaveText(/^held for quiet hours until \d\d:\d\d$/);
  const muted = page.locator("ul.notifications li").filter({ hasText: "An MCP server changed its tools" }).first();
  await expect(muted.getByTestId("notice-presentation")).toHaveText("not shown — this kind is turned off in Notifications");
  await capture(page, join(SHOTS, "09-record-held-and-muted.png"));
  await openNotificationSettings(page);
  await page.getByLabel("Extensions and MCP servers").check();
  await save(page);
});

test("work due while Raiker is paused is named as waiting, not missing", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  await page.getByRole("button", { name: /^Host/ }).click();
  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByText("Paused. Scheduled work will not start until you resume.")).toBeVisible({ timeout: 15_000 });
  await page.keyboard.press("Escape");
  harness("live_backup_harness.py", "due");
  await page.goto(`${BASE}/#/observe?tab=overview`);
  await settled(page);
  const attention = page.locator("section.attention");
  await expect(attention).toContainText("1 scheduled task is waiting while Raiker is paused", { timeout: 30_000 });
  await capture(page, join(SHOTS, "10-attention-queue-waiting-paused.png"), attention);
  await page.getByRole("button", { name: /^Host/ }).click();
  await page.getByRole("button", { name: "Resume" }).click();
  await expect(page.getByText(/Resumed\./)).toBeVisible({ timeout: 15_000 });
});

test("a routine's own tool-call limit, said by Will it run? and kept", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  harness("live_quiet_hours_harness.py", "routine");
  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  const card = page.locator("article.task").filter({ hasText: "Morning dependency digest" }).first();
  await card.getByRole("button", { name: "Will it run?" }).click();
  const panel = card.getByTestId("routine-check");
  await panel.getByLabel("Tool-call limit per run").fill("40");
  await panel.getByRole("button", { name: "Save limit" }).click();
  await expect(panel).toContainText("Each run now stops after 60 minutes or 40 tool calls.");
  await expect(panel).toContainText(/Each run is stopped after 60 minutes or 40 tool calls/, { timeout: 15_000 });
  await capture(page, join(SHOTS, "11-routine-tool-limit.png"), card);
  await page.reload();
  await settled(page);
  const again = page.locator("article.task").filter({ hasText: "Morning dependency digest" }).first();
  await again.getByRole("button", { name: "Will it run?" }).click();
  await expect(again.getByLabel("Tool-call limit per run")).toHaveValue("40");
});

test("Account's backups at 390 wide in the dark theme, without bleeding", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark" });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=account`);
  await settled(page);
  await expect(page.getByTestId("backups-card")).toBeVisible();
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "12-account-backups-390-dark.png"), page.getByTestId("backups-card"));
});

test("every capture in this round says where it came from", async () => {
  const manifest = JSON.parse(readFileSync(join(SHOTS, "manifest.json"), "utf-8")) as Record<
    string,
    { commit: string; viewport: { width: number } | null; theme: string; test: string; route: string }
  >;
  expect(Object.keys(manifest)).toContain("01-chat-real-answer.png");
  expect(Object.keys(manifest)).toContain("12-account-backups-390-dark.png");
  for (const entry of Object.values(manifest)) {
    expect(entry.commit).toMatch(/^[0-9a-f]{40}$/);
    expect(entry.test).toContain("round-2026-10-05-backups-live.spec.ts");
  }
  expect(manifest["12-account-backups-390-dark.png"].viewport?.width).toBe(390);
  expect(manifest["12-account-backups-390-dark.png"].theme).toBe("dark");
});
