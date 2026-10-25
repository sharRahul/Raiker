/**
 * Agent tool inventory, second round (docs/plans/AGENT_TOOL_INVENTORY.md),
 * against a running host and a real hosted model.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `raiker-web --workspace <ws> --port 8765 --no-browser`, holding
 *      `src/shapes.py` in a git repository.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *
 * The GitHub reads and writes (TOOL-21 – TOOL-29), PDF pages over the web
 * (TOOL-91), a recalled memory's conversation (TOOL-104) and the background
 * command notice (TOOL-01) need a credential, an outside host or a long
 * command this host does not have; the unit suite proves them.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Agent tool inventory,
 * second round"): RT-TOOL-11 … RT-TOOL-16.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-25-tool-inventory-2";

async function open(page: Page, hash: string): Promise<void> {
  await page.goto(`${BASE}/${hash}`);
  await settled(page);
}

async function start(page: Page): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
}

async function send(page: Page, prompt: string): Promise<void> {
  await page.getByLabel("Prompt", { exact: true }).fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
}

async function finished(page: Page): Promise<Locator> {
  const answer = page.locator(".message-group-raiker").last();
  await expect(answer).toBeVisible({ timeout: 180_000 });
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeVisible({ timeout: 240_000 });
  await expect(answer.locator(".response-actions")).toBeVisible({ timeout: 240_000 });
  return answer;
}

async function ask(page: Page, prompt: string): Promise<Locator> {
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await send(page, prompt);
  return finished(page);
}

/** A fresh project for Build to work in, chosen on Build's composer. */
async function buildInProject(page: Page): Promise<void> {
  const name = `Tool round ${Date.now()}`;
  await open(page, "#/projects");
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("button", { name: `Open project ${name}` }).first()).toBeVisible({ timeout: 30_000 });
  await open(page, "#/build");
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  await page.getByLabel("Project for this build").selectOption({ label: name });
  await chooseModelForTurn(page, /Haiku|claude/i, "Build composer");
}

test("RT-TOOL-11 — Anthropic connects through Add model and becomes the default", async ({ page }) => {
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

test("RT-TOOL-12 — a turn offers a connection as a card that opens Add connection on it (TOOL-72)", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(400_000);
  await start(page);
  const answer = await ask(
    page,
    "I want you to read my latest Gmail invoice. Gmail is not connected, so call suggest_connection once with " +
      "service 'Gmail' and a short reason, then tell me in one sentence what you will do once it is connected.",
  );
  const card = answer.getByTestId("connect-card");
  await expect(card).toContainText("Connect Gmail");
  await capture(page, `${SHOTS}/12-connect-card.png`, answer);
  await card.getByRole("link", { name: "Add connection" }).click();
  await expect(page).toHaveURL(/#\/connections\?add=gmail/);
  const dialog = page.getByRole("dialog", { name: "Add connection" });
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await expect(dialog.getByRole("button", { name: /Add Gmail/ })).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/12-add-connection-on-gmail.png`, dialog);
});

test("RT-TOOL-13 — skill_search finds the skill a task needs (TOOL-70)", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(400_000);
  await start(page);
  const answer = await ask(
    page,
    "Call skill_search once with query 'security review' and reply with only the name of the best skill it found.",
  );
  await expect(answer.locator(".tool-row").filter({ hasText: "Find a skill" }).first()).toBeVisible();
  await expect(answer.locator(".message-bubble-raiker")).toContainText("security-review");
  await capture(page, `${SHOTS}/13-skill-search.png`, answer);
});

test("RT-TOOL-14 — a Raiker help source opens the help panel on its article (TOOL-129)", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(400_000);
  await start(page);
  const answer = await ask(
    page,
    "Read the help article with help_read slug 'memory' and tell me in one sentence what Memory does.",
  );
  const chip = answer.locator(".source-chip").filter({ hasText: /Help: / }).first();
  await expect(chip).toBeVisible({ timeout: 30_000 });
  await chip.click();
  const panel = page.getByRole("complementary", { name: "Help" });
  await expect(panel).toBeVisible({ timeout: 30_000 });
  await expect(panel.locator("article.help-article")).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/14-help-panel-from-source.png`);
});

test("RT-TOOL-15 — Build leaves Plan only when the owner approves the plan (TOOL-09)", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(600_000);
  await start(page);
  await buildInProject(page);
  await page.getByRole("button", { name: /^How much Raiker may do this turn:/ }).click();
  await page.getByRole("menu", { name: "Mode" }).getByRole("menuitemradio", { name: /^Plan/ }).click();
  await page
    .getByLabel("Describe the change")
    .fill("Call update_plan once with three pending steps for adding a README to this project. Change nothing.");
  await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
  const approve = page.getByRole("button", { name: "Approve plan · Suggest changes" });
  await expect(approve).toBeVisible({ timeout: 300_000 });
  await expect(page.getByText("Made in Plan, so nothing has changed yet.")).toBeVisible();
  await capture(page, `${SHOTS}/15-approve-plan.png`, page.locator(".plan-slot"));
  await approve.click();
  await expect(page.getByRole("button", { name: /^How much Raiker may do this turn: Suggest changes/ })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Go ahead with the plan. Every change still asks me first.").first()).toBeVisible({ timeout: 60_000 });
  await expect(approve).toHaveCount(0);
  await capture(page, `${SHOTS}/15-plan-approved.png`);
  await page.getByRole("button", { name: /Stop/ }).first().click().catch(() => {});
});

test("RT-TOOL-16 — Build has /insights and /compress (TOOL-131)", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(600_000);
  await start(page);
  await buildInProject(page);
  await page.getByLabel("Describe the change").fill("List the files in this project with list_directory and say how many there are. Change nothing.");
  await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
  await page.getByLabel("Describe the change").fill("/insights");
  await page.keyboard.press("Enter");
  const sheet = page.getByTestId("insights-sheet");
  await expect(sheet).toBeVisible({ timeout: 30_000 });
  await expect(sheet).toContainText(/Tool calls\s*\d/);
  await capture(page, `${SHOTS}/16-build-insights.png`, sheet);
  await page.getByLabel("Describe the change").fill("/compress");
  await page.keyboard.press("Enter");
  await expect(
    page.getByText(/Summarised \d+ earlier exchanges? for the model|already summarised|could not be summarised|nothing to summarise/),
  ).toBeVisible({ timeout: 180_000 });
});
