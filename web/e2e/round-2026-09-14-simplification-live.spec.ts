/**
 * The 2026-09-14 simplification round, against a running host with a real key.
 *
 * Twelve items from `docs/plans/` were implemented in this pass. Nine of them
 * change something an owner sees, and this is the live evidence for those nine:
 * each one is driven through the product's own controls on a workspace that
 * started empty, with the captures filed beside the round record.
 *
 * The three that are not here are not owner-facing — the entry-path
 * classification (BUG-297) is asserted by `tests/test_governance_entry_paths.py`
 * against the router and the executor registry, and the two harness repairs
 * (BUG-291/292/295) are asserted by the specs that stopped mis-reporting.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import {
  chooseModelForTurn,
  hostedProviderCard,
  keepOffered,
  offeredModelIds,
  openModelDialog,
  pressCardAction,
  signInAsOwner,
} from "./hosted-provider";

/**
 * The menu entry for a model id, as the picker renders it.
 *
 * The composer names models the way an owner reads them — `claude-haiku-4-5` is
 * `Haiku 4.5` — so a spec that matched the raw id would find nothing. Matching
 * the distinctive part of the id is enough to pick one row out of a menu and
 * does not require the spec to reimplement `modelName`.
 */
function modelMenuName(modelId: string): string {
  const match = /haiku|sonnet|opus/i.exec(modelId);
  return match ? match[0] : modelId;
}

const BASE = "http://127.0.0.1:8765";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const SHOTS = "../../docs/screenshots/2026-09-14-simplification";

// Serial, and generous: this is a real host talking to a real provider, and
// the default 30s is a timeout on the network rather than on the product.
test.describe.configure({ mode: "serial", timeout: 300_000 });

let page: import("@playwright/test").Page;
/** Every uncaught console error of the whole round, in the order they arrived. */
const consoleErrors: string[] = [];

test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));
  await signInAsOwner(page, BASE);
});

test("REM-POPUP-01 — the gear is More, and Settings is one click from it", async () => {
  await page.goto(`${BASE}/#/workbench`);
  const more = page.getByRole("button", { name: "More pages and settings" });
  await expect(more).toBeVisible({ timeout: 30_000 });
  await more.click();

  const dialog = page.getByRole("dialog", { name: /^More$/ });
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  // The destination the old gear icon promised and the window would not go to.
  await expect(dialog.getByRole("link", { name: /^Settings/ })).toHaveAttribute(
    "href",
    "#/settings",
  );
  // And the sections stay, because "where is that setting" is the other
  // question this window answers.
  await expect(
    dialog.getByRole("link", { name: /^Security & sign-in$/ }),
  ).toHaveAttribute("href", "#/settings?tab=security");
  await capture(page, `${SHOTS}/more-window.png`);
  await page.keyboard.press("Escape");
});

test("REM-HOME-01 and REM-MAP-01 — Home leads with work, the map with its records", async () => {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByRole("navigation", { name: "All navigation" })).toBeVisible({
    timeout: 30_000,
  });
  await capture(page, `${SHOTS}/home.png`);

  await page.goto(`${BASE}/#/brain`);
  await page.getByRole("button", { name: "Graph settings" }).click();
  const settings = page.getByRole("complementary", { name: "Graph settings" });
  await expect(settings).toBeVisible({ timeout: 30_000 });
  // Filters is the one section about which records are on screen. The other
  // four — including five force-simulation constants — are a reach away.
  await expect(settings.locator("details[open] > summary")).toHaveText("Filters");
  await expect(settings.locator("details[open]")).toHaveCount(1);
  await expect(settings.getByText("Advanced display")).toBeVisible();
  await capture(page, `${SHOTS}/knowledge-map-settings.png`, settings);
});

