/**
 * Quiet UI — the layout system and the long pages rebuilt
 * (docs/plans/quiet-ui/01_LAYOUT_SYSTEM_AND_PAGES.md), against a running host
 * and a real hosted model.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `raiker-web --workspace <ws> --port 8765 --no-browser`.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Quiet UI layout"):
 * RT-QUI-17 … RT-QUI-25.
 */
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-21-quiet-ui-layout";

async function open(page: Page, hash: string): Promise<void> {
  await page.goto(`${BASE}/${hash}`);
  await settled(page);
}

test("RT-QUI-17 — the shell: a 232 px sidebar with 40 px rows, a 64 px rail in a narrow window, 1,180 px pages", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/settings");
  const sidebar = page.getByRole("navigation", { name: "All navigation" });
  expect(Math.round((await sidebar.boundingBox())!.width)).toBe(232);
  const row = sidebar.getByRole("link", { name: "Home" });
  expect(Math.round((await row.boundingBox())!.height)).toBe(40);
  const canvas = page.getByTestId("responsive-page");
  expect((await canvas.boundingBox())!.width).toBeLessThanOrEqual(1180);
  await capture(page, `${SHOTS}/17-shell-1440.png`);

  await page.setViewportSize({ width: 1200, height: 800 });
  await expect.poll(async () => Math.round((await sidebar.boundingBox())!.width)).toBe(64);
  await expect(sidebar.getByRole("link", { name: "Home" })).toBeVisible();
  await capture(page, `${SHOTS}/17-shell-narrow-rail-1200.png`);

  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect.poll(async () => Math.round((await sidebar.boundingBox())!.width)).toBe(232);
  expect((await canvas.boundingBox())!.width).toBeLessThanOrEqual(1180);
});

