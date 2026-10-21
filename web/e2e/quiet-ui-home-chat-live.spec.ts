/**
 * Quiet UI — Home and Chat (docs/plans/quiet-ui/03_WELCOME_HOME_AND_CHAT.md),
 * against a running host and a real hosted model.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `raiker-web --workspace <ws> --port 8765 --no-browser`.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Quiet UI Home and
 * Chat"): RT-QUI-01 … RT-QUI-09.
 */
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { HOME_GREETING } from "./home";
import { chooseModelForTurn, dismissFirstRunModelSetup, hostedProviderCard, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-21-quiet-ui-home-chat";
const TITLE = "Quiet UI live check";

async function openHome(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  await expect(page.getByRole("heading", { name: HOME_GREETING })).toBeVisible({ timeout: 30_000 });
}

function lastAnswer(page: Page) {
  return page.locator(".message-group-raiker").last();
}

test("RT-QUI-01 — a first-day Home: greeting, composer, four starters, a backup recommendation", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await openHome(page);
  await expect(page.getByRole("heading", { name: HOME_GREETING })).toHaveText(/^Welcome/);
  await expect(page.getByLabel("Ask Raiker")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Start work" })).toHaveCount(0);
  const starters = page.getByRole("list", { name: "Ways to start" });
  await expect(starters.getByRole("listitem")).toHaveCount(4);
  const rail = page.getByRole("complementary", { name: "Needs your attention" });
  await expect(rail.getByText("There is no backup of this workspace yet.")).toBeVisible({ timeout: 30_000 });
  await expect(rail.getByRole("link", { name: "Make a backup" })).toHaveAttribute("href", "#/settings?tab=account");
  // QUI-Q01 — with no model the gap is named with its fix.
  await expect(rail.getByText("No default model is chosen.")).toBeVisible();
  await capture(page, `${SHOTS}/01-home-first-day.png`);
});

test("RT-QUI-02 — Anthropic connects through Models and the composer says where data goes", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 900 });
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
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku|claude/i);
  // QUI-C04 — said in the composer before anything is sent.
  await expect(page.getByText("Sent to Anthropic")).toBeVisible({ timeout: 30_000 });
  // QUI-C10 — an empty conversation's four starters; a question fills the box.
  const starters = page.getByRole("list", { name: "Ways to start" });
  await expect(starters.getByRole("listitem")).toHaveCount(4);
  await starters.getByRole("button", { name: "Plan my week" }).click();
  await expect(page.getByLabel("Prompt", { exact: true })).toHaveValue(/Help me plan my week/);
  await capture(page, `${SHOTS}/02-chat-empty-starters-data-label.png`);
  await page.getByLabel("Prompt", { exact: true }).fill("");
});

test("RT-QUI-03 — Home's composer opens Chat and the message is answered there", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await openHome(page);
  await page.getByLabel("Ask Raiker").fill("Reply with exactly: HOME HANDOFF");
  await page.getByRole("button", { name: "Send" }).first().click();
  await expect(page).toHaveURL(/#\/new-chat/);
  await expect(lastAnswer(page)).toContainText("HOME HANDOFF", { timeout: 180_000 });
  // Found live: the hand-off was judged before Chat read its own model, and a
  // stale "Set up a model" dialog stayed over a turn that had answered.
  await expect(page.getByRole("heading", { name: /Set up a model|Repair model connection/ })).toHaveCount(0);
  // QUI-Q05 — there is a conversation to leave now, so New chat is offered.
  await expect(page.getByRole("button", { name: "New chat", exact: true })).toBeVisible();
  await capture(page, `${SHOTS}/03-home-handoff-answered.png`);
});

