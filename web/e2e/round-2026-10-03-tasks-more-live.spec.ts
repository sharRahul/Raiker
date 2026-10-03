/**
 * The 2026-10-03 round: §3.8 Tasks (UX-TASK-02, 03, 05, 06), §3.6 the More
 * window (UX-SETPOP-02, 03, 04) and UX-PERM-01, driven against a running host.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, with
 * Anthropic connected through Models from `RAIKER_LIVE_ANTHROPIC_KEY` — the key
 * typed into the Connect dialog, never written here.
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-03-tasks-more-round");

test.describe.configure({ mode: "serial" });

function watchFailures(page: Page): { failures: string[]; consoleErrors: string[] } {
  const failures: string[] = [];
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 400) {
      failures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  return { failures, consoleErrors };
}

/** Hosts this container cannot reach; their refusals are the network's, not Raiker's. */
const UNREACHABLE = /huggingface|openrouter|ollama|503/i;

/** A `datetime-local` value for a time this many days ahead, at 09:00. */
function ahead(days: number): { local: string; date: string } {
  const at = new Date();
  at.setDate(at.getDate() + days);
  const pad = (value: number) => String(value).padStart(2, "0");
  const date = `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`;
  return { local: `${date}T09:00`, date };
}

const HAIKU = /Haiku 4\.5/i;

async function composeOnTasks(page: Page, instruction: string) {
  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  // Each Work composer carries its own model choice; Tasks is asked like Chat is.
  const picker = page.getByRole("group", { name: "Plan work" }).getByRole("button", { name: /^Model for this turn:/ });
  if (/Not selected/.test((await picker.getAttribute("aria-label")) ?? (await picker.textContent()) ?? "")) {
    await chooseModelForTurn(page, HAIKU, "Plan work");
  }
  await page.getByLabel("What should Raiker do?").fill(instruction);
}

async function openDetails(page: Page) {
  const toggle = page.locator("button.schedule-toggle");
  if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();
}

test("Anthropic connects through Models", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await useAnthropic(page, BASE);
  await capture(page, join(SHOTS, "01-anthropic-connected.png"));
});

