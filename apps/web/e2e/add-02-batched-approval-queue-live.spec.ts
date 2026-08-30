/**
 * ADD-02 against a running `raiker-web` — the evidence behind that entry.
 *
 * The scenario is one turn in which the model proposes **three** file writes in a
 * single batch. Before ADD-02 the owner decided the first one and the other two
 * were dropped with an event; the whole point of this run is to watch the same
 * turn walk all three, one decision at a time, through the shipped UI.
 *
 * **On the model backend.** This spec drives a real `raiker-web` — its own
 * orchestrator, broker, policy engine, approvals inbox, suspended-turn store and
 * resume endpoints — but the provider behind it is a local OpenAI-compatible
 * stub (`127.0.0.1:8811`) rather than a hosted model, and the spec says so
 * rather than implying otherwise. That is deliberate: what ADD-02 changes is how
 * the runtime handles a multi-mutation batch, and a hosted model does not
 * reliably emit the same batch twice. The stub guarantees the input; everything
 * downstream of it is the shipped product.
 *
 * Prerequisites:
 *   1. `python apps/web/e2e/fixtures/stub_model.py 8811` (the batching model)
 *   2. `python apps/api/main.py --workspace <ws> --port 8765 --no-browser`
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { checkModelReady, hostedProviderCard, signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Batched-approval-queue-1!";
const STUB_ENDPOINT = process.env.RAIKER_LIVE_STUB_ENDPOINT ?? "http://127.0.0.1:8811/v1";
const MODEL = "raiker-batch-stub";

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

/** The pending approval the batch is currently stopped on. */
function pendingRow(target: Page) {
  return target.locator("table.table tbody tr").first();
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  await signIn(page);
});

test.afterAll(async () => await context?.close());

test("the batching model is connected through the product UI", async () => {
  test.setTimeout(180_000);
  const card = await hostedProviderCard(page, BASE, "OpenAI-compatible");
  await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
  await page.getByRole("button", { name: /Advanced: custom endpoint/ }).click();
  await page.getByPlaceholder("https://…").fill(STUB_ENDPOINT);
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });

  await card.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = card.getByLabel("Available models");
  await expect(catalogue).toBeVisible({ timeout: 60_000 });
  await catalogue.selectOption(MODEL);
  await card.getByRole("button", { name: "Use model" }).click();
  // The card shows the pinned model in its display form, not its raw identifier.
  await expect(card.locator("code").filter({ hasText: /Raiker Batch Stub/i })).toBeVisible({
    timeout: 30_000,
  });
  await checkModelReady(page, await hostedProviderCard(page, BASE, "OpenAI-compatible"));
});

test("a three-mutation batch parks as decision 1 of 3, not as one call and two losses", async () => {
  test.setTimeout(240_000);
  await page.goto(`${BASE}/#/new-chat`);
  await page
    .getByPlaceholder("How can I help you today?")
    .fill("Write one.md, two.md and three.md.");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // The transcript states which decision of the batch it is waiting on, so the
  // owner reads three approvals as one plan rather than as a repeated proposal.
  await expect(
    page.getByRole("main").getByText(/decision 1 of 3/i),
  ).toBeVisible({ timeout: 180_000 });
  await capture(page, join(SHOTS, "add-02-chat-batch-decision-1-of-3.png"));

  await page.goto(`${BASE}/#/approvals`);
  await expect(pendingRow(page).getByText(/decision 1 of 3/i)).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "add-02-approvals-decision-1-of-3.png"));
});

/**
 * Wait for the inbox to settle on a given decision of the batch.
 *
 * Deliberately not a race against a single button. Continuing a parked turn is
 * *already* the owner's from anywhere — this tab's **Continue the turn**, the
 * conversation's own cross-tab watcher (BUG-24), another window — and exactly
 * one of them wins by design (`claim_suspended_turn`). Asserting the inbox
 * state rather than which button ran the continuation tests what ADD-02
 * actually promises: the batch advances to its next decision.
 */
async function settlesOnDecision(target: Page, label: RegExp) {
  await expect(async () => {
    await target.getByRole("button", { name: "Refresh approvals" }).click();
    await expect(pendingRow(target).getByText(label)).toBeVisible({ timeout: 5_000 });
  }).toPass({ timeout: 180_000 });
}

test("approving the first decision advances the queue to the second", async () => {
  test.setTimeout(240_000);
  await page.goto(`${BASE}/#/approvals`);
  await pendingRow(page).getByRole("button", { name: /review/i }).click();

  // The review pane names the batch before the decision is made.
  await expect(page.locator("section.detail").getByText(/decision 1 of 3/i)).toBeVisible();
  await capture(page, join(SHOTS, "add-02-approval-detail-batch.png"));

  await page.getByRole("button", { name: /approve/i }).first().click();
  // The banner says what continuing will actually do: two more decisions.
  await expect(page.getByText(/2 more calls from the same batch/i)).toBeVisible({
    timeout: 30_000,
  });
  await capture(page, join(SHOTS, "add-02-resume-banner-two-queued.png"));

  await page.getByRole("button", { name: /continue the turn/i }).click();
  // Continuing lands on the *next* call of the same batch, without going back
  // to the model for a call it has already proposed.
  await settlesOnDecision(page, /decision 2 of 3/i);
  await capture(page, join(SHOTS, "add-02-approvals-decision-2-of-3.png"));
});

test("rejecting the second decision skips its call and offers the third", async () => {
  test.setTimeout(240_000);
  await page.goto(`${BASE}/#/approvals`);
  await pendingRow(page).getByRole("button", { name: /review/i }).click();
  await expect(page.locator("section.detail").getByText(/decision 2 of 3/i)).toBeVisible();

  await page.getByRole("button", { name: /^(Deny|Reject)/i }).first().click();
  await expect(page.getByText(/1 more call from the same batch/i)).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: /continue the turn/i }).click();

  // A refusal is a decision about one call. The third is still the owner's to
  // make — the batch is not abandoned because one part of it was declined.
  await settlesOnDecision(page, /decision 3 of 3/i);
  await capture(page, join(SHOTS, "add-02-approvals-decision-3-of-3.png"));
});

test("the turn finishes once the last decision is made", async () => {
  test.setTimeout(240_000);
  await page.goto(`${BASE}/#/approvals`);
  await pendingRow(page).getByRole("button", { name: /review/i }).click();
  await expect(page.locator("section.detail").getByText(/decision 3 of 3/i)).toBeVisible();
  await page.getByRole("button", { name: /approve/i }).first().click();
  await page.getByRole("button", { name: /continue the turn/i }).click();

  // Every call of the batch reached a decision, so nothing is left waiting —
  // the state that used to be reached by dropping two calls on the floor.
  await expect(async () => {
    await page.goto(`${BASE}/#/approvals`);
    await expect(page.getByText(/nothing waiting on you/i)).toBeVisible({ timeout: 5_000 });
  }).toPass({ timeout: 180_000 });
  await capture(page, join(SHOTS, "add-02-batch-completed.png"));

  // And the refusal is recorded as its own decision — the second of three —
  // rather than as the batch failing.
  await page.getByRole("tab", { name: "denied" }).click();
  await expect(page.getByText(/decision 2 of 3/i).first()).toBeVisible({ timeout: 30_000 });
});
