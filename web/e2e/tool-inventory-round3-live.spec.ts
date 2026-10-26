/**
 * Agent tool inventory, third round, against a running host and a real model.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `raiker-web --workspace <ws> --port 8765 --no-browser`, with
 *      `notebooks/demo.ipynb` in it.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *
 * The GitHub operations (TOOL-27 – TOOL-29) need a credential this host does
 * not have, and an extended search needs a search provider the host's network
 * allows; the unit suite proves them.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Agent tool inventory,
 * third round"): RT-TOOL-17 … RT-TOOL-22.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-25-tool-inventory-3";

async function open(page: Page, hash: string): Promise<void> {
  await page.goto(`${BASE}/${hash}`);
  await settled(page);
}

async function start(page: Page): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
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
  await page.getByLabel("Prompt", { exact: true }).fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  return finished(page);
}

test("RT-TOOL-17 — help opens an article as its intro and parts, and a part on its own", async ({ page }) => {
  test.setTimeout(120_000);
  await start(page);
  await open(page, "#/approvals");
  await page.getByRole("button", { name: /^Help/ }).first().click();
  const panel = page.getByRole("complementary", { name: "Help" });
  await expect(panel).toBeVisible({ timeout: 30_000 });
  // Approvals maps to one part of its article, so ? lands on that part.
  await expect(panel.locator("article.help-article h2").first()).toHaveText(/What .approved. means/, { timeout: 30_000 });
  await expect(panel.getByRole("navigation", { name: "More in this article" })).toBeVisible();
  await capture(page, `${SHOTS}/17-help-part.png`, panel);
  await panel.getByRole("button", { name: /Permissions and the runtime/ }).first().click();
  const parts = panel.getByRole("list", { name: "In this article" });
  await expect(parts).toBeVisible({ timeout: 30_000 });
  await expect(parts.getByRole("button", { name: /Capability gates/ })).toBeVisible();
  // The intro stops at the first part: no part heading is drawn above the list.
  await expect(panel.locator("article.help-intro h2")).toHaveCount(0);
  await capture(page, `${SHOTS}/17-help-article-parts.png`, panel);
});

test("RT-TOOL-18 — help search lands on the part that answers it", async ({ page }) => {
  test.setTimeout(120_000);
  await start(page);
  await open(page, "#/new-chat");
  await page.getByRole("button", { name: /^Help/ }).first().click();
  const panel = page.getByRole("complementary", { name: "Help" });
  await panel.getByRole("searchbox", { name: "Search help" }).fill("fallback");
  const results = panel.getByRole("list", { name: "Search results" });
  const hit = results.getByRole("button", { name: /Fallback sequence/ }).first();
  await expect(hit).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/18-help-search-parts.png`, panel);
  await hit.click();
  await expect(panel.locator("article.help-article h2").first()).toHaveText(/Fallback sequence/, { timeout: 30_000 });
});

test("RT-TOOL-19 — Anthropic connects through Add model and becomes the default", async ({ page }) => {
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
  await review.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden();
});

test("RT-TOOL-20 — a flagged site is read, with an alert on the row (owner's decision)", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(600_000);
  await start(page);
  await open(page, "#/settings?tab=web-access");
  const site = page.getByLabel("Site to flag");
  await expect(site).toBeVisible({ timeout: 30_000 });
  await site.fill("github.com");
  await page.getByRole("button", { name: "Flag", exact: true }).click();
  await expect(page.getByRole("button", { name: "Remove flag from github.com" })).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/20-flagged-sites.png`, page.locator("main"));
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page
    .getByLabel("Prompt", { exact: true })
    .fill(
      "Call web_fetch once with url https://github.com/about and question 'what is GitHub', then tell me in " +
        "one sentence what the page says, and pass on any Raiker alert.",
    );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  // A fresh instance reads web pages after asking: the read is approved here.
  const card = page.getByRole("region", { name: "Raiker Safety" }).last();
  const answer = page.locator(".message-group-raiker").last();
  await expect(card.getByText("Waiting for your decision").or(answer.locator(".response-actions"))).toBeVisible({
    timeout: 240_000,
  });
  if (await card.getByText("Waiting for your decision").isVisible().catch(() => false)) {
    await card.getByRole("button", { name: /Allow once/ }).click();
  }
  const done = await finished(page);
  const alerts = done.getByRole("list", { name: "Alerts for this read" });
  await expect(alerts).toContainText("flagged", { timeout: 60_000 });
  await capture(page, `${SHOTS}/20-flagged-read-alert.png`, done);
});

test("RT-TOOL-21 — a notebook reads as cells and an edit names its cell (TOOL-03)", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(600_000);
  await start(page);
  const answer = await ask(
    page,
    "Read notebooks/demo.ipynb with read_file, then propose one edit_file call with cell 1 that changes " +
      "'x = 1' to 'x = 2' in that cell. Do not change anything else.",
  );
  await expect(answer.locator(".tool-row").filter({ hasText: "demo.ipynb › cell 1" }).first()).toBeVisible({
    timeout: 60_000,
  });
  await capture(page, `${SHOTS}/21-notebook-cell-edit.png`, answer);
});

test("RT-TOOL-22 — a Plan turn questions its own plan before proposing it (TOOL-151)", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(600_000);
  await start(page);
  const name = `Tool round 3 ${Date.now()}`;
  await open(page, "#/projects");
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("button", { name: `Open project ${name}` }).first()).toBeVisible({ timeout: 30_000 });
  await open(page, "#/build");
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  await page.getByLabel("Project for this build").selectOption({ label: name });
  await chooseModelForTurn(page, /Haiku|claude/i, "Build composer");
  await page.getByRole("button", { name: /^How much Raiker may do this turn:/ }).click();
  await page.getByRole("menu", { name: "Mode" }).getByRole("menuitemradio", { name: /^Plan/ }).click();
  await page.getByLabel("Describe the change").fill("Plan adding a CONTRIBUTING.md to this project. Change nothing.");
  await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
  await expect(page.getByText(/Questions I asked of this plan/i).first()).toBeVisible({ timeout: 300_000 });
  await capture(page, `${SHOTS}/22-plan-grill.png`);
});
