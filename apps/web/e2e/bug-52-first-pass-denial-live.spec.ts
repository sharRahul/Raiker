/**
 * BUG-52 against a running `raiker-web` — the evidence behind that entry.
 *
 * ADD-02 made a policy refusal *inside a drained queue* skip its own call and
 * let the batch carry on. A refusal in the batch's **first pass** did neither:
 * it ended the turn and dropped the calls behind it. The same refusal therefore
 * produced two different outcomes depending only on whether the owner happened
 * to have made a decision earlier in the same batch.
 *
 * Both scenarios here put the refusal *first*, with no approval ahead of it:
 *
 *  1. A read-only batch — `read_file(../escape.md)` then `list_directory(".")`.
 *     The turn used to end at the refused read. It now answers, and says which
 *     call was refused.
 *  2. A batch that also contains writes — `read_file(../escape.md)`,
 *     `write_file(one.md)`, `write_file(three.md)`. The turn used to end at the
 *     refused read and drop both writes. It now reaches the write's approval as
 *     **decision 2 of 3**, with the third call queued behind it.
 *
 * **On the model backend.** This spec drives a real `raiker-web` — its own
 * orchestrator, broker, policy engine, approvals inbox, suspended-turn store and
 * resume endpoints — but the provider behind it is a local OpenAI-compatible
 * stub (`127.0.0.1:8811`) rather than a hosted model, and the spec says so
 * rather than implying otherwise. What BUG-52 changes is how the runtime handles
 * one specific batch shape, and a hosted model does not reliably emit the same
 * batch twice. The stub guarantees the input; everything downstream is shipped.
 *
 * Prerequisites:
 *   1. `python apps/web/e2e/fixtures/stub_model.py 8811` (the batching model, as ADD-02)
 *   2. `python apps/api/main.py --workspace <ws> --port 8765 --no-browser`
 *      with `RAIKER_MODEL_EGRESS_ALLOWLIST=127.0.0.1`
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { checkModelReady, hostedProviderCard, signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
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
  await signInAsOwner(target, BASE);
}

/**
 * The refused call's own transcript row, for the most recent turn.
 *
 * BUG-206 slice E replaced the "Policy refused …" card that used to sit at the
 * bottom of the turn. It existed because a refused call was the *only* call the
 * transcript could speak about; now that every call has a row, a refused one is
 * that same row in a refused state, in the place it was refused.
 */
function refusedRow(target: Page) {
  return target.locator('.tool-row[data-state="refused"]').last();
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
  await expect(card.locator("code").filter({ hasText: /Raiker Batch Stub/i })).toBeVisible({
    timeout: 30_000,
  });
  await checkModelReady(page, await hostedProviderCard(page, BASE, "OpenAI-compatible"));
});

test("a refused first call no longer ends the turn — the read behind it still answers", async () => {
  test.setTimeout(240_000);
  await page.goto(`${BASE}/#/new-chat`);
  await page
    .getByPlaceholder("How can I help you today?")
    .fill("Read ../escape.md and list the workspace.");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // The turn answers. Before BUG-52 it ended on the refused read with
  // "Action denied by policy" and the listing behind it was dropped.
  await expect(page.getByRole("main").getByText(/policy refused that one call/i)).toBeVisible({
    timeout: 180_000,
  });
  // BUG-53: these are two model requests in one turn. They must remain two
  // paragraphs, while deltas within either request still join without spaces.
  const answer = page.locator(".message-bubble-raiker").last();
  await expect(answer.locator(".markdown > p")).toHaveCount(2);
  await expect(answer.locator(".markdown > p").first()).toContainText("inspect both locations");
  await expect(answer.locator(".markdown > p").last()).toContainText(
    "The policy refused that one call",
  );

  // And the refusal is stated in the transcript, named to its own call, so a
  // reader does not take it as a verdict on everything the batch asked for.
  const row = refusedRow(page);
  await expect(row).toBeVisible({ timeout: 30_000 });
  await expect(row.locator(".tool-label")).toHaveText("Read file");
  await expect(row.locator(".tool-reason")).toContainText("refused");
  // The card it replaced is gone, and the other call in the batch kept its own
  // row rather than being folded into a summary of the refusal.
  await expect(page.locator(".refusal-card")).toHaveCount(0);
  await expect(page.locator('.tool-row[data-state="success"]')).toHaveCount(1);
  await capture(page, join(SHOTS, "bug-52-chat-refusal-does-not-end-the-turn.png"));
});

test("a refusal ahead of a write reaches decision 2 of 3 instead of dropping both writes", async () => {
  test.setTimeout(240_000);
  await page.goto(`${BASE}/#/new-chat`);
  await page
    .getByPlaceholder("How can I help you today?")
    .fill("Run the batch: read ../escape.md, then write one.md and three.md.");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // The refused read is call 1 of 3 and there is no approval ahead of it. The
  // turn now carries on to the write's approval, which is decision 2 of 3.
  await expect(page.getByRole("main").getByText(/decision 2 of 3/i)).toBeVisible({
    timeout: 180_000,
  });
  await expect(refusedRow(page).locator(".tool-label")).toHaveText("Read file", {
    timeout: 30_000,
  });
  await capture(page, join(SHOTS, "bug-52-chat-decision-2-of-3-after-a-refusal.png"));

  await page.goto(`${BASE}/#/approvals`);
  const pendingRow = page.locator("table.table tbody tr").first();
  await expect(pendingRow.getByText(/decision 2 of 3/i)).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "bug-52-approvals-decision-2-of-3.png"));
});

test("the third call is still the owner's to decide", async () => {
  test.setTimeout(240_000);
  await page.goto(`${BASE}/#/approvals`);
  await page.locator("table.table tbody tr").first().getByRole("button", { name: /review/i }).click();
  await expect(page.locator("section.detail").getByText(/decision 2 of 3/i)).toBeVisible();
  await page.getByRole("button", { name: /approve/i }).first().click();
  // The banner counts what is genuinely left: the refused read is decided, the
  // third write is not.
  await expect(page.getByText(/1 more call from the same batch/i)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /continue the turn/i }).click();

  await expect(async () => {
    await page.goto(`${BASE}/#/approvals`);
    await expect(
      page.locator("table.table tbody tr").first().getByText(/decision 3 of 3/i),
    ).toBeVisible({ timeout: 5_000 });
  }).toPass({ timeout: 180_000 });
  await capture(page, join(SHOTS, "bug-52-approvals-decision-3-of-3.png"));
});
