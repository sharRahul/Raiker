import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";

/**
 * BUG-302 — an event's summary says what that event did.
 *
 * `sessions-reopened-typed-answer.png` is what this replaces: four near-identical
 * rows of `raiker:table {"caption": …` under a rendered table that already said
 * the same thing legibly. The events were right to be there and right to be
 * verbatim; what was wrong is that four of them described themselves with one
 * borrowed sentence.
 *
 * Live, and with a real answer, because the defect only appears once a turn has
 * produced something long enough to be borrowed. A unit test can hold the
 * sentences apart; only a real turn proves the inspector stops repeating one.
 *
 * Preconditions:
 *   1. `raiker-web` on 127.0.0.1:8765
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (entered through the UI)
 */
const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-09-18-round");
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";
const MODEL_LABEL = /Haiku 4\.5/;

test("four closing events describe four different things", async ({ page }) => {
  test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set for this round.");
  test.setTimeout(240_000);

  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });

  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill("In two sentences, say what a governed audit log is for.");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // The turn having *closed* is the precondition, not the first token of it:
  // the three events this is about are written when it closes, and inspecting a
  // running turn measures a list that has not been produced yet.
  const answer = page.locator(".message-bubble-raiker").last();
  await expect(answer).toBeVisible({ timeout: 240_000 });
  await expect
    .poll(async () => ((await answer.textContent()) ?? "").trim().length, {
      timeout: 240_000,
      intervals: [1_000],
    })
    .toBeGreaterThan(40);

  await page.goto(`${BASE}/#/observe?tab=sessions`);
  // The row opens the session and the turn button opens the turn. Both are the
  // inspector's own controls, so the spec drives the page the way an owner
  // auditing a turn does rather than by loading a deep link.
  await page.locator("tr.row-btn .session-title").first().click();
  await page.locator("button.turn-btn").first().click();

  const events = page.locator("ul.events li");
  await expect(events.first()).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "sessions-event-summaries.png"));

  const summaries = await page.locator("ul.events li .ev-summary").allInnerTexts();
  const nonEmpty = summaries.map((line) => line.trim()).filter((line) => line !== "");

  // The rule, not the wording: no two events in one turn say the same thing.
  const repeated = nonEmpty.filter(
    (line, index) => nonEmpty.indexOf(line) !== index && line.length > 24,
  );
  expect(repeated).toEqual([]);

  // And the three that used to borrow the answer now say what they did.
  const joined = nonEmpty.join("\n");
  expect(joined).toContain("Turn closed as completed.");
  expect(joined).toContain("Recorded a restore point for this turn at CLOSED.");
});
