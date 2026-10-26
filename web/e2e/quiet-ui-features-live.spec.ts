/**
 * Quiet UI — features and improvements (Quiet UI plan 06, closed 2026-10-26: FIXED-1150 … FIXED-1167),
 * against a running host and a real hosted model.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `raiker-web --workspace <ws> --port 8765 --no-browser`.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *
 * The desktop-only parts — the tray (QUI-F11), a project in its own window
 * (QUI-F13) and Quick Entry's shortcut (QUI-F01) — are proved in
 * `desktop/e2e/shell.spec.ts`; Quick Entry's page is driven here.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Quiet UI features and
 * improvements"): RT-QUI-44 … RT-QUI-56.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-24-quiet-ui-features";

async function open(page: Page, hash: string): Promise<void> {
  await page.goto(`${BASE}/${hash}`);
  await settled(page);
}

async function start(page: Page): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
}

/** Send one prompt in a new chat and return the answer group once it has finished. */
async function ask(page: Page, prompt: string): Promise<Locator> {
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  return finished(page);
}

async function finished(page: Page): Promise<Locator> {
  const answer = page.locator(".message-group-raiker").last();
  await expect(answer).toBeVisible({ timeout: 180_000 });
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeVisible({ timeout: 240_000 });
  await expect(answer.locator(".response-actions")).toBeVisible({ timeout: 240_000 });
  return answer;
}

test("RT-QUI-44 — Anthropic connects through Add model and becomes the default", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(360_000);
  await start(page);
  await open(page, "#/models");
  await page.getByRole("button", { name: "Add model" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Add model" });
  await dialog.getByRole("button", { name: /An account I have/ }).click();
  const card = dialog.locator("article.provider-card").filter({ hasText: "Anthropic" }).first();
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    if (WORKSPACE_ID) {
      await page.getByRole("button", { name: "Advanced" }).last().click();
      await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE_ID);
    }
    await page.locator(".signin-connect").click();
  }
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 90_000 });
  await keepModelAvailable(page, card, MODEL);
  const review = dialog.getByRole("region", { name: "3 · Review" });
  const makeDefault = review.getByRole("button", { name: "Make default" }).first();
  await expect(makeDefault.or(review.getByText("Default", { exact: true })).first()).toBeVisible({ timeout: 60_000 });
  if (await makeDefault.isVisible().catch(() => false)) await makeDefault.click();
  await expect(review.getByText("Default", { exact: true }).first()).toBeVisible({ timeout: 60_000 });
  await review.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden();
});

test("RT-QUI-45 — Home and Chat say where the message goes, with attachments (QUI-F17)", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  await open(page, "#/home");
  const label = page.locator(".home-composer .data-label");
  await expect(label).toHaveText(/Sent to Anthropic/, { timeout: 30_000 });
  await page.locator("#home-prompt").fill("Summarise this");
  await page.locator(".home-composer").getByRole("button", { name: "Add attachment" }).click();
  await page.locator(".home-composer").getByLabel("Upload document").setInputFiles({
    name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("Anna prefers short replies."),
  });
  await expect(label).toHaveText(/Sent to Anthropic, with 1 file/, { timeout: 30_000 });
  await capture(page, `${SHOTS}/45-home-data-label.png`, page.locator(".home-composer"));
});

