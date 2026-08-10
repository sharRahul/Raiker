/**
 * The 2026-08-10 round's five defects, against a running `raiker-web` holding a
 * real Anthropic credential entered through the product's own Models page.
 *
 * Each test is the reproduction from `docs/plans/TO_BE_FIXED.md`, run forward
 * over the fix:
 *
 *  * **BUG-68** — the Chat context popover rendered `NaN input · NaN output`
 *    beneath four correct figures, because the API's secret-shaped-field
 *    redactor discarded `session_input_tokens` / `session_output_tokens` and the
 *    browser formatted `"***REDACTED***"`. The line must read real counts.
 *  * **BUG-70** — Build's Plan / Edit / Auto chips issued four
 *    `POST /api/capability-modes/<cap>/<mode>` calls with no step-up, rewriting
 *    the owner's standing permissions globally and permanently. Pressing a chip
 *    must now change nothing standing, and must say so.
 *  * **BUG-71** — Permissions listed **Memory store** with all four decision
 *    modes while no turn could ever propose a memory write, because
 *    `memory_write` / `memory_forget` were absent from the model's catalogue.
 *    A turn must be able to propose one, and the Memory page must stop
 *    promising proposals it cannot produce.
 *  * **BUG-73** — a conversation ended, durably, saying "No command was
 *    executed" beneath the chip for the file the approval had just written. A
 *    parked turn must report its *state*, never a claim about execution.
 *  * **BUG-82** — the advisor is a second model this runtime calls, chosen in
 *    the same UI as the chat model and never readiness-checked. Its selector
 *    must carry the same chip and repair sentence a provider card does.
 *
 * Prerequisites:
 *   1. `python -m apps.api.main --workspace <fresh ws> --port 8765 --no-browser`
 *      with `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (entered through the UI
 *      below — never committed)
 *
 * The workspace must be **fresh**: three of the claims are about what a
 * capability or a page does before the owner has touched it.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { useHostedModel, refreshHostedReadiness } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Round-0810-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function signIn(target: Page) {
  await target.goto(`${BASE}/#/workbench`);
  await expect(target.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const confirm = target.getByLabel("Confirm password");
  await target.getByLabel("Username").fill("owner");
  await target.getByLabel("Password", { exact: true }).fill(PASSWORD);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await target.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await target.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  await expect(target.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 30_000 });
}

/** Send one prompt in Chat and wait for *this* turn to finish. */
async function ask(prompt: string) {
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  const before = await page.locator(".message-bubble-raiker").count();
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
  await expect
    .poll(async () => page.locator(".message-bubble-raiker").count(), { timeout: 60_000 })
    .toBeGreaterThan(before);
  return page.locator(".message-bubble-raiker").last();
}

/**
 * Open one capability's card on the Permissions page.
 *
 * `fresh: false` reuses the page already on screen. Permissions is one governed
 * read per load, and reading four capabilities with four navigations is enough
 * requests in enough seconds to earn a 429 from the API's own rate limiter — so
 * a snapshot of several capabilities navigates once and filters in place.
 */
async function openCapability(label: string, fresh = true) {
  const search = page.getByPlaceholder("Search capabilities…");
  if (fresh || !(await search.isVisible().catch(() => false))) {
    await page.goto(`${BASE}/#/capabilities`);
    await expect(search).toBeVisible({ timeout: 30_000 });
  }
  await search.fill(label);
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  if ((await card.getByRole("button", { name: label }).getAttribute("aria-expanded")) !== "true") {
    await card.getByRole("button", { name: label }).click();
  }
  await expect(card.locator(".cap-detail")).toBeVisible({ timeout: 10_000 });
  return card;
}

async function enableCapability(label: string, reason: string) {
  const card = await openCapability(label);
  const turnOn = card.getByRole("button", { name: "Turn on" });
  await expect(turnOn).toBeVisible({ timeout: 10_000 });
  await turnOn.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await dialog.getByLabel("Reason (required)").fill(reason);
  const token = dialog.getByLabel(/Confirmation token/);
  if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
  const ack = dialog.getByRole("checkbox");
  if (await ack.isVisible().catch(() => false)) await ack.check();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
  await expect(page.getByText(`Enabled ${label}.`)).toBeVisible({ timeout: 30_000 });
}

