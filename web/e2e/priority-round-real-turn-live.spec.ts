import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import {
  checkModelReady,
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
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";

test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set");

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
  test.setTimeout(600_000);
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
  await expect(page.getByText("Not installed on this machine").first()).toBeVisible();
  await capture(page, join(SHOTS, "fixed-365-meter-after-connecting-live.png"));

  // FIXED-367 — a task owns a conversation, and every cycle runs in it.
  await page.goto(`${BASE}/#/tasks`);
  await page.getByLabel("Task title").fill("Overnight research");
  await page
    .getByLabel("Instructions")
    .fill("Reply with exactly the word ACKNOWLEDGED and nothing else.");
  await page.getByRole("button", { name: /^Create (task|routine)$/ }).click();
  const card = page.locator("article.task").filter({ hasText: "Overnight research" });
  await expect(card).toBeVisible({ timeout: 60_000 });

  await card.getByRole("button", { name: "Run now" }).click();
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
  await expect(page.getByRole("link", { name: /Overnight research/ })).toBeVisible({
    timeout: 60_000,
  });
  await page.getByRole("button", { name: "Routines" }).click();
  await expect(page.getByRole("link", { name: /Overnight research/ })).toBeVisible();
  await capture(page, join(SHOTS, "fixed-368-routine-on-the-board-live.png"));
});
