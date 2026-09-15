import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import {
  checkModelReady,
  chooseModelForTurn,
  connectHostedProvider,
  signInAsOwner,
  useHostedModel,
} from "./hosted-provider";

/**
 * The 2026-09-03 round against a real provider turn.
 *
 * The sweep in `priority-round-2026-09-03-live.spec.ts` proves the surfaces on a
 * host with no model, which is the state FIXED-365 is about. This one connects
 * a real key through the UI and drives the parts that need a model to answer:
 * the honest meter *after* a provider is connected, a task with a thread of its
 * own, and that thread appearing on the board beside the owner's chats.
 *
 * The key comes from the environment. A live spec is evidence, not a place to
 * keep a credential.
 */

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "plans", "screenshots", "working");
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";

test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set");

/** This round's routine, named so it cannot be confused with an earlier one. */
const ROUTINE = `Overnight research ${Date.now().toString(36)}`;

/**
 * BUG-272 — found by this spec, on its first run against the supplied key.
 *
 * The key is *identity-linked*: valid, with nothing to rotate, and refused with
 * HTTP 400 because Anthropic requires a workspace named on every request made
 * with one. Raiker reported `provider_http_error:http_400` — a code with no
 * repair in it, which is the shape FIXED-355 removed from a rejected key.
 *
 * This runs on any key. With an identity-linked one it asserts the new answer;
 * with an ordinary one the model becomes ready and the test below covers it.
 */
test("a refused key says what is wrong with it, not which status came back", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  const card = await connectHostedProvider(page, BASE, "Anthropic", "API key", KEY);
  await checkModelReady(page, card);

  // Whatever this key turns out to be, the card must not read as a bare status.
  await expect(card.getByText(/provider_http_error/)).toHaveCount(0);
  await capture(page, join(SHOTS, "bug-272-provider-answer-live.png"), card);
});

test("a connected provider makes the meter say so, and a routine gets a thread", async ({
  page,
}) => {
  // Connecting a provider, pinning a model, creating a task and waiting for the
  // scheduler to claim and complete a real governed cycle is several minutes of
  // real work before the first assertion about the thread can be made.
  test.setTimeout(900_000);
  await signInAsOwner(page, BASE);

  // FIXED-365 — the meter counts what is actually set up. With nothing
  // connected it said "No model ready"; connecting one is what should move it,
  // not a model string in a config file.
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "API key",
    key: KEY,
    model: MODEL,
  });
  await page.goto(`${BASE}/#/models`);
  await expect(page.getByText(/1 model (ready|set up)/)).toBeVisible({ timeout: 60_000 });
  // And the undetected local runtime is still honest about itself.
  //
  // **Found live on 2026-09-15.** This looked for the sentence on whichever tab
  // `#/models` opens, which is Overview. BUG-270's line lives in the **On this
  // device** section, and that section is on **Add model** — so the assertion
  // waited out its timeout on a page that was never going to carry it, and read
  // as a product that had stopped being honest about a missing runtime. Same
  // class as BUG-295 and FIXED-534: the drift is in the harness.
  await page.goto(`${BASE}/#/models?tab=add`);
  await expect(page.getByText("Not installed on this machine").first()).toBeVisible({
    timeout: 60_000,
  });
  await capture(page, join(SHOTS, "fixed-365-meter-after-connecting-live.png"));

  // FIXED-367 — a task owns a conversation, and every cycle runs in it.
  //
  // **Found live on 2026-09-15.** This filled a **Task title** and an
  // **Instructions** field, which is the form COMPOSER-10 replaced: planning
  // work is one instruction now, and the title is derived from it
  // ([FIXED-470](../../docs/plans/FIXED_ITEMS.md)). The spec sat on a label the
  // product had stopped printing until its ten-minute timeout — the same
  // harness drift BUG-295 and FIXED-534 record, and the reason this scenario
  // stayed unrun for one round longer than the key did.
  await page.goto(`${BASE}/#/tasks`);
  const instruction = page.getByLabel("What should Raiker do?");
  await expect(instruction).toBeVisible({ timeout: 60_000 });
  // BUG-250 — a name this round owns. A shared workspace keeps what earlier
  // rounds made, and "Overnight research" resolved to three threads here on the
  // run that found this: two leftovers and the one under test. A spec that has
  // to disambiguate its own subject is a spec that can pass on somebody else's
  // evidence.
  await instruction.fill(
    `${ROUTINE}. Reply with exactly the word ACKNOWLEDGED and nothing else.`,
  );
  // A **routine**, not a one-off, and deliberately: this entry's claim is about
  // *a routine's cycle* running in its own conversation, and a one-off leaves
  // Open work the moment it completes — so the card the Thread link lives on is
  // gone before the cycle that would put a turn in the thread has landed. A
  // routine is rescheduled rather than completed, so it stays on the board with
  // its thread, which is the state an owner actually reads.
  await page.getByRole("button", { name: "Routine", exact: true }).click();
  await page.getByRole("button", { expanded: false, name: /Runs|Every|Once/ }).click();
  const firstRun = page.getByLabel("First run");
  await expect(firstRun).toBeVisible({ timeout: 30_000 });
  // A minute ago, so the scheduler's next tick finds it due rather than the
  // round waiting out an hour for a slot.
  const due = new Date(Date.now() - 60_000);
  const pad = (value: number) => String(value).padStart(2, "0");
  await firstRun.fill(
    `${due.getFullYear()}-${pad(due.getMonth() + 1)}-${pad(due.getDate())}T` +
      `${pad(due.getHours())}:${pad(due.getMinutes())}`,
  );
  // BUG-292 — pinning a model and choosing the one that answers are two
  // decisions, and the composer is right to refuse until the second is made.
  await chooseModelForTurn(page, /Haiku 4\.5/i, "Plan work");
  await page.getByRole("button", { name: /^Create (task|routine)$/ }).click();
  const card = page.locator("article.task").filter({ hasText: ROUTINE });
  await expect(card).toBeVisible({ timeout: 60_000 });

  // **Found live on 2026-09-15.** This pressed **Run now**, which a task created
  // on the *Task* cadence never offers: that cadence is "runs now", so the task
  // is already due and the card's recovery button is for a *parked* one. The
  // click waited out the whole test timeout for a control whose absence is the
  // product working. Nothing needs pressing — the scheduler claims it on its
  // next tick, which is the thing under test.
  const runNow = card.getByRole("button", { name: "Run now" });
  if (await runNow.isVisible().catch(() => false)) await runNow.click();
  // The thread link appears once the cycle has written a turn into it, which is
  // the property under test: the run happened *in the conversation*.
  const thread = card.getByRole("link", { name: /Thread/ });
  await expect(thread).toBeVisible({ timeout: 300_000 });
  await capture(page, join(SHOTS, "fixed-367-task-thread-link-live.png"), card);

  await thread.click();
  // Opening it lands in Chat on that conversation, with the cycle in it.
  await expect(page).toHaveURL(/#\/new-chat\?session=/);
  await expect(page.getByText(/ACKNOWLEDGED/i).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "fixed-367-routine-thread-in-chat-live.png"));

  // FIXED-368 — and the same thread is on the board, beside the owner's chats.
  await page.goto(`${BASE}/#/search-chat`);
  await expect(page.getByRole("link", { name: new RegExp(ROUTINE) })).toBeVisible({
    timeout: 60_000,
  });
  await page.getByRole("button", { name: "Routines" }).click();
  await expect(page.getByRole("link", { name: new RegExp(ROUTINE) })).toBeVisible();
  await capture(page, join(SHOTS, "fixed-368-routine-on-the-board-live.png"));
});