test("a weekday routine is composed in two groups and keeps its terms", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await composeOnTasks(page, "Draft my stand-up notes from yesterday's work.");
  await page.getByRole("button", { name: "Repeating" }).click();
  await openDetails(page);
  const schedule = page.getByRole("group", { name: "Schedule" });
  await expect(schedule).toBeVisible();
  await expect(page.getByRole("group", { name: "Organisation" })).toBeVisible();
  await page.getByLabel("Repeat").selectOption("weekdays");
  await page.getByLabel("First run").fill(ahead(2).local);
  await page.getByLabel("Last day it runs").fill(ahead(40).date);
  await page.getByLabel("If a run is missed").selectOption("skip");
  const preview = page.getByRole("status", { name: "Next runs" });
  await expect(preview.getByRole("listitem")).toHaveCount(3);
  await expect(preview).toContainText("skipped");
  // Weekdays only: no Saturday or Sunday among the three runs it previews.
  await expect(preview).not.toContainText(/Sat|Sun/);
  await expect(page.getByLabel("Parent work")).toHaveCount(0);
  await capture(page, join(SHOTS, "02-routine-schedule-and-organisation.png"), page.getByRole("group", { name: "Plan work" }));
  await page.getByRole("button", { name: /Create routine/ }).click();
  await expect(page.getByText("Saved to your work queue.")).toBeVisible({ timeout: 30_000 });
  const card = page.locator("article.task", { hasText: "Draft my stand-up notes" });
  await expect(card).toContainText("Runs on weekdays");
  await expect(card).toContainText("until");
  await expect(card).toContainText("skips missed runs");
  // UX-TASK-05 — not run yet, so its control is Cancel and its badge says when.
  await expect(card.getByText("scheduled", { exact: true })).toBeVisible();
  await expect(card.getByRole("button", { name: "Cancel" })).toBeVisible();
  await expect(card.getByRole("button", { name: "Stop" })).toHaveCount(0);
  await capture(page, join(SHOTS, "03-routine-card-terms.png"), card);
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("delegated work folds under its parent, and a real run can be run again", async ({ page }) => {
  test.setTimeout(420_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await composeOnTasks(page, "Reply with the single word: ready.");
  await openDetails(page);
  await page.getByRole("button", { name: "Make this part of other work…" }).click();
  await page.getByLabel("Parent work").selectOption({ label: "Draft my stand-up notes from yesterday's work" });
  await page.getByRole("button", { name: /^Create task/ }).click();
  await expect(page.getByText("Saved to your work queue.")).toBeVisible({ timeout: 30_000 });
  // The child is folded under its parent, with the parent counting it.
  const parent = page.locator("article.task", { hasText: "Draft my stand-up notes" });
  const fold = parent.getByRole("button", { name: /delegated task settled/ });
  await expect(fold).toBeVisible();
  await expect(page.locator("article.task", { hasText: "Reply with the single word" })).toHaveCount(0);
  // The child runs now against the real provider, and settles.
  await expect
    .poll(
      async () => {
        await page.getByRole("button", { name: "Refresh" }).click();
        return (await fold.textContent()) ?? "";
      },
      { timeout: 300_000, intervals: [5_000] },
    )
    .toMatch(/1 of 1 delegated task settled/);
  await capture(page, join(SHOTS, "04-delegated-folded.png"), parent);
  await fold.click();
  // Opened, the parent shows all of its delegated work — the settled child
  // included, under it rather than again in Finished work.
  const finished = page.locator("article.task", { hasText: "Reply with the single word" });
  await expect(finished.getByRole("heading", { name: /Reply with the single word/ })).toBeVisible();
  await expect(page.locator(".history-row", { hasText: "Reply with the single word" })).toHaveCount(0);
  // Finished one-off work offers Run again, which files new work.
  await expect(finished.getByRole("button", { name: "Run again" })).toBeVisible();
  // Its last step is history, not what it is doing now; and the composer kept
  // its model, so the next task is not blocked behind "No model is chosen".
  await expect(finished.getByText(/^Now:/)).toHaveCount(0);
  await expect(page.getByText("No model is chosen.")).toHaveCount(0);
  await capture(page, join(SHOTS, "05-finished-run-again.png"), page.locator("section.work-list"));
  await finished.getByRole("button", { name: "Run again" }).click();
  await expect(page.getByText(/Filed “Reply with the single word: ready” again as new work/)).toBeVisible({ timeout: 30_000 });
  expect(seen.failures.filter((line) => !UNREACHABLE.test(line))).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("Permissions leads with what each permission is for", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/capabilities`);
  await settled(page);
  const registry = page.getByRole("region", { name: "All permissions" });
  const headings = registry.locator(".phase-head .phase-fold");
  await expect(headings.first()).toBeVisible();
  const order = await registry.locator(".phase-head label").allTextContents();
  const names = order.map((text) => text.trim());
  expect(names).toEqual([
    "Files and code",
    "Web and research",
    "Messages and services",
    "Memory",
    "System and runtimes",
  ]);
  await capture(page, join(SHOTS, "06-permissions-by-task.png"), registry.locator(".registry-heading").locator(".."));
  await registry.getByRole("button", { name: "Technical area (advanced)" }).click();
  await expect(registry.getByRole("checkbox", { name: "Select all Execution capabilities" })).toBeVisible();
  await registry.getByRole("button", { name: "What it's for" }).click();
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("More groups by purpose, remembers where you were, and hands search to the palette", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/models`);
  await settled(page);
  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  await page.getByRole("button", { name: "More pages and settings" }).click();
  const more = page.getByRole("dialog", { name: /^more$/i });
  await expect(more.getByText("You are on")).toContainText("Tasks");
  const headings = await more.getByRole("heading", { level: 3 }).allTextContents();
  expect(headings).toEqual(["Recent", "Review", "Connect", "Settings", "Diagnostics & help"]);
  await expect(more.getByRole("heading", { name: "Recent" }).locator("..").getByRole("link", { name: "Models" })).toBeVisible();
  await capture(page, join(SHOTS, "07-more-by-purpose.png"), more);
  await more.getByRole("button", { name: /Search pages, settings and commands/ }).click();
  await expect(more).toBeHidden();
  const palette = page.getByRole("dialog").filter({ has: page.getByRole("combobox").or(page.getByRole("textbox")) });
  await expect(palette.first()).toBeVisible();
  await page.keyboard.type("privacy");
  await capture(page, join(SHOTS, "08-palette-finds-settings.png"));
  await page.keyboard.press("Escape");
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("on a phone More is a full-height sheet with Back", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  await page.getByRole("button", { name: "More pages and settings" }).click();
  const more = page.getByRole("dialog", { name: /^more$/i });
  const box = await more.boundingBox();
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(840);
  expect(box?.width ?? 0).toBeGreaterThanOrEqual(388);
  await expect(more.getByRole("button", { name: "Back" })).toBeVisible();
  await capture(page, join(SHOTS, "09-more-sheet-390.png"));
  await more.getByRole("button", { name: "Back" }).click();
  await expect(more).toBeHidden();
  // The Tasks composer at a phone's width, details open.
  await openDetails(page);
  await capture(page, join(SHOTS, "10-tasks-details-390.png"));
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("every destination loads with no refused request or console error", async ({ page }) => {
  test.setTimeout(240_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  for (const route of [
    "home", "new-chat", "build", "design", "search-chat", "tasks", "projects", "memory",
    "brain", "approvals", "messaging", "capabilities", "models", "extensions", "observe",
    "guide", "settings",
  ]) {
    await page.goto(`${BASE}/#/${route}`);
    await settled(page);
  }
  expect(seen.failures.filter((line) => !UNREACHABLE.test(line))).toEqual([]);
  expect(seen.consoleErrors.filter((line) => !UNREACHABLE.test(line))).toEqual([]);
});