test("RT-QUI-04 — the conversation is titled, renamed in place, and listed under Chat", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const sidebar = page.getByRole("navigation", { name: "All navigation" });
  const recent = sidebar.getByRole("list", { name: "Recent chats" });
  await expect(recent.getByRole("link").first()).toBeVisible({ timeout: 30_000 });
  await recent.getByRole("link").first().click();
  const rename = page.getByRole("button", { name: "Rename conversation" });
  await expect(rename).toBeVisible({ timeout: 30_000 });
  await rename.click();
  const input = page.getByRole("textbox", { name: "Conversation title" });
  await input.fill(TITLE);
  await input.press("Enter");
  await expect(page.getByRole("heading", { name: TITLE })).toBeVisible({ timeout: 30_000 });
  await expect(recent.getByRole("link", { name: TITLE })).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/04-title-renamed-recent-chats.png`);
});

test("RT-QUI-05 — scrolling up stops following; Jump to latest brings the answer back", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  const fresh = page.getByRole("button", { name: "New chat", exact: true });
  if (await fresh.isVisible()) await fresh.click();
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(
    "Without using any tools and without creating a document, reply directly in this chat: write the numbers 1 to 120, one per line, each followed by a short fact about that number.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  // A Markdown list draws its numbers as markers, not text, so the answer is
  // awaited by its finished turn: the running turn's controls go away.
  await expect(page.getByTestId("turn-control")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("turn-control")).toHaveCount(0, { timeout: 240_000 });
  const thread = page.locator(".thread");
  expect(await thread.evaluate((el) => el.scrollHeight > el.clientHeight * 2)).toBe(true);
  await thread.evaluate((el) => el.scrollTo({ top: 0 }));
  const jump = page.getByRole("button", { name: "Jump to latest" });
  await expect(jump).toBeVisible({ timeout: 15_000 });
  await capture(page, `${SHOTS}/05-jump-to-latest.png`);
  await jump.click();
  await expect(jump).toHaveCount(0);
  const atBottom = await thread.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight < 60);
  expect(atBottom).toBe(true);
});

test("RT-QUI-06 — a running turn reads Stop safely, and stopping says it kept its work", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  const fresh = page.getByRole("button", { name: "New chat", exact: true });
  if (await fresh.isVisible()) await fresh.click();
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(
    "Without using any tools and without creating a document, reply directly in this chat with a 1500-word essay on the history of maps.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const control = page.getByTestId("turn-control");
  const stop = control.getByRole("button", { name: "Stop safely" });
  await expect(stop).toBeVisible({ timeout: 60_000 });
  await expect(control.getByLabel("Add instruction")).toBeVisible();
  await expect(stop).toBeEnabled({ timeout: 60_000 });
  await capture(page, `${SHOTS}/06-running-turn-stop-safely.png`);
  await stop.click();
  await expect(page.getByText(/Stop requested|Stopped at your request/).first()).toBeVisible({ timeout: 60_000 });
});

test("RT-QUI-07 — Home after work: a time-of-day greeting and This week", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await openHome(page);
  await expect(page.getByRole("heading", { name: HOME_GREETING })).toHaveText(/^Good (morning|afternoon|evening)/);
  await expect(page.getByRole("list", { name: "Ways to start" })).toHaveCount(0);
  await capture(page, `${SHOTS}/07-home-after-work.png`);
});

test("RT-QUI-08 — after an update Home says so once, and the line is dismissed", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await openHome(page);
  // As if this browser last saw an older version: Home reads it when it mounts.
  await page.evaluate(() => localStorage.setItem("raiker.whats-new.seen-version", "0.0.0-previous"));
  await page.reload();
  await expect(page.getByRole("heading", { name: HOME_GREETING })).toBeVisible({ timeout: 30_000 });
  const line = page.getByText(/^Raiker was updated to /);
  await expect(line).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("link", { name: "What's new" })).toHaveAttribute("href", "#/settings?tab=updates");
  await capture(page, `${SHOTS}/08-whats-new.png`);
  await page.getByRole("button", { name: "Dismiss" }).click();
  await expect(line).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: HOME_GREETING })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/^Raiker was updated to /)).toHaveCount(0);
});

test("RT-QUI-09 — Settings › General runs setup again and keeps the chosen model", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=general`);
  await settled(page);
  await expect(page.getByRole("option", { name: "Home" })).toHaveCount(1);
  await page.getByRole("button", { name: "Run setup again" }).click();
  await expect(page.locator("#setup-title")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("#setup-title")).not.toHaveText(/^Preparing/, { timeout: 30_000 });
  await capture(page, `${SHOTS}/09-setup-again.png`);
  await dismissFirstRunModelSetup(page);
  await expect(page.locator("#setup-title")).toHaveCount(0, { timeout: 30_000 });
});
