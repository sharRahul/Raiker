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
 * The suite is **re-runnable over the same workspace**: the scenarios that are
 * about a capability's off state turn it off themselves rather than assuming a
 * pristine install, which is what made the BUG-69 spec a once-per-workspace run
 * (BUG-84). Leave about a minute between consecutive runs, though — a scripted
 * pass makes more governed reads per minute than a person does and will meet the
 * runtime's own 120-request limiter, which is the limiter working rather than a
 * defect (the UI names it; see FIXED-160).
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { refreshHostedReadiness, signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Round-0810-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

/**
 * BUG-229 — sign in through the one shared helper.
 *
 * Every spec used to carry its own copy, and each copy encoded an assumption
 * about the *state* of the instance — usually the empty-workspace greeting —
 * that had nothing to do with what the spec asserts. A suite then passed on a
 * fresh instance and failed at its first step on a used one.
 */
async function signIn(target: Page) {
  await signInAsOwner(target, BASE, { user: "owner", password: PASSWORD });
}

/** Send one prompt in Chat and wait for *this* turn to finish. */
async function ask(prompt: string) {
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  const before = await page.locator(".message-bubble-raiker").count();
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
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

/**
 * Turn a capability off if it is on, so a scenario about the *off* state can be
 * re-run over a workspace an earlier run already changed.
 *
 * The alternative — requiring a fresh workspace — is what makes a live suite
 * runnable exactly once, which is the ergonomics defect BUG-84 records for the
 * BUG-69 spec. Driving both directions is also better evidence: it shows the
 * page tracking the gate rather than happening to agree with it.
 */
async function disableCapability(label: string, reason: string) {
  const card = await openCapability(label);
  const turnOff = card.getByRole("button", { name: "Turn off" });
  if (!(await turnOff.isVisible().catch(() => false))) return;
  await turnOff.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await dialog.getByLabel("Reason (required)").fill(reason);
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
  await expect(page.getByText(`Disabled ${label}.`)).toBeVisible({ timeout: 30_000 });
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

/**
 * Build's posture is one chip and one menu (it was three side-by-side buttons),
 * so choosing a mode is: open the chip, click the option.
 */
function modeTrigger(target: Page) {
  return target.getByRole("button", { name: /^How much Raiker may do this turn:/ });
}

async function pickMode(
  target: Page,
  label: "Plan" | "Edit" | "Auto",
  options: { keepMenuOpen?: boolean } = {},
) {
  await modeTrigger(target).click();
  await expect(target.getByRole("menu", { name: "Mode" })).toBeVisible();
  if (options.keepMenuOpen) return;
  await target.getByRole("menuitemradio", { name: new RegExp(`^${label}`) }).click();
  await expect(modeTrigger(target)).toHaveAccessibleName(
    `How much Raiker may do this turn: ${label}`,
  );
}

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
  // no dialog, no reason, and no acknowledgement. Build now *opens* in Auto, so
  // the assertion is that arriving in it wrote nothing — and the composer says
  // what the owner's standing permissions actually amount to.
  await expect(modeTrigger(page)).toHaveAccessibleName(
    "How much Raiker may do this turn: Auto",
  );
  await expect(page.getByText(/Change in Permissions/)).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: join(SHOTS, "r0810-bug70-build-auto-changes-nothing-standing.png") });

  await pickMode(page, "Plan");
  // The mode menu is where a posture is explained, and it says whose it is.
  await pickMode(page, "Plan", { keepMenuOpen: true });
  await expect(page.getByRole("menu", { name: "Mode" })).toContainText(
    /applies to this conversation's turns only/i,
  );
  await page.keyboard.press("Escape");
  page.off("request", listener);

  expect(requests, "a composer chip must not write standing decision modes").toEqual([]);
  expect(await standingWriteModes()).toEqual(before);
  await page.screenshot({ path: join(SHOTS, "r0810-bug70-permissions-unchanged.png") });
});