test("RT-QUI-18 — Connections lists what is connected and adds a service in a dialog", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/extensions?tab=connectors");
  // The old address lands on the renamed page.
  await expect(page.getByRole("heading", { level: 1, name: "Connections" })).toBeVisible();
  const tabs = page.getByRole("tablist", { name: "Connection categories" });
  await expect(tabs.getByRole("tab")).toHaveText(["Services", "Channels", "Advanced"]);
  await expect(page.getByText(/Nothing is connected yet/)).toBeVisible({ timeout: 30_000 });
  // No catalogue on the page: no install cards, no readiness tiles.
  await expect(page.getByRole("button", { name: /^Install$/ })).toHaveCount(0);
  await expect(page.getByText("Usable now")).toHaveCount(0);
  await capture(page, `${SHOTS}/18-connections-empty.png`);

  await page.getByRole("button", { name: "Add connection" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Add connection" });
  await expect(dialog.getByRole("searchbox", { name: "Search services" })).toBeVisible();
  await expect(dialog.getByRole("group", { name: "Categories" })).toBeVisible();
  // The account Build works as is named apart from the GitHub API connector.
  await expect(dialog.getByRole("button", { name: /GitHub sign-in/ })).toBeVisible();
  await dialog.getByRole("searchbox", { name: "Search services" }).fill("gmail");
  await capture(page, `${SHOTS}/18-add-connection-search.png`);
  await dialog.getByRole("button", { name: /Gmail/ }).first().click();
  await expect(dialog.getByRole("heading", { name: /Gmail/ })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Add Gmail" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Slack/ })).toHaveCount(0);
  await capture(page, `${SHOTS}/18-add-connection-steps.png`);
  await dialog.getByRole("button", { name: "Close" }).click();

  // Advanced is one segmented list; an old Hooks address opens its segment.
  await open(page, "#/extensions?tab=hooks");
  const segments = page.getByRole("group", { name: "Advanced connections" });
  await expect(segments.getByRole("button", { name: "Hooks" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText(/A hook can only make an action/)).toBeVisible();
  await capture(page, `${SHOTS}/18-connections-advanced-hooks.png`);
});

test("RT-QUI-19 — Channels lists linked channels and links a new one from Add channel", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/connections?tab=channels");
  await expect(page.getByText(/No channel is linked/)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Add channel" }).click();
  const dialog = page.getByRole("dialog", { name: "Add channel" });
  await expect(dialog.getByRole("button", { name: /Webhooks/ })).toBeVisible();
  await dialog.getByRole("button", { name: /Webhooks/ }).click();
  await expect(dialog.getByLabel("Allowed senders")).toBeVisible();
  await expect(dialog.getByText(/Pairing does not switch it on/)).toBeVisible();
  await capture(page, `${SHOTS}/19-add-channel-webhooks.png`);
});

test("RT-QUI-20 — Permissions: categories beside one permission at a time", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/capabilities");
  const rail = page.getByRole("navigation", { name: "Permission categories" });
  await expect(rail.getByRole("button", { name: /^Overview/ })).toHaveAttribute("aria-current", "page");
  await expect(rail.getByRole("button", { name: /^Advanced/ })).toBeVisible();
  await expect(page.getByRole("region", { name: "What Raiker can do for you" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Common permissions" })).toHaveCount(0);
  await capture(page, `${SHOTS}/20-permissions-overview.png`);

  await rail.getByRole("button", { name: /^Web and research/ }).click();
  await expect(page).toHaveURL(/category=web-and-research/);
  const rows = page.getByRole("listbox", { name: /Web and research permissions/ });
  await expect(rows.getByRole("option").first()).toBeVisible();
  // A row is text; the four-way choice is in the detail, once.
  await expect(rows.getByRole("button")).toHaveCount(0);
  await expect(page.getByRole("group", { name: /When Raiker wants to use/ })).toHaveCount(1);
  await capture(page, `${SHOTS}/20-permissions-category-detail.png`);

  // The overflow holds Select several and the technical grouping.
  await page.getByRole("button", { name: "More actions for permissions" }).click();
  await expect(page.getByRole("menuitem", { name: "Select several" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "Group by technical area" })).toBeVisible();
  await page.keyboard.press("Escape");
});

test("RT-QUI-21 — Models: Add model in three steps connects Anthropic and makes it the default", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(360_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/models");
  await expect(page.getByRole("tablist")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "No default model is chosen" })).toBeVisible({ timeout: 30_000 });
  // Chat's readiness: four steps under the card, the stopped one marked.
  const readiness = page.getByRole("list", { name: "Chat readiness" });
  await expect(readiness.getByRole("listitem")).toHaveCount(4);
  await expect(readiness.locator('[data-state="blocked"]')).toHaveCount(1);
  await capture(page, `${SHOTS}/21-models-empty.png`);

  await page.getByRole("button", { name: "Add model" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Add model" });
  for (const source of ["On this computer", "An account I have", "Hugging Face", "Custom endpoint"]) {
    await expect(dialog.getByRole("button", { name: new RegExp(source) })).toBeVisible();
  }
  await capture(page, `${SHOTS}/21-add-model-step-1.png`);
  await dialog.getByRole("button", { name: /An account I have/ }).click();
  await expect(dialog.getByText("2 · An account I have")).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "Your hosted providers" })).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "On this device" })).toHaveCount(0);
  const card = dialog.locator("article.provider-card").filter({ hasText: "Anthropic" }).first();
  // A rerun on the same workspace finds Anthropic connected already.
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
  await expect(review.getByText("Sent to Anthropic").first()).toBeVisible({ timeout: 60_000 });
  await expect(review.getByText("Billed by Anthropic").first()).toBeVisible();
  await capture(page, `${SHOTS}/21-add-model-review.png`);
  const makeDefault = review.getByRole("button", { name: "Make default" }).first();
  await expect(makeDefault.or(review.getByText("Default", { exact: true })).first()).toBeVisible({ timeout: 60_000 });
  if (await makeDefault.isVisible().catch(() => false)) await makeDefault.click();
  await expect(review.getByRole("alert")).toHaveCount(0);
  await expect(review.getByText("Default", { exact: true }).first()).toBeVisible({ timeout: 60_000 });
  await review.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden();

  const profile = page.getByRole("region", { name: /Haiku/ });
  await expect(profile.getByText("Sent to Anthropic")).toBeVisible({ timeout: 30_000 });
  const models = page.getByRole("listbox", { name: "My models" });
  await expect(models.getByRole("option", { name: /Haiku/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Usage · last 7 days" })).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/21-models-profile-card-my-models.png`);
});

test("RT-QUI-22 — a Chat turn answers on the model Add model made the default", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill("Reply with exactly: LAYOUT ROUND");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".message-group-raiker").last()).toContainText("LAYOUT ROUND", { timeout: 180_000 });
  await capture(page, `${SHOTS}/22-chat-answer.png`);
});