test("RT-QUI-46 — a turn ends with its receipt; the top bar showed it running (QUI-F16, QUI-F04)", async ({ page }) => {
  test.setTimeout(400_000);
  await start(page);
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(
    "List the files and folders at the top of this workspace with the list_directory tool, then tell me how many there are.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  // QUI-F04 — while it runs, the top bar names it from every page.
  const line = page.getByTestId("live-work-line");
  await expect(line).toBeVisible({ timeout: 60_000 });
  await capture(page, `${SHOTS}/46-live-work-line.png`, page.locator("header.topbar"));
  const answer = await finished(page);
  await expect(line).toHaveCount(0, { timeout: 60_000 });
  const receipt = answer.getByTestId("turn-receipt");
  await expect(receipt).toContainText(/Haiku 4\.5 · ≈ \$0\.\d+ · \d+ files? read · nothing else left this computer/, { timeout: 30_000 });
  await receipt.locator("summary").click();
  await expect(receipt.getByText("Left this computer", { exact: true })).toBeVisible();
  await expect(receipt).toContainText("The conversation, to Anthropic");
  await capture(page, `${SHOTS}/46-receipt.png`, answer);
});

test("RT-QUI-47 — a question arrives as a card and the turn continues on the answer (QUI-F02)", async ({ page }) => {
  test.setTimeout(400_000);
  await start(page);
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(
    "Before writing anything, call the ask_owner_question tool once with two questions: " +
      "'Which greeting do you prefer?' with options Hello and Hi (single choice), and " +
      "'Which days suit you?' with options Mon, Tue and Wed (multiSelect true). " +
      "After I answer, write one sentence that uses my answers.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const card = page.getByTestId("clarify-card");
  await expect(card).toBeVisible({ timeout: 180_000 });
  await expect(card.getByText("Waiting for your answer")).toBeVisible();
  await expect(card.getByText("1 of 2")).toBeVisible();
  await expect(page.getByRole("button", { name: /Allow once/ })).toHaveCount(0);
  await expect(page.locator(".tool-waiting").getByText("waiting for your answer", { exact: true })).toBeVisible();
  await capture(page, `${SHOTS}/47-question-card.png`, card);
  await card.getByRole("radio", { name: /^Hi/ }).check();
  await card.getByRole("button", { name: "Next question" }).click();
  await card.getByRole("checkbox", { name: /^Tue/ }).check();
  await card.getByRole("checkbox", { name: /^Wed/ }).check();
  await card.getByRole("button", { name: "Confirm and continue" }).click();
  const answer = page.locator(".message-group-raiker").last();
  await expect(answer.locator(".message-bubble-raiker")).toContainText(/Hi/, { timeout: 240_000 });
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeVisible({ timeout: 240_000 });
  // Found live: the answered question read "failed" and the turn "Partially completed".
  await expect(answer.locator(".tool-row[data-state='failed']")).toHaveCount(0);
  await expect(answer.getByText("Partially completed")).toHaveCount(0);
  await capture(page, `${SHOTS}/47-question-answered.png`, answer);
});

test("RT-QUI-48 — a correction is offered as a memory and saved (QUI-F20)", async ({ page }) => {
  test.setTimeout(400_000);
  await start(page);
  const answer = await ask(page, "That's wrong — Anna prefers short replies. Reply with one short sentence acknowledging it.");
  const offer = answer.getByRole("group", { name: "Remember this correction" });
  await expect(offer).toContainText("Remember: Anna prefers short replies?");
  await expect(offer).not.toContainText("Reply with");
  await capture(page, `${SHOTS}/48-correction-offer.png`, offer);
  await offer.getByRole("button", { name: "Save" }).click();
  await expect(answer.getByText("Remembered.")).toBeVisible({ timeout: 30_000 });
  await open(page, "#/memory?tab=memories");
  await expect(page.getByRole("heading", { name: "Anna prefers short replies." })).toBeVisible({ timeout: 30_000 });
});

test("RT-QUI-49 — one search finds chats, tasks and memories, with type filters (QUI-F22)", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  await open(page, "#/home");
  await page.keyboard.press("Control+K");
  const palette = page.getByRole("dialog", { name: "Search and commands" });
  await palette.getByRole("textbox", { name: "Search everything" }).fill("Anna");
  const results = palette.getByRole("listbox", { name: "Results" });
  await expect(results.getByText("Memories", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(results.getByText("Chats", { exact: true })).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/49-search-everything.png`, palette);
  await palette.getByRole("button", { name: "Memories" }).click();
  await expect(results.getByText("Chats", { exact: true })).toHaveCount(0);
  await results.getByRole("option", { name: /Anna prefers short replies/ }).click();
  await expect(page).toHaveURL(/#\/memory\?tab=memories&record=/);
  await expect(page.locator(".memory-card").filter({ hasText: "Anna prefers short replies." }).getByRole("button", { name: /More for/ })).toHaveAttribute("aria-expanded", "true", { timeout: 30_000 });
});

test("RT-QUI-50 — Save as routine and a schedule template fill the task form, nothing saved (QUI-F18, QUI-F06)", async ({ page }) => {
  test.setTimeout(400_000);
  await start(page);
  const answer = await ask(page, "List the files at the top of this workspace with the list_directory tool and count them.");
  await answer.getByRole("button", { name: "Save as routine" }).click();
  await expect(page).toHaveURL(/#\/tasks/);
  const instruction = page.getByLabel("What should Raiker do?");
  await expect(instruction).toHaveValue(/List the files at the top of this workspace[\s\S]*Last time this took these steps: /, { timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Repeating" })).toHaveAttribute("aria-pressed", "true");
  await capture(page, `${SHOTS}/50-save-as-routine.png`);
  await instruction.fill("");
  const templates = page.getByRole("group", { name: "Start from a template" });
  await templates.getByRole("button", { name: "Morning brief" }).click();
  await expect(instruction).toHaveValue(/brief for today/);
  await expect(page.getByLabel("Repeat")).toHaveValue("daily");
  await expect(page.getByText(/Results appear on Home and in this task's own conversation/)).toBeVisible();
  await capture(page, `${SHOTS}/50-template-morning-brief.png`);
});

test("RT-QUI-51 — Memory › Controls lists what Raiker built, and Undo turns it off (QUI-F09)", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  await open(page, "#/memory?tab=controls");
  const built = await page.evaluate(async () => {
    const csrf = document.cookie.split("; ").find((row) => row.startsWith("raiker_csrf="))?.split("=")[1] ?? "";
    const headers = { "content-type": "application/json", "X-Raiker-CSRF": decodeURIComponent(csrf) };
    const response = await fetch("/api/skills/build", {
      method: "POST",
      credentials: "include",
      headers,
      body: JSON.stringify({ name: "weekly-summary", description: "Writes the weekly summary", body: "Summarise the week in five bullets." }),
    });
    if (response.status !== 200) return response.status;
    // A built skill starts off; the owner turns it on, as in Connections › Skills.
    const { skill_id: skillId } = (await response.json()) as { skill_id: string };
    const activated = await fetch(`/api/skills/${skillId}/active`, {
      method: "PUT",
      credentials: "include",
      headers,
      body: JSON.stringify({ active: true }),
    });
    return activated.status;
  });
  expect(built).toBe(200);
  // The same address does not remount the page; read the lists again.
  await page.reload();
  await settled(page);
  await expect(page.getByRole("heading", { name: "What Raiker has learned to do" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Approvals you've given" })).toBeVisible();
  const row = page.locator(".control-list li").filter({ hasText: "weekly-summary" });
  await expect(row).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/51-memory-controls.png`);
  await row.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText(/is off\. Turn it on again in Connections › Skills/)).toBeVisible({ timeout: 30_000 });
});

test("RT-QUI-52 — chat text has its own size (QUI-F12)", async ({ page }) => {
  test.setTimeout(240_000);
  await start(page);
  await open(page, "#/settings?tab=personalisation");
  const select = page.getByRole("combobox", { name: "Chat text size" });
  await expect(select).toHaveValue("110", { timeout: 30_000 });
  await select.selectOption("140");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("You have unsaved changes")).toBeHidden({ timeout: 30_000 });
  await capture(page, `${SHOTS}/52-chat-text-size.png`, page.locator("section.settings-card", { has: select }));
  const scale = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--chat-text-scale").trim());
  expect(scale).toBe("1.4");
  await select.selectOption("110");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("You have unsaved changes")).toBeHidden({ timeout: 30_000 });
});

