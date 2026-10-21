/**
 * Quiet UI round 2 — Home and Chat (docs/plans/quiet-ui/03_WELCOME_HOME_AND_CHAT.md),
 * against a running host and a real hosted model.
 *
 * Runs after `quiet-ui-home-chat-live.spec.ts` on the same workspace: that
 * spec connects Anthropic through the product's own dialog and leaves
 * conversations behind, which is what Home's Continue card needs.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Quiet UI round 2"):
 * RT-QUI-10 … RT-QUI-13.
 */
import { writeFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { HOME_GREETING } from "./home";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-21-quiet-ui-round-2";

async function openHome(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  await expect(page.getByRole("heading", { name: HOME_GREETING })).toBeVisible({ timeout: 30_000 });
}

function lastAnswer(page: Page) {
  return page.locator(".message-group-raiker").last();
}

test("RT-QUI-10 — Home offers one thread to continue, with its next step, in one column", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await openHome(page);
  const card = page.getByRole("region", { name: "Continue where you left off" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card.getByRole("link", { name: /^Continue / })).toHaveCount(1);
  await expect(card.getByText(/turns? · updated/)).toBeVisible();
  await expect(card.getByRole("link", { name: /^All threads \(\d+\)$/ })).toBeVisible();
  // QUI-H01 — one 980 px column.
  const width = await page.locator(".workbench").evaluate((el) => el.getBoundingClientRect().width);
  expect(width).toBeLessThanOrEqual(981);
  await capture(page, `${SHOTS}/10-home-continue-card.png`);
});

test("RT-QUI-11 — a file attached on Home rides the message into Chat and is read", async ({ page }, testInfo) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const file = testInfo.outputPath("code-word.txt");
  await writeFile(file, "The code word for this test is PELICAN.\n");
  await openHome(page);
  await page.getByRole("button", { name: "Add attachment" }).click();
  await page.getByLabel("Upload document").setInputFiles(file);
  await expect(page.getByText("code-word.txt")).toBeVisible({ timeout: 30_000 });
  await page.getByLabel("Ask Raiker").fill("What is the code word in the attached file? Reply with just the word.");
  await capture(page, `${SHOTS}/11-home-attach.png`);
  await page.getByRole("button", { name: "Send" }).first().click();
  await expect(page).toHaveURL(/#\/new-chat/);
  await expect(lastAnswer(page)).toContainText("PELICAN", { timeout: 180_000 });
  await expect(page.locator(".turn").last().getByText("code-word.txt")).toBeVisible();
});

test("RT-QUI-12 — search in the conversation, and the context panel over and beside the transcript", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1280, height: 800 });
  await signInAsOwner(page, BASE);
  const recent = page.getByRole("navigation", { name: "All navigation" }).getByRole("list", { name: "Recent chats" });
  await expect(recent.getByRole("link").first()).toBeVisible({ timeout: 30_000 });
  await recent.getByRole("link").first().click();
  await expect(lastAnswer(page)).toContainText("PELICAN", { timeout: 30_000 });

  await page.getByRole("button", { name: "Search in conversation" }).click();
  await page.getByRole("searchbox", { name: "Search in conversation" }).fill("pelican");
  await expect(page.getByText("1 of 1")).toBeVisible();
  await expect(page.locator(".turn.search-hit")).toHaveCount(1);
  await capture(page, `${SHOTS}/12-chat-search.png`);
  await page.getByRole("searchbox", { name: "Search in conversation" }).press("Escape");

  // QUI-C07 — closed by default; Context shows the file this chat used.
  const panel = page.getByRole("complementary", { name: "Conversation context" });
  await expect(panel).toHaveCount(0);
  await page.getByRole("button", { name: "Context", exact: true }).click();
  await expect(panel.getByText("code-word.txt", { exact: true })).toBeVisible();
  // QUI-C12 — at 1,280 px it opens over the transcript.
  const thread = page.locator(".thread");
  const over = await panel.evaluate((el) => getComputedStyle(el.parentElement as HTMLElement).position);
  expect(over).toBe("fixed");
  // Over the transcript, never over the composer: Send stays reachable.
  const send = page.getByRole("button", { name: "Send", exact: true });
  const panelBottom = await panel.evaluate((el) => el.getBoundingClientRect().bottom);
  const sendTop = await send.evaluate((el) => el.getBoundingClientRect().top);
  expect(panelBottom).toBeLessThanOrEqual(sendTop);
  await capture(page, `${SHOTS}/12-context-panel-1280.png`);

  // From 1,920 px it sits beside the transcript.
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect(panel).toBeVisible();
  const beside = await panel.evaluate((el) => getComputedStyle(el.parentElement as HTMLElement).position);
  expect(beside).toBe("static");
  const panelLeft = await panel.evaluate((el) => el.getBoundingClientRect().left);
  const threadRight = await thread.evaluate((el) => el.getBoundingClientRect().right);
  expect(panelLeft).toBeGreaterThanOrEqual(threadRight - 1);
  await capture(page, `${SHOTS}/12-context-panel-1920.png`);
});

test("RT-QUI-13 — Run in background files the draft as a task and keeps the chat free", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  const fresh = page.getByRole("button", { name: "New chat", exact: true });
  if (await fresh.isVisible()) await fresh.click();
  await chooseModelForTurn(page, /Haiku|claude/i);
  const prompt = page.getByLabel("Prompt", { exact: true });
  await prompt.fill("Background check: reply with exactly BACKGROUND DONE");
  await page.getByRole("button", { name: "Tools" }).click();
  await page.getByRole("menu", { name: "Tools" }).getByRole("menuitem", { name: /Run in background/ }).click();
  await expect(page.getByText("Running in the background.")).toBeVisible({ timeout: 30_000 });
  await expect(prompt).toHaveValue("");
  const open = page.getByRole("link", { name: "Open the task" });
  await expect(open).toHaveAttribute("href", /#\/tasks\?task=/);
  await capture(page, `${SHOTS}/13-run-in-background.png`);
  await open.click();
  await expect(page.getByText("Background check: reply with exactly BACKGROUND DONE").first()).toBeVisible({
    timeout: 30_000,
  });
});
