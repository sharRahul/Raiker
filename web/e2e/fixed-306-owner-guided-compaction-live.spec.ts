/**
 * **Summarise up to here**, against a real conversation and a real model (FIXED-306).
 *
 * The unit tests prove the plan is inclusive, the route writes the record the
 * turn path would have written, and a `PreCompact` refusal stops the owner's
 * compaction too. What they cannot prove is the thing this control has to be
 * true about on screen: that summarising a range **removes nothing**.
 *
 * So this spec sends two real turns, summarises up to the first, and then asserts
 * both halves of the claim in the place an owner would check them — the summary
 * happened, and every turn is still in the transcript afterwards.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
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
  await signInAsOwner(target, BASE);
}

async function send(prompt: string) {
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  await signIn(page);
});

test.afterAll(async () => {
  await context?.close();
});

test("an owner summarises a range, and the transcript keeps every turn", async () => {
  test.setTimeout(420_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");

  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });

  await page.goto(`${BASE}/#/new-chat`);
  await send("Reply with exactly the word: alpha.");
  await send("Reply with exactly the word: bravo.");

  // Both exchanges are on screen before anything is summarised, so the
  // "removes nothing" assertion below has something to be about.
  const firstPrompt = page.getByText("Reply with exactly the word: alpha.").first();
  await expect(firstPrompt).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Reply with exactly the word: bravo.").first()).toBeVisible();

  // The control is on the owner's own message and appears on hover.
  await firstPrompt.hover();
  const summarise = page
    .getByRole("button", { name: "Summarise this conversation up to and including this message" })
    .first();
  await expect(summarise).toBeVisible({ timeout: 30_000 });
  await summarise.click();

  await expect(page.getByText(/Summarised \d+ earlier exchange/)).toBeVisible({
    timeout: 120_000,
  });
  // The half a person would not think to check, and the half that makes the
  // control safe: nothing left the transcript.
  await expect(page.getByText("Nothing was removed from this transcript.")).toBeVisible();
  await expect(page.getByText("Reply with exactly the word: alpha.").first()).toBeVisible();
  await expect(page.getByText("Reply with exactly the word: bravo.").first()).toBeVisible();

  await page.screenshot({
    path: join(SHOTS, "fixed-306-summarise-up-to-here.png"),
  });
});

test("summarising the same point again says so instead of doing it twice", async () => {
  test.setTimeout(240_000);

  const firstPrompt = page.getByText("Reply with exactly the word: alpha.").first();
  await firstPrompt.hover();
  await page
    .getByRole("button", { name: "Summarise this conversation up to and including this message" })
    .first()
    .click();

  // A mark an earlier boundary already covers is a state, not an error: the
  // owner asked for something that is already true.
  await expect(page.getByText("Everything up to that point is already summarised.")).toBeVisible({
    timeout: 120_000,
  });
});
