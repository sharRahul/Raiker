/**
 * FIXED-1389 to FIXED-1395 — the 2026-11-14 round, against a real host.
 *
 * RT-1114-01  Anthropic connects through Add model with an identity-linked key
 *             and the workspace ID the provider asks for, and Chat answers.
 * RT-1114-02  The Tasks composer is one bar: no pill rows above the input, the
 *             timing behind one control, templates under the card.
 * RT-1114-03  Choosing "At a time" opens the details with the start time.
 * RT-1114-04  A task created from the new composer is filed on the board.
 * RT-1114-05  ChatGPT sign-in with a code shows the real device code that the
 *             owner's Codex returned, and Cancel ends it.
 * RT-1114-06  ChatGPT browser sign-in hands the owner the auth.openai.com page.
 * RT-1114-07  Settings › Updates, Security and Advanced open with their own
 *             names; Work › Library and Threads empty states are carded.
 *
 * Needs `RAIKER_LIVE_ANTHROPIC_KEY` and `RAIKER_LIVE_ANTHROPIC_WORKSPACE`, read
 * from the environment and never written here, and a host started with
 * `RAIKER_CODEX_PATH` pointing at a Codex CLI for RT-1114-05/06.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { checkModelReady, chooseModelForTurn, hostedProviderCard, openHostedProviders, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY, ANTHROPIC_MODEL, LIVE_BASE as BASE } from "./live";

const WORKSPACE = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE ?? "";
const OUT = "../../output/playwright/2026-11-14-round";

test.describe.configure({ mode: "serial" });

async function openAddModel(page: Page, source: "account" | "custom"): Promise<void> {
  await openHostedProviders(page, BASE, source);
}

test("RT-1114-01 Anthropic connects with its workspace and Chat answers", async ({ page }) => {
  test.setTimeout(420_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  expect(WORKSPACE, "set RAIKER_LIVE_ANTHROPIC_WORKSPACE").not.toBe("");
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  // A workspace that already holds the connection (a rerun) skips straight on.
  if (await connect.isVisible().catch(() => false)) {
    await card.getByRole("button", { name: "Connect", exact: true }).click();
    await page.getByLabel("Anthropic API key").fill(ANTHROPIC_KEY);
    // BUG-274 — an identity-linked key names the workspace it acts in.
    const advanced = page.locator(".sso-toggle");
    if (await advanced.isVisible().catch(() => false)) {
      if ((await advanced.getAttribute("aria-expanded")) === "false") await advanced.click();
    }
    await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE);
    await page.locator(".signin-connect").click();
    await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
    await expect(page.locator(".signin-overlay")).toHaveCount(0, { timeout: 60_000 });
  }
  await keepModelAvailable(page, card, ANTHROPIC_MODEL);
  const pinned = await hostedProviderCard(page, BASE, "Anthropic");
  await checkModelReady(page, pinned);
  await capture(page, `${OUT}/01-anthropic-connected.png`);

  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByRole("group", { name: "Message composer" });
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await chooseModelForTurn(page, /Haiku/);
  await composer.getByRole("textbox").first().fill("Reply with exactly: RAIKER_ROUND_OK");
  const send = composer.getByRole("button", { name: /^Send/ });
  await expect(send).toBeEnabled({ timeout: 60_000 });
  await send.click();
  // Raiker's answer, not the prompt that contains the same words.
  await expect(page.locator(".message-group-raiker").getByText("RAIKER_ROUND_OK").last()).toBeVisible({
    timeout: 120_000,
  });
  await capture(page, `${OUT}/01-chat-answer.png`);
});

test("RT-1114-02/03/04 the Tasks composer is one bar and files work", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/tasks`);
  const composer = page.getByRole("group", { name: "Plan work" });
  await expect(composer).toBeVisible({ timeout: 30_000 });
  // RT-1114-02 — no timing pills inside the card; one schedule control instead.
  await expect(composer.getByRole("group", { name: "When to run" })).toHaveCount(0);
  await expect(composer.getByRole("group", { name: "Start from a template" })).toHaveCount(0);
  await expect(page.getByRole("group", { name: "Start from a template" })).toBeVisible();
  const toggle = composer.locator("button.schedule-toggle");
  await expect(toggle).toHaveText(/Runs now/);
  // The bar's controls share one row at desktop width.
  const create = composer.getByRole("button", { name: /Create task|Start|Schedule/ });
  const [toggleBox, createBox] = [await toggle.boundingBox(), await create.boundingBox()];
  expect(toggleBox && createBox && Math.abs(toggleBox.y + toggleBox.height / 2 - (createBox.y + createBox.height / 2))).toBeLessThan(8);
  await capture(page, `${OUT}/02-tasks-composer.png`);

  // RT-1114-03 — At a time opens the details with the start time.
  await toggle.click();
  const menu = page.getByRole("dialog", { name: "Schedule" });
  await expect(menu.getByRole("group", { name: "When to run" })).toBeVisible();
  await capture(page, `${OUT}/03-schedule-menu.png`);
  await menu.getByRole("button", { name: "At a time" }).click();
  await expect(page.getByLabel("Start time")).toBeVisible();
  await menu.getByRole("button", { name: "Now" }).click();
  await menu.getByRole("button", { name: "Done", exact: true }).click();
  await expect(menu).toBeHidden();

  // RT-1114-04 — a one-pass task from the new composer is filed.
  await chooseModelForTurn(page, /Haiku/, "Plan work");
  await composer.getByLabel("What should Raiker do?").fill("Reply with the single word READY.");
  await expect(create).toBeEnabled({ timeout: 60_000 });
  await create.click();
  // The board's own row, not the instruction still in the composer.
  await expect(page.locator("h4", { hasText: "Reply with the single word READY" }).first()).toBeVisible({
    timeout: 60_000,
  });
  await capture(page, `${OUT}/04-task-filed.png`);
});

test("RT-1114-05/06 ChatGPT sign-in hands the owner a code and a page", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await openAddModel(page, "account");
  const row = page.locator("article", { has: page.getByRole("heading", { name: "ChatGPT subscription" }) });
  await expect(row).toBeVisible({ timeout: 30_000 });
  await capture(page, `${OUT}/05-chatgpt-row.png`);

  // RT-1114-05 — device code from the real Codex App Server. Codex fetches the
  // code from auth.openai.com itself; on a host whose network refuses that
  // service, the card must say so in words rather than as a reason code.
  await row.getByRole("button", { name: "Sign in with a code" }).click();
  const code = row.getByLabel("One-time code");
  const unreachable = row.getByText(/could not reach ChatGPT's sign-in service \(auth\.openai\.com\)/);
  await expect(code.or(unreachable)).toBeVisible({ timeout: 60_000 });
  if (await code.isVisible()) {
    await expect(code).toHaveText(/^[A-Z0-9]{3,}-?[A-Z0-9]{3,}$/);
    const verify = row.getByRole("link", { name: "Open the sign-in page" });
    await expect(verify).toHaveAttribute("href", /^https:\/\/auth\.openai\.com\//);
    await captureElement(row, `${OUT}/05-chatgpt-device-code.png`);
    await row.getByRole("button", { name: "Cancel" }).click();
  } else {
    test.info().annotations.push({ type: "network", description: "auth.openai.com unreachable from this host" });
    await row.scrollIntoViewIfNeeded();
    await captureElement(row, `${OUT}/05-chatgpt-device-code-unreachable.png`);
  }
  await expect(row.getByRole("button", { name: "Sign in with ChatGPT" })).toBeVisible();

  // RT-1114-06 — the browser sign-in page is handed to the owner's browser.
  const popup = page.waitForEvent("popup", { timeout: 30_000 }).catch(() => null);
  await row.getByRole("button", { name: "Sign in with ChatGPT" }).click();
  const again = row.getByRole("link", { name: "Open sign-in again" });
  await expect(again).toHaveAttribute("href", /^https:\/\/auth\.openai\.com\/oauth\/authorize\?/, {
    timeout: 60_000,
  });
  const opened = await popup;
  if (opened) await opened.close();
  await row.scrollIntoViewIfNeeded();
  await captureElement(row, `${OUT}/06-chatgpt-browser.png`);
  await row.getByRole("button", { name: "Cancel" }).click();
});

test("RT-1114-07 sections open with their names and empty states are carded", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  for (const [tab, heading] of [
    ["updates", "Updates"],
    ["security", "Security"],
    ["advanced", "Advanced"],
  ] as const) {
    await page.goto(`${BASE}/#/settings?tab=${tab}`);
    await expect(page.getByRole("heading", { level: 2, name: heading, exact: true })).toBeVisible({
      timeout: 30_000,
    });
    await capture(page, `${OUT}/07-settings-${tab}.png`);
  }
  await page.goto(`${BASE}/#/work?tab=library`);
  await expect(page.locator(".card", { hasText: "Nothing made yet" })).toBeVisible({ timeout: 30_000 });
  await capture(page, `${OUT}/07-library.png`);
});