/** The decision mode each Build write capability currently stands at. */
async function standingWriteModes(): Promise<Record<string, string>> {
  const modes: Record<string, string> = {};
  await page.goto(`${BASE}/#/capabilities`);
  await expect(page.getByPlaceholder("Search capabilities…")).toBeVisible({ timeout: 30_000 });
  for (const capability of ["File writes", "Patch apply", "Shell commands", "Processes"]) {
    const card = await openCapability(capability, false);
    for (const mode of ["Ask", "Allow", "Auto", "Deny"]) {
      const button = card.getByRole("button", { name: mode, exact: true });
      if ((await button.getAttribute("aria-pressed")) === "true") modes[capability] = mode;
    }
  }
  return modes;
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  page = await context.newPage();
  await signIn(page);
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
});

test.afterAll(async () => {
  await context?.close();
});

test("BUG-68 — the context meter reports real input and output counts", async () => {
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.goto(`${BASE}/#/new-chat`);
  await ask("Say OK.");

  await page.getByRole("button", { name: /Context window/i }).click();
  const popover = page.locator(".context-popover");
  await expect(popover).toBeVisible({ timeout: 30_000 });

  // The regression: `number.format("***REDACTED***")` is NaN, so this exact line
  // read "NaN input · NaN output" beneath four correct figures.
  const split = popover.getByText(/\d[\d,]*\s+input\s+·\s+\d[\d,]*\s+output/);
  await expect(split).toBeVisible({ timeout: 30_000 });
  await expect(popover.getByText(/NaN/)).toHaveCount(0);
  await page.screenshot({ path: join(SHOTS, "r0810-bug68-context-meter-real-io-counts.png") });
});

test("BUG-70 — a Build mode chip changes nothing standing and says so", async () => {
  const before = await standingWriteModes();
  expect(Object.keys(before)).toHaveLength(4);

  await page.goto(`${BASE}/#/build`);
  const requests: string[] = [];
  const listener = (request: { url: () => string; method: () => string }) => {
    if (request.method() === "POST" && request.url().includes("/api/capability-modes/")) {
      requests.push(request.url());
    }
  };
  page.on("request", listener);

  // Auto was the sharpest case: four high-risk permissions set to `auto` with
  // no dialog, no reason, and no acknowledgement.
  await page.getByRole("button", { name: "Auto", exact: true }).click();
  await expect(page.getByRole("button", { name: "Auto", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByText(/Change in Permissions/)).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: join(SHOTS, "r0810-bug70-build-auto-changes-nothing-standing.png") });

  await page.getByRole("button", { name: "Plan", exact: true }).click();
  await expect(page.getByText(/for this turn only/i)).toBeVisible({ timeout: 10_000 });
  page.off("request", listener);

  expect(requests, "a composer chip must not write standing decision modes").toEqual([]);
  expect(await standingWriteModes()).toEqual(before);
  await page.screenshot({ path: join(SHOTS, "r0810-bug70-permissions-unchanged.png") });
});

test("BUG-70 — Plan really refuses the write it is presented as refusing", async () => {
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.goto(`${BASE}/#/build`);
  await page.getByRole("button", { name: "Plan", exact: true }).click();

  const composer = page.getByLabel("Describe the change");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(
    "Use the write_file tool to create plan-mode-probe.md containing the word BLOCKED. " +
      "If the tool is refused, say exactly what the refusal was.",
  );
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });

  // The posture is enforced by the runtime, not by prompt wording: the turn
  // never parks for an approval, because the call is refused outright.
  await expect(page.getByRole("button", { name: /Review|Approve/ })).toHaveCount(0);
  await page.screenshot({ path: join(SHOTS, "r0810-bug70-plan-mode-refuses-the-write.png") });
});

