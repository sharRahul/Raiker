/**
 * MEM-BRIEF-01 and MEM-MODE-02, against a running host: the Memory Brief, the
 * owner's recall mode, Incognito over it, and what each answer says it used.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `python -m raiker.api.serve --workspace <ws> --port 8765 --no-browser`.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Memory Brief and recall
 * mode"): RT-MEM-01 … RT-MEM-06.
 */
import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import {
  checkModelReady,
  chooseModelForTurn,
  hostedProviderCard,
  keepModelAvailable,
  signInAsOwner,
} from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE, sendTurn } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = "../../docs/screenshots/2026-10-20-memory-brief-recall-mode";
const TEA = "My favourite tea is oolong, brewed short.";
const QUESTION = "Which drink do I like best? Answer with one word.";

async function openRecall(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/memory?tab=recall`);
  await settled(page);
}

async function chooseMode(page: Page, label: RegExp): Promise<void> {
  await openRecall(page);
  const group = page.getByRole("radiogroup", { name: "Recall mode" });
  await group.getByRole("radio", { name: label }).click();
  await expect(group.getByRole("radio", { name: label })).toHaveAttribute("aria-checked", "true", {
    timeout: 30_000,
  });
}

/** Ask in a new chat and wait for the settled answer. */
async function ask(page: Page, text: string): Promise<void> {
  await page.goto(`${BASE}/#/home`);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku|claude/i);
  await sendTurn(page, text);
  await expect(page.locator(".message-bubble-raiker").last()).not.toBeEmpty({ timeout: 180_000 });
  await expect(page.getByRole("button", { name: "Send this message again" }).last()).toBeVisible({
    timeout: 180_000,
  });
}

test("RT-MEM-01 — Anthropic connects through the UI and answers", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    if (WORKSPACE_ID) {
      await page.getByRole("button", { name: "Advanced" }).click();
      await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE_ID);
    }
    await page.locator(".signin-connect").click();
  }
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  await keepModelAvailable(page, card, MODEL);
  const pinned = await hostedProviderCard(page, BASE, "Anthropic");
  await checkModelReady(page, pinned);
  await expect(pinned.getByText(/can reach/i).first()).toBeVisible();
  expect(await page.content()).not.toContain(KEY);
});

test("RT-MEM-02 — an imported memory and the recall mode card", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await openRecall(page);
  const advanced = page.locator("details.advanced");
  if (!(await advanced.evaluate((element) => (element as HTMLDetailsElement).open))) {
    await page.getByText("Advanced memory management").click();
  }
  const file = join(tmpdir(), "mem-brief-live.json");
  writeFileSync(file, JSON.stringify({ memories: [{ text: TEA, scope: "account" }] }));
  await page.locator('.file-button input[type="file"]').setInputFiles(file);
  // A re-run finds the record already stored and offers nothing to import.
  const importOne = page.getByRole("button", { name: /^Import 1 record$/ });
  const already = page.getByText(/already stored/i).first();
  await expect(importOne.or(already)).toBeVisible({ timeout: 30_000 });
  if (await importOne.isVisible()) {
    await importOne.click();
    await expect(page.getByText(/^Imported 1 record/)).toBeVisible({ timeout: 30_000 });
  }
  const group = page.getByRole("radiogroup", { name: "Recall mode" });
  await expect(group.getByRole("radio", { name: /Search when relevant/ })).toHaveAttribute(
    "aria-checked",
    "true",
  );
  await capture(page, `${SHOTS}/01-recall-mode-card.png`, page.locator(".recall-mode-card"));
});

test("RT-MEM-03 — Search when relevant: the answer says Brief + search", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await chooseMode(page, /Search when relevant/);
  await ask(page, "What is my favourite tea? Answer with one word.");
  await expect(page.locator(".message-bubble-raiker").last()).toContainText(/oolong/i);
  const strip = page.getByRole("button", { name: /Remembered \d+.*Brief \+ search/ }).last();
  await expect(strip).toBeVisible({ timeout: 30_000 });
  await strip.click();
  await expect(page.getByText(/Recall mode: Search when relevant · searched sqlite-fts\d/).last()).toBeVisible();
  await capture(page, `${SHOTS}/02-search-answer-strip.png`);
});

test("RT-MEM-04 — Brief only: the brief answers a question that shares no words", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await chooseMode(page, /Brief only/);
  await ask(page, QUESTION);
  await expect(page.locator(".message-bubble-raiker").last()).toContainText(/oolong/i);
  const strip = page.getByRole("button", { name: /Remembered \d+.*Brief only/ }).last();
  await expect(strip).toBeVisible({ timeout: 30_000 });
  await strip.click();
  await expect(page.getByText(/Recall mode: Brief only · no search/).last()).toBeVisible();
  await capture(page, `${SHOTS}/03-brief-only-answer.png`);
});

test("RT-MEM-05 — Off: the answer says memory was off", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await chooseMode(page, /^Off/);
  await ask(page, QUESTION);
  await expect(page.getByText("Memory off for this answer").last()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: /Remembered \d+/ })).toHaveCount(0);
  await capture(page, `${SHOTS}/04-off-answer.png`);
});

test("RT-MEM-06 — Incognito wins over the mode, and the card at 390 px dark", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await chooseMode(page, /Search when relevant/);
  const incognito = page.getByRole("switch", { name: "Incognito session" });
  if ((await incognito.getAttribute("aria-checked")) !== "true") await incognito.click();
  await expect(incognito).toHaveAttribute("aria-checked", "true", { timeout: 30_000 });
  await expect(page.getByText(/no mode recalls anything until you turn it off/i)).toBeVisible();
  await ask(page, "What is my favourite tea? Answer with one word.");
  await expect(page.getByText("Memory not used: Incognito is on").last()).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/05-incognito-answer.png`);

  await page.setViewportSize({ width: 390, height: 900 });
  await page.emulateMedia({ colorScheme: "dark" });
  await openRecall(page);
  const card = page.locator(".recall-mode-card");
  await expect(card).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await capture(page, `${SHOTS}/06-recall-mode-card-390-dark.png`, card);

  // Leave the workspace as the round found it.
  await page.getByRole("switch", { name: "Incognito session" }).click();
  await expect(page.getByRole("switch", { name: "Incognito session" })).toHaveAttribute(
    "aria-checked",
    "false",
    { timeout: 30_000 },
  );
});