test("BUG-70 — Plan really refuses the write it is presented as refusing", async () => {
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.goto(`${BASE}/#/build`);
  await pickMode(page, "Plan");

  const composer = page.getByLabel("Describe the change");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(
    "Use the write_file tool to create plan-mode-probe.md containing the word BLOCKED. " +
      "If the tool is refused, say exactly what the refusal was.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });

  // The posture is enforced by the runtime, not by prompt wording: the turn
  // never parks for an approval, because the call is refused outright.
  await expect(page.getByRole("button", { name: /Review|Approve/ })).toHaveCount(0);
  await page.screenshot({ path: join(SHOTS, "r0810-bug70-plan-mode-refuses-the-write.png") });
});

test("BUG-71 — Memory states what it can actually promise", async () => {
  // Both directions, driven from Permissions, so the claim is that the page
  // *tracks* the gate rather than that it agreed with it once.
  await disableCapability("Memory store", "BUG-71 live verification — off state");

  await page.goto(`${BASE}/#/memory`);
  const posture = page.locator(".posture-card");
  await expect(posture).toBeVisible({ timeout: 30_000 });
  // With the capability off the page used to promise proposals anyway: "When
  // Raiker identifies a useful preference or durable fact, it will propose it
  // for review."
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

  // Reopen the parked conversation itself. Checking a *fresh* chat would prove
  // nothing — the defect was a durable claim inside the conversation that had
  // parked, and it survived a reload, which is what made it worth a bug.
  const openParkedConversation = async () => {
    await page.goto(`${BASE}/#/new-chat`);
    const recent = page.getByRole("link", { name: /memory_write/i }).first();
    await expect(recent).toBeVisible({ timeout: 30_000 });
    await recent.click();
    await expect(page.getByText(/Waiting for your decision/i).first()).toBeVisible({
      timeout: 30_000,
    });
  };

  await openParkedConversation();
  // Whatever else the transcript shows, it must not claim that no command was
  // executed — that is a verdict on execution, and a parked turn has a state,
  // not a verdict. The sentence is gone from the product entirely, and the
  // state it replaced is never persisted as an answer.
  const denial = page.getByText(/No command was executed/);
  await expect(denial).toHaveCount(0);

  // Reload and come back to it. The bearer token is held in memory only — never
  // localStorage or sessionStorage — so a reload really does end the session and
  // the owner signs in again. Surviving that is exactly what the false claim
  // used to do.
  await page.reload();
  await signIn(page);
  await openParkedConversation();
  await expect(denial).toHaveCount(0);
  await page.screenshot({ path: join(SHOTS, "r0810-bug73-parked-turn-states-its-state.png") });
});

test("BUG-82 — the advisor model carries a readiness chip and a repair sentence", async () => {
  // Reach Routing the way a person does — open Models, then pick the tab.
  //
  // A scripted suite makes more governed reads per minute than a person does and
  // routinely meets the runtime's own 120-request limiter by this point. That is
  // the limiter working, not a defect: the page names it and offers Refresh
  // (FIXED-160), so this waits it out and retries rather than reporting a
  // problem the product does not have.
  const advisor = page.locator("section.advisor");
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await page.goto(`${BASE}/#/models?tab=routing`);
    const routing = page.getByRole("tab", { name: "Routing" });
    if (await routing.isVisible({ timeout: 15_000 }).catch(() => false)) {
      if ((await routing.getAttribute("aria-selected")) !== "true") await routing.click();
      if (await advisor.isVisible({ timeout: 10_000 }).catch(() => false)) break;
    }
    await page.waitForTimeout(20_000);
  }
  await expect(advisor).toBeVisible({ timeout: 30_000 });

  const selector = advisor.getByLabel("Advisor model profile");
  const anthropic = advisor
    .locator("option")
    .filter({ hasText: /Anthropic/ })
    .first();
  await selector.selectOption(await anthropic.getAttribute("value"));
  // Save is correctly disabled when the selection already matches what is
  // stored, so a re-run over the same workspace has nothing to save.
  const save = advisor.getByRole("button", { name: /Save advisor/ });
  if (await save.isEnabled()) {
    await save.click();
    await expect(advisor.getByText("Saved.")).toBeVisible({ timeout: 30_000 });
  }

  // Before the fix there was nothing here at all: no probe, no state, no chip,
  // and no row in `GET /api/model-readiness`.
  const chip = advisor.getByTestId("advisor-readiness-chip");
  await expect(chip).toBeVisible({ timeout: 30_000 });
  // Pressing Check runs the same exact-model readiness check a provider card
  // runs, against the model the advisor would actually call. The claim is that
  // a verdict is produced and shown — not which verdict, which is a property of
  // the account rather than of the product.
  await advisor.getByRole("button", { name: /Check advisor/ }).click();
  await expect(advisor.getByRole("button", { name: /Check advisor/ })).toBeEnabled({
    timeout: 120_000,
  });
  await expect(chip).not.toHaveText(/Checking…/, { timeout: 120_000 });
  await expect(chip).not.toHaveText(/Not checked/, { timeout: 120_000 });
  await page.screenshot({ path: join(SHOTS, "r0810-bug82-advisor-readiness.png") });
});