test("BUG-296 — Models opens with no console error on an unreachable Hub", async () => {
  const before = consoleErrors.length;
  await page.goto(`${BASE}/#/models`);
  await expect(page.getByRole("tablist", { name: "Model settings" })).toBeVisible({
    timeout: 60_000,
  });
  await page.getByRole("tab", { name: "Add model" }).click();
  // The panel still says the Hub cannot be reached, in the right place — that
  // was never the defect. What must not happen is a 503 in the console on a
  // request nobody asked for.
  await page.waitForTimeout(4_000);
  expect(
    consoleErrors.slice(before).filter((line) => /hugging-face/i.test(line)),
  ).toEqual([]);
  await capture(page, `${SHOTS}/models-add.png`);
});

test("REM-MODEL-02 — routing tuning is folded, the substitution disclosure is not", async () => {
  await page.goto(`${BASE}/#/models`);
  await page.getByRole("tab", { name: "Runtime & routing" }).click();

  const advanced = page.locator("details.advanced-routing");
  await expect(advanced).toBeVisible({ timeout: 30_000 });
  await expect(advanced).not.toHaveAttribute("open", "");
  // Work defaults — which names a fallback that displaced the owner's
  // selection — stays outside it, because a substitution that changes provider
  // changes where the owner's words go.
  await expect(page.getByRole("heading", { name: "Work defaults" })).toBeVisible();
  await capture(page, `${SHOTS}/runtime-routing-folded.png`);

  await advanced.locator("summary").click();
  await expect(page.getByRole("heading", { name: "Model fallback sequence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Advisor model" })).toBeVisible();
  await capture(page, `${SHOTS}/runtime-routing-open.png`);
});

test("BUG-289 — an unreachable hosted provider gets a remedy an owner has", async () => {
  // This host's egress proxy answers `CONNECT openrouter.ai` with 403, which is
  // a genuinely *unclassified* failure — the request never reached a provider
  // that could refuse it — and so is the exact case this last-resort branch is
  // for. A credential is needed only to get as far as making the call; it is
  // never transmitted, because the tunnel is refused before the request goes.
  const card = await hostedProviderCard(page, BASE, "OpenRouter");
  const connect = card.getByRole("button", { name: /^(Connect|Reconnect)$/ });
  if (await connect.count()) {
    await connect.first().click();
    const field = page.getByLabel(/OpenRouter API key/i);
    await expect(field).toBeVisible({ timeout: 30_000 });
    await field.fill("sk-or-v1-unreachable-host-probe");
    await page.locator(".signin-connect").click();
    await expect(page.getByRole("dialog", { name: /Connect to OpenRouter/i })).toBeHidden({
      timeout: 60_000,
    });
  }

  // A connected card keeps one primary action and an overflow (MODEL-15), so
  // Test lives in the menu. `pressCardAction` is the helper that knows that.
  await pressCardAction(page, card, /^Test/);

  const note = card.getByText(/could not be reached/i);
  await expect(note).toBeVisible({ timeout: 180_000 });
  // "Check that it is running" is a thing an owner can do about llama.cpp on
  // their own machine and not a thing they can do about OpenRouter.
  await expect(card.getByText(/Check that it is running/i)).toHaveCount(0);
  await expect(card.getByText(/proxy or firewall/i)).toBeVisible();
  await capture(page, `${SHOTS}/openrouter-unreachable.png`, card);
});

