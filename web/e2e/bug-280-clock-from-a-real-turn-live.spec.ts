/**
 * BUG-280, the half a host without weather egress can still measure: does a
 * real model answer a relative-time question from Raiker's clock?
 *
 * The 2026-09-07 round proved the whole environment contract against the
 * runtime — the bundle a turn is given, the event it records, the precedence,
 * the DST behaviour, the stale-refresh note, and every governed refusal — and
 * recorded honestly that two halves of it were unmeasured. One was the weather
 * round trip. The other was this: *"no model reasoned from the bundle"*, because
 * that round's key was identity-linked and the host had no local runtime, so no
 * provider on it could complete a turn.
 *
 * The bundle being right is a fact about the orchestrator. The model *using* it
 * is a claim only a real turn can support, and a model with training knowledge
 * of dates is exactly the thing that can make a wrong answer look plausible.
 *
 * **What this deliberately does not assert.** It never hardcodes a date. The
 * expectation is read from `/api/environment` — the same function the
 * orchestrator calls to build the turn's bundle — so the spec measures agreement
 * between the runtime and the model rather than agreement between the model and
 * whatever day the suite happened to be written on.
 *
 * Prerequisites:
 *   1. `raiker-web --workspace <ws> --port 8765 --no-browser` with
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (entered through the UI)
 */
import { expect, test, type Page } from "@playwright/test";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";
const MODEL_LABEL = /Haiku 4\.5/i;

test.describe.configure({ mode: "serial" });

interface Bundle {
  timezone: string;
  timezone_source: string;
  local_date: string;
  day_of_week: string;
}

/** The runtime's own answer, read the way the orchestrator derives it. */
async function clockBundle(page: Page): Promise<Bundle> {
  return page.evaluate(async () => {
    const response = await fetch("/api/environment", { credentials: "same-origin" });
    if (!response.ok) throw new Error(`environment ${response.status}`);
    return (await response.json()) as Bundle;
  });
}

async function setTimezone(page: Page, zone: string): Promise<void> {
  await page.goto(`${BASE}/#/settings?tab=general`);
  const select = page.getByLabel("Time zone");
  await expect(select).toBeVisible({ timeout: 30_000 });
  await select.selectOption(zone);
  await page.getByRole("button", { name: /^Save/ }).click();
  await expect(page.getByText(/Saved/i).first()).toBeVisible({ timeout: 30_000 });
}

/** Send one question in a fresh conversation and return the answer text. */
async function ask(page: Page, question: string): Promise<string> {
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill(question);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const answer = page.locator(".message-bubble-raiker").last();
  await expect(answer).toBeVisible({ timeout: 240_000 });
  // The bubble exists before the stream finishes, so wait for it to stop
  // growing rather than reading a half-written sentence.
  let settled = "";
  await expect
    .poll(
      async () => {
        const now = ((await answer.textContent()) ?? "").trim();
        const unchanged = now.length > 8 && now === settled;
        settled = now;
        return unchanged;
      },
      { timeout: 240_000, intervals: [1_500] },
    )
    .toBe(true);
  return settled;
}

test("a real turn answers today's date from the runtime, not from training", async ({ page }) => {
  test.setTimeout(420_000);
  test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is required for this round.");

  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: /API key/,
    key: ANTHROPIC_KEY,
    model: MODEL,
  });

  await setTimezone(page, "Europe/London");
  const london = await clockBundle(page);
  expect(london.timezone).toBe("Europe/London");
  expect(london.timezone_source).toBe("owner_setting");

  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);

  const answer = await ask(
    page,
    "What is today's date and what day of the week is it? Answer with only the " +
      "date in YYYY-MM-DD form and the day name, nothing else.",
  );

  // The runtime's date and day, in the model's own answer. A model that had
  // answered from training knowledge would name a date from its cutoff.
  expect(answer).toContain(london.local_date);
  expect(answer.toLowerCase()).toContain(london.day_of_week.toLowerCase());
});

test("changing the zone changes the answer, because the clock is the owner's", async ({ page }) => {
  test.setTimeout(420_000);
  test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is required for this round.");

  await signInAsOwner(page, BASE);
  // Far enough that the wall clock is unmistakably different, whichever way the
  // round happens to run.
  await setTimezone(page, "Pacific/Auckland");
  const auckland = await clockBundle(page);
  expect(auckland.timezone).toBe("Pacific/Auckland");

  const answer = await ask(
    page,
    "What time is it right now, and in which time zone? Answer in one short line.",
  );

  // The zone the owner chose, named by the model, from the bundle the runtime
  // derived rather than from anything the model could have guessed.
  expect(answer).toMatch(/Auckland|New Zealand|NZ[DS]T/i);

  // Put it back, so a later spec in the same workspace is not reading somebody
  // else's clock.
  await setTimezone(page, "Europe/London");
});