test("RT-QUI-23 — Settings: Account in General, an Advanced section, Security as rows", async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/settings");
  const rail = page.getByRole("navigation", { name: "Settings sections" });
  await expect(rail.getByRole("button")).toHaveText([
    "General",
    "Personalisation",
    "Notifications",
    "Security",
    "Privacy",
    "Execution profiles",
    "Web access",
    "Advanced",
    "About & updates",
  ]);
  await expect(page.getByLabel("Display name")).toBeVisible({ timeout: 30_000 });
  // Account is part of General, and names the owner once Settings has loaded.
  await expect(page.getByText(/Signed in as Rahul/)).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/23-settings-general-with-account.png`);

  // Old addresses: Runtime configuration is Advanced's first segment.
  await open(page, "#/settings?tab=runtime");
  const segments = page.getByRole("group", { name: "Advanced settings" });
  await expect(segments.getByRole("button", { name: "Runtime" })).toHaveAttribute("aria-pressed", "true");
  await segments.getByRole("button", { name: "Model serving" }).click();
  await expect(page.getByRole("heading", { name: "Work defaults" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Advanced routing")).toBeVisible();
  await capture(page, `${SHOTS}/23-settings-advanced-model-serving.png`);
  await segments.getByRole("button", { name: "Usage and spending" }).click();
  await expect(page.getByTestId("spend-limit")).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/23-settings-advanced-usage.png`);

  await open(page, "#/settings?tab=security");
  for (const label of ["Password", "Two-step sign-in", "Devices", "Encryption", "Vault key", "Standing approval grants"]) {
    await expect(page.getByRole("heading", { name: label, exact: true }).first()).toBeVisible();
  }
  await expect(page.getByLabel("Current password")).toHaveCount(0);
  await capture(page, `${SHOTS}/23-settings-security-rows.png`);
  await page.locator(".setting-row").filter({ hasText: "Vault key" }).getByRole("button").click();
  const vault = page.getByRole("dialog", { name: "Vault key" });
  await expect(vault.getByLabel("Vault key")).toBeVisible();
  await expect(vault.getByText("Technical details")).toBeVisible();
  await capture(page, `${SHOTS}/23-settings-vault-dialog.png`);
  await vault.getByRole("button", { name: "Close" }).click();

  // GitHub moved to Connections; its old address opens the sign-in there.
  await page.goto(`${BASE}/#/settings?tab=github`);
  await expect(page).toHaveURL(/#\/connections\?tab=services&item=github-account/, { timeout: 30_000 });
  await expect(page.getByRole("dialog", { name: "Add connection" }).getByRole("heading", { name: "GitHub sign-in" })).toBeVisible({
    timeout: 30_000,
  });
  await capture(page, `${SHOTS}/23-github-in-connections.png`);
});

test("RT-QUI-24 — Help opens beside the page on its article, searches, and answers old guide links", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/models");
  await page.getByRole("button", { name: "Help", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "Help" });
  await expect(panel).toBeVisible();
  expect(Math.round((await panel.boundingBox())!.width)).toBe(360);
  await expect(panel.getByRole("article")).toContainText(/model/i, { timeout: 30_000 });
  await capture(page, `${SHOTS}/24-help-models-article.png`);
  await panel.getByRole("searchbox", { name: "Search help" }).fill("memory");
  await expect(panel.getByRole("list", { name: "Help articles" }).getByRole("button").first()).toContainText(/Memory/i);
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();

  // An old Guide address opens the panel on that article over the page.
  await page.goto(`${BASE}/#/guide?section=memory`);
  await expect(panel).toBeVisible({ timeout: 30_000 });
  await expect(panel.getByRole("article")).toContainText(/memor/i, { timeout: 30_000 });
  await capture(page, `${SHOTS}/24-help-from-old-guide-address.png`);
});

test("RT-QUI-25 — the rebuilt pages fit their size budget at 1440×900", async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const heights: Record<string, number> = {};
  for (const hash of [
    "#/connections?tab=services",
    "#/connections?tab=channels",
    "#/capabilities",
    "#/models",
    "#/settings?tab=general",
    "#/settings?tab=security",
  ]) {
    await open(page, hash);
    await page.waitForTimeout(500);
    heights[hash] = await page.evaluate(() => {
      const main = document.querySelector("main#main") as HTMLElement | null;
      return main?.scrollHeight ?? 0;
    });
  }
  console.log("RT-QUI-25 heights", JSON.stringify(heights));
  for (const [hash, height] of Object.entries(heights)) {
    const budget = hash.startsWith("#/settings") ? 900 * 1.5 : 900;
    expect(height, `${hash} is ${height}px`).toBeLessThanOrEqual(budget);
  }
});