test("BUG-286 — a fresh composer names nothing, then answers with a real key", async () => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");

  // Before any model is chosen: the trigger says Not selected, and — the fix —
  // the menu above it no longer opens naming a model nobody picked.
  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByRole("group", { name: "Message composer" });
  const trigger = composer.getByRole("button", { name: /^Model for this turn:/ });
  await expect(trigger).toHaveAccessibleName(/Not selected/, { timeout: 60_000 });
  await trigger.click();
  const menu = page.getByRole("menu", { name: "Models" });
  await expect(menu).toBeVisible({ timeout: 30_000 });
  await expect(menu.getByText(/Selected · unavailable/)).toHaveCount(0);
  await capture(page, `${SHOTS}/composer-nothing-selected.png`);
  await page.keyboard.press("Escape");

  // Now connect the key through the UI, exactly as an owner would.
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  const connect = card.getByRole("button", { name: /^(Connect|Reconnect)$/ });
  if (await connect.count()) {
    await connect.first().click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    await page.locator(".signin-connect").click();
    await expect(page.getByRole("dialog", { name: "Connect to Anthropic" })).toBeHidden({
      timeout: 60_000,
    });
  }
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });

  // BUG-295 — this waits for the catalogue rather than for the dialog to mount,
  // so `offeredModelIds` reads the provider's real answer instead of an empty
  // fieldset. Before the fix it returned `[]` here and the line below asked for
  // `input[value="undefined"]`.
  const dialog = await openModelDialog(page, card);
  const offered = await offeredModelIds(dialog);
  const chosen =
    offered.find((id) => /haiku/i.test(id)) ?? offered.find((id) => /claude/i.test(id)) ?? offered[0];
  await capture(page, `${SHOTS}/anthropic-catalogue.png`);
  // Keeping a model offered is what makes it *available* everywhere.
  await keepOffered(dialog, chosen);

  // BUG-292 — and choosing it in the composer is what makes it the model for
  // the turn. Two different decisions, by design, and the spec that conflated
  // them waited out its timeout on a correctly-disabled Send.
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, new RegExp(modelMenuName(chosen), "i"));
  await page
    .getByPlaceholder("How can I help you today?")
    .fill("Reply with exactly: SIMPLIFICATION LIVE");
  const send = page.getByRole("button", { name: "Send", exact: true });
  await expect(send).toBeEnabled({ timeout: 120_000 });
  await send.click();
  await expect(
    page.getByRole("main").getByText("SIMPLIFICATION LIVE", { exact: true }),
  ).toBeVisible({ timeout: 300_000 });
  await capture(page, `${SHOTS}/anthropic-turn.png`);
});

test("REM-PROJ-01 — a project card leads with work, lifecycle is one reach away", async () => {
  await page.goto(`${BASE}/#/projects`);
  const name = page.getByLabel(/Project name/i).first();
  if (await name.count()) {
    await name.fill("Round evidence");
    await page.getByRole("button", { name: /^Create project$/ }).first().click();
  }
  const card = page.locator("article").filter({ hasText: "Round evidence" }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });

  await expect(card.getByRole("button", { name: /^New chat$/ })).toBeVisible();
  await expect(card.getByRole("button", { name: /^Start in Build$/ })).toBeVisible();
  // Delete erases a managed project's folder. It is not the same size and one
  // click away as a button an owner presses all day.
  await expect(card.getByRole("button", { name: /^Delete$/ })).toHaveCount(0);
  await capture(page, `${SHOTS}/project-card.png`, card);

  await card.getByRole("button", { name: /More actions for Round evidence/ }).click();
  for (const action of ["Archive", "Move", "Delete"]) {
    await expect(page.getByRole("menuitem", { name: action })).toBeVisible();
  }
  await capture(page, `${SHOTS}/project-lifecycle-menu.png`);
  await page.keyboard.press("Escape");
});

test("REM-LAUNCH-02 — the unlock screen keeps Unlock primary and explains the branch", async () => {
  const context = page.context();
  const fresh = await context.newPage();
  await fresh.goto(`${BASE}/#/logout`);
  await fresh.goto(`${BASE}/#/workbench`);
  const unlock = fresh.getByRole("button", { name: /^Unlock Raiker$/ });
  if (await unlock.count()) {
    await expect(unlock).toHaveClass(/btn-primary/);
    await expect(
      fresh.getByRole("button", { name: "Use or create another instance" }),
    ).toBeVisible();
    await expect(fresh.getByText(/own workspace, models and memory/i)).toBeVisible();
    await capture(fresh, `${SHOTS}/unlock.png`);
  }
  await fresh.close();
});

test("the round ends with no uncaught console error", async () => {
  // The rule the live manual test plan sets, and the one BUG-296 was filed to
  // protect: a round that learns to ignore one console error has learned to
  // ignore the next.
  expect(consoleErrors).toEqual([]);
});
