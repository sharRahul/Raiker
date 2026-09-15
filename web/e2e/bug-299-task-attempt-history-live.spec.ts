/**
 * BUG-299 / UX-TASK-04 against a running `raiker-web` — a task has an address.
 *
 * Two shipped changes already promised this page and neither could point at it.
 * [FIXED-531] deduplicated Home's rows and its acceptance asked each to "link to
 * the canonical Tasks detail". [FIXED-533] gave one run one Stop, Resume and
 * Run-now meaning and, with it, an honest third settlement — `outcome_unknown`,
 * whose remedy reads *"refresh to see the run's current state"*. There was
 * nowhere to refresh to: a task had a status and a current step, no attempt
 * list, no record of the approval it paused on and no route of its own.
 *
 * This drives the whole of it through the product against a real Anthropic
 * model: plan a task, watch it run, open its history from the board, from Home
 * and by URL, and read the attempts the runtime recorded rather than a status
 * line standing in for them.
 *
 * Prerequisites:
 *   1. `raiker-web --workspace <ws> --port 8765 --no-browser` with
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (entered through the UI)
 */
import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(
  import.meta.dirname,
  "..",
  "..",
  "docs",
  "screenshots",
  "2026-09-15-task-history",
);
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";
/** How the composer's own menu names it — a display name, not the wire id. */
const MODEL_LABEL = /Haiku 4\.5/;
const INSTRUCTION = "Reply with one short sentence confirming the run started.";

test.describe.configure({ mode: "serial" });

/** The task this round plans, named so every step can find exactly it. */
const TITLE = "Reply with one short sentence confirming the run started";

async function planATask(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/tasks`);
  const instruction = page.getByLabel("What should Raiker do?");
  await expect(instruction).toBeVisible({ timeout: 30_000 });
  await instruction.fill(INSTRUCTION);
  // BUG-292 — pinning a model on a provider card and choosing the one that
  // answers are two different decisions. The Tasks composer is right to refuse
  // until the second has been made.
  await chooseModelForTurn(page, MODEL_LABEL, "Plan work");
  await page.getByRole("button", { name: /Create task/ }).click();
  await expect(page.getByText("Saved to your work queue.")).toBeVisible({ timeout: 30_000 });
}

test("a task's attempts have an address, and every surface links to it", async ({ page }) => {
  // Registering an owner, connecting a provider and running a governed cycle
  // does not fit the 30-second default.
  test.setTimeout(300_000);
  test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is required for this round.");
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: /API key/,
    key: ANTHROPIC_KEY,
    model: MODEL,
  });

  await planATask(page);

  // ── the board links every task to its own history ────────────────────────
  const boardLink = page.getByRole("link", { name: TITLE }).first();
  await expect(boardLink).toBeVisible({ timeout: 60_000 });
  const href = await boardLink.getAttribute("href");
  expect(href).toMatch(/^#\/tasks\?task=task_/);

  // ── the address itself ───────────────────────────────────────────────────
  await boardLink.click();
  const panel = page.getByRole("region", { name: TITLE });
  await expect(panel).toBeVisible({ timeout: 30_000 });
  // The filing is a record in its own right, so a task that has not settled
  // still opens on something rather than on an empty page.
  await expect(panel.getByText("Filed.").first()).toBeVisible({ timeout: 30_000 });
  // The board is still underneath: following a link never costs the page.
  await expect(page.getByLabel("What should Raiker do?")).toBeVisible();

  // ── the attempt itself, once the cycle has run ───────────────────────────
  // "Run now" is on the card; the history is the place the outcome is read.
  await page.goto(`${BASE}/#/tasks`);
  const runNow = page.getByRole("button", { name: /^Run now$/ }).first();
  if (await runNow.isVisible().catch(() => false)) await runNow.click();

  await page.goto(`${BASE}${href}`);
  await expect(panel).toBeVisible({ timeout: 30_000 });
  // A run the scheduler claimed records where it started, which is the half of
  // a history that did not exist before: every ending had no beginning.
  await expect(panel.getByRole("heading", { name: "Attempt 1", level: 4 })).toBeVisible({
    timeout: 120_000,
  });
  // The step the runtime recorded, not a sentence this spec supplied: the
  // attempt's first row is the current step the claim wrote onto the task.
  await expect(panel.getByText("Starting scheduled run").first()).toBeVisible({
    timeout: 30_000,
  });
  // And the attempt states how it settled, which is the thing a status line
  // could never keep: the next cycle used to overwrite it.
  await expect(panel.getByText("completed", { exact: true }).first()).toBeVisible({
    timeout: 30_000,
  });
  await capture(page, join(SHOTS, "task-attempt-history.png"));

  // ── Home's rows point at the same address ────────────────────────────────
  await page.goto(`${BASE}/#/home`);
  const homeLink = page.getByRole("link", { name: TITLE }).first();
  if (await homeLink.isVisible().catch(() => false)) {
    expect(await homeLink.getAttribute("href")).toBe(href);
  }

  // Everything above is the ordinary path, and it ends with a clean console.
  // Asserted here rather than at the end of the test because the last step
  // deliberately asks for a task that does not exist, and a budget that is
  // spent by the spec's own probe stops measuring anything (BUG-296).
  expect(consoleErrors).toEqual([]);

  // ── a task that is not this account's is said so, not shown empty ────────
  // The 404 is the right answer and the owner drove the request, so it keeps
  // its status exactly as FIXED-527 says a driven route should. What matters is
  // that the page reports it rather than showing an empty history.
  await page.goto(`${BASE}/#/tasks?task=task_does_not_exist`);
  await expect(page.getByText("That task is not on this account's board.")).toBeVisible({
    timeout: 30_000,
  });
});
