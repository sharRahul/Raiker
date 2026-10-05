/**
 * The 2026-10-05 (fifth) round, first phase: what a turn is told about language
 * and place (DEC-21 General), dates in the owner's format, a permission saved
 * from a stale tab (13.2 #6), a task filed once however often it is sent
 * (13.2 #6), a routine's cost limit (DEC-12 step 6), and a backup with a
 * conversation deleted after it — which the second phase restores from the
 * lock screen (`round-2026-10-05-lockscreen-live.spec.ts`).
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, served
 * with `RAIKER_LIVE_WORKSPACE` pointing at it. Harness:
 * `scripts/live_recovery_harness.py`. Anthropic is entered through the Connect
 * dialog from `RAIKER_LIVE_ANTHROPIC_KEY` and never written anywhere.
 */
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { horizontalBleed, settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_MODEL, LIVE_BASE, sendTurn, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-05-recovery-round");
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

function harness(...args: string[]): Record<string, unknown> {
  const out = execFileSync(PYTHON, [join(REPO, "scripts", "live_recovery_harness.py"), WORKSPACE, ...args], {
    encoding: "utf-8",
  });
  return JSON.parse(out.trim()) as Record<string, unknown>;
}

/** A same-origin API call made the way the page makes one. */
async function api(page: Page, method: string, path: string, body?: unknown, headers: Record<string, string> = {}) {
  return page.evaluate(
    async ({ method, path, body, headers }) => {
      const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/)?.[1] ?? "";
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: {
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
          ...(method === "GET" ? {} : { "X-Raiker-CSRF": decodeURIComponent(csrf) }),
          ...headers,
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const json: unknown = await response.json().catch(() => null);
      return { status: response.status, json };
    },
    { method, path, body, headers },
  );
}

async function openSettings(page: Page, tab: string): Promise<void> {
  await page.goto(`${BASE}/#/settings?tab=${tab}`);
  await settled(page);
  await page
    .waitForResponse((response) => response.url().endsWith("/api/settings"), { timeout: 10_000 })
    .catch(() => undefined);
  await page.waitForTimeout(1_000);
}

test("General names three languages and the date format takes effect", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await openSettings(page, "general");
  await expect(page.getByText("Raiker's own text is in English.", { exact: false })).toBeVisible();
  await expect(page.getByText("Country or region")).toHaveCount(0);
  await page.getByLabel("Answer in").selectOption("fr");
  await page.getByLabel("Dates and times").selectOption("de-DE");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText(/saved/i).first()).toBeVisible({ timeout: 15_000 });
  // The sample on the control is written in the chosen format: "05.10.2026, 17:23".
  await expect(page.locator("label").filter({ hasText: "Dates and times" })).toContainText(/\d{2}\.\d{2}\.2026, \d{2}:\d{2}/);
  await capture(page, join(SHOTS, "01-general-three-languages.png"), page.locator(".settings-card").first());
  await openSettings(page, "personalisation");
  await page.getByLabel("Default weather location").fill("Edinburgh, United Kingdom");
  await page.getByLabel("Default weather location").blur();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText(/Models are told only that you set one, never the place/)).toBeVisible();
  await capture(page, join(SHOTS, "02-weather-location-disclosed.png"), page.locator(".settings-card").nth(1));
  expect(seen.failures).toEqual([]);
});