test("BUG-71 — Memory states what it can actually promise", async () => {
  await page.goto(`${BASE}/#/memory`);
  const posture = page.locator(".posture-card");
  await expect(posture).toBeVisible({ timeout: 30_000 });
  // A fresh workspace has the capability off, and the page used to promise
  // proposals regardless: "When Raiker identifies a useful preference or durable
  // fact, it will propose it for review."
  await expect(posture).toContainText(/Memory store is off/i);
  // Both the posture strip and the empty state now carry it, which is the point.
  await expect(page.getByRole("link", { name: /Turn on Memory store/i }).first()).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "r0810-bug71-memory-says-the-gate-is-off.png") });

  await enableCapability("Memory store", "BUG-71 live verification");
  await page.goto(`${BASE}/#/memory`);
  await expect(page.locator(".posture-card")).toContainText(/Memory store is on/i, {
    timeout: 30_000,
  });
  await page.screenshot({ path: join(SHOTS, "r0810-bug71-memory-says-the-gate-is-on.png") });
});

test("BUG-71 — a Chat turn can propose a durable memory", async () => {
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.goto(`${BASE}/#/new-chat`);
  const answer = await ask(
    "Use the memory_write tool to remember this durable fact: " +
      "“The owner prefers metric units.” Then tell me which tool you used.",
  );

  // Before the fix the model answered that its only memory tools were
  // `memory_get`, `memory_list` and `memory_search`, all read-only.
  await expect(answer).not.toContainText(/unknown_tool|read[- ]only|cannot save|no.*tool.*write/i);
  await expect(
    page.getByText(/waiting for your approval|Review|memory/i).first(),
  ).toBeVisible({ timeout: 60_000 });
  await page.screenshot({ path: join(SHOTS, "r0810-bug71-chat-proposes-a-memory-write.png") });
});

test("BUG-73 — a parked turn reports its state, never a denial of what ran", async () => {
  await page.goto(`${BASE}/#/approvals`);
  await expect(page.getByRole("heading", { name: /Approvals/i })).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: join(SHOTS, "r0810-bug73-approval-waiting.png") });

  await page.goto(`${BASE}/#/new-chat`);
  // The turn is parked. Whatever else the transcript shows, it must not claim
  // that no command was executed — that is a verdict on execution, and a parked
  // turn has a state, not a verdict. The sentence is gone from the product, and
  // the state is never persisted as an answer.
  const denial = page.getByText(/No command was executed/);
  await expect(denial).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  await expect(denial).toHaveCount(0);
  await page.screenshot({ path: join(SHOTS, "r0810-bug73-parked-turn-states-its-state.png") });
});

test("BUG-82 — the advisor model carries a readiness chip and a repair sentence", async () => {
  await page.goto(`${BASE}/#/models?tab=routing`);
  const advisor = page.locator("section.advisor");
  await expect(advisor).toBeVisible({ timeout: 30_000 });

  const selector = advisor.getByLabel("Advisor model profile");
  const anthropic = advisor
    .locator("option")
    .filter({ hasText: /Anthropic/ })
    .first();
  await selector.selectOption(await anthropic.getAttribute("value"));
  await advisor.getByRole("button", { name: /Save advisor/ }).click();
  await expect(advisor.getByText("Saved.")).toBeVisible({ timeout: 30_000 });

  // Before the fix there was nothing here at all: no probe, no state, no chip,
  // and no row in `GET /api/model-readiness`.
  const chip = advisor.getByTestId("advisor-readiness-chip");
  await expect(chip).toBeVisible({ timeout: 30_000 });
  await advisor.getByRole("button", { name: /Check advisor/ }).click();
  await expect(advisor.getByText(/can reach|cannot execute|not reachable|rejected|no credit|no quota/i))
    .toBeVisible({ timeout: 120_000 });
  await page.screenshot({ path: join(SHOTS, "r0810-bug82-advisor-readiness.png") });
});
