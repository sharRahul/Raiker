/**
 * BUG-245 — a cited past conversation opens the exchange it names.
 *
 * FIXED-317 made `conversation_search` a citable source and FIXED-316 made a
 * turn coordinate openable. The two did not meet: opening a **Past
 * conversations** chip showed each exchange's conversation title and date above
 * its text — which is what made it checkable at all — and the exchanges were
 * text, so verifying one still meant retyping the title into chat search.
 *
 * Live, and with a real model, because the whole claim is about what the
 * *runtime* recorded from a tool result it actually executed. A fixture would
 * assert the panel renders a list it was handed.
 *
 * Run with `RAIKER_LIVE_ANTHROPIC_KEY` set.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { refreshHostedReadiness, signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";
const MARKER = "peregrine falcon deployment window";

let context: BrowserContext;
let page: Page;

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  await signInAsOwner(page, BASE);
});

test.afterAll(async () => {
  await context?.close();
});

/** Send a prompt on the visible composer and wait for the turn to finish. */
async function send(prompt: string, timeout = 300_000) {
  const composer = page
    .locator("#prompt-input:visible, textarea[placeholder^='Describe']:visible")
    .first();
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout });
}

async function openChat() {
  await page.getByRole("link", { name: "Chat", exact: true }).first().click();
  await expect(page).toHaveURL(/#\/new-chat/, { timeout: 30_000 });
}

test("a cited past conversation lists its exchanges, and each one opens", async () => {
  test.setTimeout(900_000);
  expect(KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");

  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: KEY,
    model: MODEL,
  });

  // A conversation worth finding later. The marker is nonsense on purpose:
  // recall has to have found *this* exchange, not something that reads like it.
  await openChat();
  await send(`Remember this for later: the ${MARKER} is the third Tuesday of each month.`);

  // A new conversation, so answering needs the search rather than the thread.
  await page.getByRole("button", { name: "New chat", exact: true }).first().click();
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await openChat();
  await send(
    `Search my past conversations for "${MARKER}" using your conversation search tool, ` +
      "then tell me what we said about it and cite the source.",
  );

  // The chip the search produced.
  const chip = page.getByRole("button", { name: /Past conversations/ }).first();
  await expect(chip).toBeVisible({ timeout: 60_000 });
  await chip.click();

  // The defect, as an assertion: each exchange the search returned is a link,
  // and the link carries the turn — not just the conversation.
  const links = page.getByRole("navigation", { name: "Exchanges this search returned" });
  await expect(links).toBeVisible({ timeout: 30_000 });
  const first = links.getByRole("link").first();
  await expect(first).toHaveAttribute("href", /#\/(new-chat|build)\?session=[^&]+&turn=/);
  await capture(page, `${SHOTS}/bug-245-cited-exchanges.png`, links);

  // And following it lands on that exchange, with the mark a search hit gets.
  await first.click();
  await expect(page).toHaveURL(/turn=/, { timeout: 30_000 });
  await expect(page.locator(".turn-anchored")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(new RegExp(MARKER, "i")).first()).toBeVisible({
    timeout: 30_000,
  });
});