test("a real Anthropic turn answers in French and is told no place", async ({ page }) => {
  test.setTimeout(300_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await useAnthropic(page);
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  await chooseModelForTurn(page, new RegExp(ANTHROPIC_MODEL.includes("haiku") ? "Haiku" : ".", "i"));
  await sendTurn(page, "Greet me in one short sentence.");
  await expect(page.getByText(/bonjour|salut|ravi|enchanté/i).first()).toBeVisible({ timeout: 120_000 });
  const told = harness("environment") as { payload: Record<string, unknown> };
  expect(told.payload.answer_language).toBe("fr");
  expect(told.payload.default_weather_location).toBe("set");
  expect(told.payload).not.toHaveProperty("location");
  expect(JSON.stringify(told.payload)).not.toContain("Edinburgh");
  expect(JSON.stringify(told.payload)).not.toContain("de-DE");
  await capture(page, join(SHOTS, "03-chat-answers-in-french.png"));
  expect(seen.failures).toEqual([]);
});

test("a stale tab cannot overwrite a permission another tab changed", async ({ page, context }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/capabilities`);
  await settled(page);
  const stale = page.getByRole("group", { name: /shell commands/i }).last();
  await expect(stale.getByRole("button", { name: "Ask me", pressed: true })).toBeVisible({ timeout: 30_000 });

  const other = await context.newPage();
  await other.goto(`${BASE}/#/capabilities`);
  await settled(other);
  const fresh = other.getByRole("group", { name: /shell commands/i }).last();
  await fresh.getByRole("button", { name: "Never" }).click();
  await expect(other.getByText(/is now set to “Never”/)).toBeVisible({ timeout: 15_000 });
  await other.close();

  // This tab still shows "Ask me" and now tries a change of its own.
  await stale.getByRole("button", { name: "Never" }).click();
  await expect(page.getByText(/changed somewhere else since this page loaded, so nothing was changed/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(stale.getByRole("button", { name: "Never", pressed: true })).toBeVisible({ timeout: 15_000 });
  await capture(page, join(SHOTS, "04-permission-stale-tab-refused.png"));
  // From the page that shows the current value, the owner's change goes through.
  await stale.getByRole("button", { name: "Ask me" }).click();
  await expect(page.getByText(/is now set to “Ask me”/)).toBeVisible({ timeout: 15_000 });
});

test("the same task sent twice is filed once, and a changed resend is refused", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  const key = { "Idempotency-Key": "draft-live-round-0001" };
  const draft = {
    title: "Water the office plants",
    description: "Remind me to water the plants on Friday.",
    model_profile: "anthropic-hosted",
    model: ANTHROPIC_MODEL,
  };
  const first = await api(page, "POST", "/api/tasks", draft, key);
  const again = await api(page, "POST", "/api/tasks", draft, key);
  expect(first.status, JSON.stringify(first.json)).toBe(201);
  expect(again.status).toBe(201);
  expect((again.json as { task_id: string }).task_id).toBe((first.json as { task_id: string }).task_id);
  const changed = await api(page, "POST", "/api/tasks", { ...draft, title: "Water every plant" }, key);
  expect(changed.status).toBe(409);
  expect((changed.json as { detail: { reason_code: string } }).detail.reason_code).toBe("idempotency_key_reused");
  await page.reload();
  await settled(page);
  await expect(page.locator("article.task").filter({ hasText: "Water the office plants" })).toHaveCount(1);
  await capture(page, join(SHOTS, "05-task-filed-once.png"), page.locator("article.task").filter({ hasText: "Water the office plants" }));
});

test("a routine's cost limit is said, and a run that reaches it stops at a safe boundary", async ({ page }) => {
  test.setTimeout(420_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  const at = new Date(Date.now() + 24 * 3600_000).toISOString();
  const title = `Workspace survey ${Date.now() % 100_000}`;
  const made = await api(page, "POST", "/api/tasks", {
    title,
    description:
      "List the files at the top of the workspace, then read each of the first three files you find, then summarise what this workspace is for.",
    recurrence: "daily",
    scheduled_at: at,
    timezone: "UTC",
    model_profile: "anthropic-hosted",
    model: ANTHROPIC_MODEL,
  });
  expect(made.status, JSON.stringify(made.json)).toBe(201);
  const taskId = (made.json as { task_id: string }).task_id;
  await page.reload();
  await settled(page);
  const card = page.locator("article.task").filter({ hasText: title }).first();
  await card.getByRole("button", { name: "Will it run?" }).click();
  const panel = card.getByTestId("routine-check");
  await panel.getByLabel("Cost limit per run in US dollars").fill("0.01");
  await panel.getByRole("button", { name: "Save limit" }).click();
  await expect(panel).toContainText("Each run now stops after 60 minutes or $0.01.");
  await expect(panel).toContainText(/Each run is stopped after 60 minutes or \$0\.01/, { timeout: 15_000 });
  await capture(page, join(SHOTS, "06-routine-cost-limit-said.png"), card);

  // Its next slot, made due: the host's own pass runs it, as at 03:00.
  expect((harness("due", taskId) as { changed: number }).changed).toBe(1);
  // Wait for the host's pass to run it and land its outcome on the card.
  let summary = "";
  for (let i = 0; i < 72 && !summary; i += 1) {
    await page.waitForTimeout(5_000);
    const read = await api(page, "GET", `/api/tasks/${taskId}`);
    summary = (read.json as { task: { summary: string | null } }).task.summary ?? "";
  }
  // The routine's prompt sends it round a tool loop; at $0.01 it is stopped
  // before the model is asked again, by the provider's own token counts.
  expect(summary).toMatch(/reached its cost limit of \$0\.01/);
  await page.reload();
  await settled(page);
  await capture(page, join(SHOTS, "07-routine-run-outcome.png"), page.locator("article.task").filter({ hasText: title }).first());
  test.info().annotations.push({ type: "routine-outcome", description: summary });
  expect(seen.failures).toEqual([]);
});

test("a backup, then a conversation deleted after it", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  // A second conversation to delete after the backup is taken.
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  await chooseModelForTurn(page, new RegExp(ANTHROPIC_MODEL.includes("haiku") ? "Haiku" : ".", "i"));
  await sendTurn(page, "Reply with exactly: deleted after the backup");
  await expect(page.getByText(/deleted after the backup/i)).toHaveCount(2, { timeout: 120_000 });
  const session = (harness("environment") as { session: string }).session;
  await page.goto(`${BASE}/#/settings?tab=account`);
  await settled(page);
  const card = page.getByTestId("backups-card");
  await card.getByRole("button", { name: "Back up now" }).click();
  await expect(card).toContainText(/Backed up and verified — /, { timeout: 60_000 });
  // Deleted after the backup: a restore must not bring it back.
  const deleted = await api(page, "DELETE", `/api/sessions/${session}`, undefined, { "X-Session-Delete-Confirm": session });
  expect(deleted.status, JSON.stringify(deleted.json)).toBeLessThan(300);
  const left = harness("sessions") as { sessions: { session_id: string }[] };
  expect(left.sessions.map((row) => row.session_id)).not.toContain(session);
  test.info().annotations.push({ type: "deleted-session", description: session });
  await capture(page, join(SHOTS, "08-backup-before-deletion.png"), card);
});

test("General at 390 wide in the dark theme, without bleeding", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark" });
  await signInAsOwner(page, BASE);
  await openSettings(page, "general");
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "09-general-390-dark.png"), page.locator(".settings-card").first());
});
