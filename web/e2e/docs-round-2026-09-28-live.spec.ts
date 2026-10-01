import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { DESTINATIONS, WIDTHS, settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";
import { LIVE_BASE, LIVE_KEYS } from "./live";

/**
 * The 2026-09-28 round, live: the items from `docs/plans/` this run closed that
 * only a browser and a real host can prove.
 *
 * * **GEP-02** — the owner's decision is that Stop halts everything being
 *   performed, and the thing an owner most often wants to stop is the answer
 *   they are watching stream. That is only provable against a provider that is
 *   really streaming one.
 * * **BUG-307** — `style-src` lost `'unsafe-inline'`. A unit test proves the
 *   header; only a browser can prove the product still draws under it, and the
 *   browser's `securitypolicyviolation` event is where a refusal shows.
 *
 * The security findings closed with them (CR-03, CR-04, CR-10, CR-11, CR-13) and
 * GCR-12 change no surface on their own and are proved by their unit tests.
 *
 * Preconditions:
 *   1. `raiker-web` on 127.0.0.1:8765, on a workspace reset for the round
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment — entered through the UI
 */
const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-09-28-docs-round");
const ANTHROPIC_KEY = LIVE_KEYS.anthropic;
const MODEL = "claude-haiku-4-5-20251001";
const MODEL_LABEL = /Haiku 4\.5/;

test.describe.configure({ mode: "serial" });
test.setTimeout(600_000);

test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set for this round.");

/**
 * Every CSP refusal the page reports, from the browser's own event rather than
 * the console's wording — installed before any script of the page runs, so a
 * refusal during boot is caught too.
 */
async function watchForPolicyViolations(page: Page): Promise<() => Promise<string[]>> {
  const consoleRefusals: string[] = [];
  page.on("console", (message) => {
    if (/Content Security Policy|Refused to (load|execute|connect|apply)/i.test(message.text())) {
      consoleRefusals.push(message.text());
    }
  });
  await page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as { __cspRefusals: string[] }).__cspRefusals = seen;
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(`${event.violatedDirective} ← ${event.blockedURI || "inline"} (${event.sourceFile}:${event.lineNumber})`);
    });
  });
  return async () => {
    const fromPage = await page
      .evaluate(() => (window as unknown as { __cspRefusals?: string[] }).__cspRefusals ?? [])
      .catch(() => [] as string[]);
    return [...consoleRefusals, ...fromPage];
  };
}

test("the owner's provider is connected, and a model is ready to answer", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "anthropic",
    keyLabel: "API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await capture(page, join(SHOTS, "01-anthropic-connected.png"));
});

/**
 * GEP-02 — Stop reaches the answer being written, with no task running.
 *
 * Before this round the switch read the task list alone, so with only a chat
 * turn streaming it said "Nothing is running" and could not stop it.
 */
test("GEP-02: the stop switch stops the answer being written", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);

  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill(
    "Write a detailed, 1500-word history of the printing press, in numbered sections of " +
      "at least 150 words each. Do not use any tools.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // The answer is streaming: the switch, opened now, counts it.
  const stop = page.getByRole("button", { name: /Stop all work/ });
  await expect(page.locator(".message-bubble-raiker").first()).toBeVisible({ timeout: 120_000 });
  await stop.click();
  const dialog = page.getByRole("dialog", { name: /Stop all work in progress\?/ });
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await expect(dialog).toContainText("1 answer being written");
  await expect(dialog).toContainText("whether or not it reaches outside this machine");
  await capture(page, join(SHOTS, "02-stop-counts-the-answer-being-written.png"));

  await dialog.getByRole("button", { name: "Stop all" }).click();
  // One answer, reported once. The first run of this round said "1 answer
  // being written and 1 task": a turn's own governance task, which the task
  // list hides because it *is* the turn, was counted as a second thing.
  await expect(dialog).toContainText("Stop applied at the safe boundary to 1 answer being written.", {
    timeout: 30_000,
  });
  await expect(dialog).not.toContainText(/\d+ tasks?\b/);
  await capture(page, join(SHOTS, "03-stop-applied.png"));
  await dialog.getByRole("button", { name: "Close" }).click();

  // The turn ends as stopped — said so in the transcript, not a failure.
  await expect(page.getByText(/Stopped at your request/)).toBeVisible({ timeout: 180_000 });
  await capture(page, join(SHOTS, "04-turn-stopped-at-safe-boundary.png"));

  // And nothing is left running for the switch to count.
  await stop.click();
  await expect(page.getByRole("dialog", { name: "Nothing is running" })).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: "Close" }).click();
});

/**
 * GEP-02 — the next turn in the same conversation is not stopped by the last
 * press: the stop reached a live turn and was consumed by it.
 */
test("GEP-02: a stopped conversation answers its next turn", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill("Reply with the single word: ready");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText(/ready/i).first()).toBeVisible({ timeout: 180_000 });
  await expect(page.getByText(/Stopped at your request/)).toHaveCount(0);
});

/**
 * BUG-307 — every destination, at every width, under `style-src 'self'`.
 */
test("BUG-307: nothing is refused without an inline-style allowance", async ({ page }) => {
  const refusals = await watchForPolicyViolations(page);
  const response = await page.goto(`${BASE}/#/workbench`);
  const policy = response?.headers()["content-security-policy"] ?? "";
  expect(policy).toContain("style-src 'self'");
  expect(policy).not.toContain("unsafe-inline");

  await signInAsOwner(page, BASE);
  for (const { width, height } of WIDTHS) {
    await page.setViewportSize({ width, height });
    for (const destination of DESTINATIONS) {
      await page.goto(`${BASE}/#/${destination.route}`);
      await expect(page.locator("main#main")).toBeVisible({ timeout: 60_000 });
      await settled(page).catch(() => undefined);
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Threads, holding this round's two conversations, drawn under the policy.
  await page.goto(`${BASE}/#/search-chat`);
  await expect(page.getByText(/printing press/i).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "05-threads-under-strict-style-src.png"));
  // Home, once its readiness read has answered: the rail says what was read.
  await page.goto(`${BASE}/#/workbench`);
  const rail = page.getByRole("complementary", { name: "Needs your attention" });
  await expect(rail).toContainText(/Nothing needs you right now|not an all-clear/, { timeout: 90_000 });
  await expect(rail).not.toContainText(/still reading/, { timeout: 90_000 });
  await capture(page, join(SHOTS, "06-home-under-strict-style-src.png"));
  const found = await refusals();
  expect(found, `the policy refused something the product needs:\n${found.join("\n")}`).toEqual([]);
});