test("RT-QUI-53 — Notifications by event (QUI-F05)", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  await open(page, "#/settings?tab=notification");
  const card = page.locator("section.card", { has: page.getByRole("heading", { name: "What interrupts you" }) });
  for (const label of ["Approval needed", "Input needed", "Response ready", "Task failed", "Background task finished"]) {
    await expect(card.getByLabel(label)).toBeChecked({ timeout: 30_000 });
  }
  await expect(card).toContainText("inside Raiker they always show");
  await card.getByLabel("Input needed").uncheck();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("You have unsaved changes")).toBeHidden({ timeout: 30_000 });
  await page.reload();
  await settled(page);
  await expect(card.getByLabel("Input needed")).not.toBeChecked({ timeout: 30_000 });
  await capture(page, `${SHOTS}/53-notifications-by-event.png`, card);
  await card.getByLabel("Input needed").check();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("You have unsaved changes")).toBeHidden({ timeout: 30_000 });
});

test("RT-QUI-54 — one confirmation dialog: Esc cancels, Enter confirms (QUI-F10)", async ({ page }) => {
  test.setTimeout(240_000);
  await start(page);
  await open(page, "#/work?tab=threads");
  const organise = page.getByRole("button", { name: /^Organise / }).first();
  await expect(organise).toBeVisible({ timeout: 30_000 });
  await organise.click();
  await page.getByRole("group", { name: /^Organise / }).getByRole("button", { name: "Archive", exact: true }).click();
  const dialog = page.getByRole("dialog").filter({ has: page.getByRole("button", { name: "Archive", exact: true }) });
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeVisible();
  await capture(page, `${SHOTS}/54-confirm-dialog.png`);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("RT-QUI-55 — Quick Entry files a task and the top bar shows it (QUI-F01, QUI-F04)", async ({ page }) => {
  test.setTimeout(300_000);
  await start(page);
  await page.setViewportSize({ width: 560, height: 120 });
  await open(page, "#/quick-entry");
  const box = page.getByRole("textbox", { name: "Ask Raiker" });
  await expect(box).toBeFocused({ timeout: 30_000 });
  await expect(page.getByRole("combobox", { name: "Send to" })).toHaveValue("new");
  await box.fill("Write a three-line haiku about autumn and keep it in this task's conversation.");
  await capture(page, `${SHOTS}/55-quick-entry.png`);
  await box.press("Enter");
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page).toHaveURL(/#\/home/);
  await settled(page);
  await expect(page.getByTestId("live-work-line")).toContainText(/haiku/i, { timeout: 60_000 });
  await capture(page, `${SHOTS}/55-live-work-task.png`, page.locator("header.topbar"));
});

test("RT-QUI-56 — the tray switch is offered only in the desktop window (QUI-F11)", async ({ page }) => {
  test.setTimeout(120_000);
  await start(page);
  await open(page, "#/settings?tab=general");
  await expect(page.getByRole("heading", { name: "Answers" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Desktop window" })).toHaveCount(0);
});
