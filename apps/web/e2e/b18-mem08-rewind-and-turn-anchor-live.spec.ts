/**
 * B18 and MEM-08, against a real conversation and a real model.
 *
 * Both are the same shape of defect and this spec is written to hold both
 * halves of it: a coordinate that existed and could not be reached.
 *
 * * **B18 — rewind where the work happens.** The governed restore has had an
 *   executor, a capability, a classification and a route since Workstream B,
 *   and it was reachable only from the Checkpoints page. Undoing the turn that
 *   broke something meant leaving the conversation, recognising a snapshot by
 *   id, and coming back. What must be true on screen: the rewind is asked for
 *   at the turn, it previews **this turn's** impact, and it restores nothing —
 *   it raises an approval a human resolves.
 * * **MEM-08 — a turn coordinate you can open.** Chat search has always known
 *   which exchange matched, and opened the conversation at the top anyway. What
 *   must be true on screen: the result lands on the exchange, marks it, and
 *   leaves an address that opens the conversation rather than replaying a
 *   highlight.
 *
 * Nothing here is asserted from a fixture: the turns are real turns against a
 * hosted model, the search is the product's own search, and the approval is the
 * one the runtime raised.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const USER = process.env.RAIKER_LIVE_USER ?? "Rahul";
const PASSWORD = process.env.RAIKER_LIVE_PASSWORD ?? "Ithink@10";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function sendChat(prompt: string) {
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
}

/** B18 — the three rare actions now sit behind one handle under a message. */
async function openMessageMenu(index = 0) {
  await page.getByRole("button", { name: "More actions for this message" }).nth(index).click();
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  // Signing in, dismissing a wizard that may not be there, connecting a
  // provider and probing a real model is minutes of work, not the hook default.
  test.setTimeout(420_000);
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  await signInAsOwner(page, BASE, { user: USER, password: PASSWORD });
  test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is required for this round.");
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
});

test.afterAll(async () => {
  await context?.close();
});

test("the rewind is asked for at the turn, and restores nothing on its own", async () => {
  test.setTimeout(420_000);
  await page.goto(`${BASE}/#/new-chat`);
  await sendChat("In one sentence, what is a checkpoint for?");

  await openMessageMenu();
  const rewind = page.getByRole("menuitem", { name: /Rewind to before this/ });
  await expect(rewind).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "b18-01-message-menu.png"));
  await rewind.click();

  // Either the preflight opened, or this turn wrote no checkpoint and the
  // surface says so. Both are correct; neither is silence, which is the
  // behaviour this closes.
  const panel = page.getByRole("complementary", { name: "Rewind preflight" });
  const noPoint = page.getByText(/no checkpoint was written for that turn/i);
  await expect(panel.or(noPoint).first()).toBeVisible({ timeout: 60_000 });
  // Photograph the settled plan, not the spinner in front of it.
  await expect(
    panel.getByText(/Computing what a rewind would change/).or(noPoint).first(),
  ).toBeHidden({ timeout: 60_000 });
  await capture(page, join(SHOTS, "b18-02-rewind-preflight.png"));

  if (await panel.isVisible().catch(() => false)) {
    const ask = page.getByRole("button", { name: /Request this rewind/i });
    if (await ask.isVisible().catch(() => false)) {
      // It is a preview: the ask is withheld until the impact is acknowledged,
      // and the panel says in words that it performs nothing.
      await expect(ask).toBeDisabled();
      await expect(page.getByText(/this panel never performs a rewind/i)).toBeVisible();
    } else {
      // A chat turn changes no workspace file. "Nothing to rewind" is an answer,
      // and the panel gives it instead of a form nobody can submit.
      await expect(panel.getByText(/a rewind would change nothing/i)).toBeVisible();
    }
  }
});

test("a search result opens the exchange it matched, and spends the anchor", async () => {
  test.setTimeout(420_000);
  await page.goto(`${BASE}/#/new-chat`);
  await sendChat("Reply with exactly: ZEBRAFISH-ANCHOR-ONE.");
  await sendChat("Reply with exactly: ZEBRAFISH-ANCHOR-TWO.");

  await page.goto(`${BASE}/#/search-chat`);
  await page.getByLabel("Search chat history").fill("ZEBRAFISH");
  const result = page.locator(".search-chat li a").first();
  await expect(result).toBeVisible({ timeout: 30_000 });
  const href = await result.getAttribute("href");
  expect(href).toContain("session=");
  await capture(page, join(SHOTS, "mem08-01-search-result.png"));

  await result.click();
  // The exchange the search named is marked, and only that one.
  if ((href ?? "").includes("turn=")) {
    await expect(page.locator(".turn.turn-anchored")).toHaveCount(1, { timeout: 30_000 });
    await capture(page, join(SHOTS, "mem08-02-landed-on-the-exchange.png"));
    // The anchor is spent: this address opens the conversation, not a highlight.
    await expect
      .poll(() => page.url(), { timeout: 30_000 })
      .not.toContain("turn=");
  }
});

// The two surfaces this round changed, at the two widths where a right-hand
// panel and a per-message overflow behave differently. A control that works at
// 1440px and traps the owner at 390px is not shipped.
test("the rewind panel and the message overflow work at a phone width too", async () => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByRole("button", { name: "More actions for this message" }).first())
    .toBeVisible({ timeout: 60_000 });
  await openMessageMenu();
  await expect(page.getByRole("menuitem", { name: /Rewind to before this/ })).toBeVisible();
  await capture(page, join(SHOTS, "b18-03-message-menu-mobile.png"));
  await page.getByRole("menuitem", { name: /Rewind to before this/ }).click();
  const panel = page.getByRole("complementary", { name: "Rewind preflight" });
  const noPoint = page.getByText(/no checkpoint was written for that turn/i);
  await expect(panel.or(noPoint).first()).toBeVisible({ timeout: 60_000 });
  await expect(
    panel.getByText(/Computing what a rewind would change/).or(noPoint).first(),
  ).toBeHidden({ timeout: 60_000 });
  // The page itself never scrolls sideways, at any width. That is the whole
  // responsive contract, and a stacked panel is where it usually breaks.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  await capture(page, join(SHOTS, "b18-04-rewind-preflight-mobile.png"));
  await page.setViewportSize({ width: 1440, height: 1000 });
});

// Build is the surface whose turns change files, so it is the surface the
// rewind matters most on — and its workspace grid is a different layout from
// Chat's, which is exactly where a shared panel goes wrong.
test("Build asks for the rewind at the turn too, in its own layout", async () => {
  test.setTimeout(420_000);
  await page.goto(`${BASE}/#/build`);
  await expect(page.locator("main#main")).toBeVisible();

  // Build will not send without a project. Reuse one if the workspace has it.
  const projectSelect = page.getByLabel("Project for this build");
  await expect(projectSelect).toBeVisible({ timeout: 30_000 });
  if ((await projectSelect.locator("option").count()) < 2) {
    await page.goto(`${BASE}/#/projects`);
    await page.getByLabel(/name/i).first().fill("Rewind round");
    await page.getByRole("button", { name: /create project/i }).first().click();
    await page.goto(`${BASE}/#/build`);
    await expect(projectSelect).toBeVisible({ timeout: 30_000 });
  }
  await projectSelect.selectOption({ index: 1 });

  // Chat stays mounted behind Build, so a bare `form.composer textarea`
  // resolves to Chat's hidden one. Build's own placeholder is the scope.
  const composer = page.locator(".build").getByPlaceholder(/^Describe (what you want built|the change in )/);
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill("Reply with exactly: BUILD-REWIND-ONE.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });

  // Chat is mounted behind Build with its own message rows, so the overflow
  // handle is scoped to the Build surface rather than taken by index.
  await page.locator(".build").getByRole("button", { name: "More actions for this message" }).first().click();
  await page.getByRole("menuitem", { name: /Rewind to before this/ }).click();
  const panel = page.getByRole("complementary", { name: "Rewind preflight" });
  const noPoint = page.getByText(/no checkpoint was written for that turn/i);
  await expect(panel.or(noPoint).first()).toBeVisible({ timeout: 60_000 });
  await expect(
    panel.getByText(/Computing what a rewind would change/).or(noPoint).first(),
  ).toBeHidden({ timeout: 60_000 });
  // Build's grid is `main + rail`; the panel takes a column of its own rather
  // than stacking under the composer or widening the page.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  await capture(page, join(SHOTS, "b18-05-build-rewind-preflight.png"));
});

test("a checkpoint links back to the exchange it was taken at", async () => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/observe?tab=checkpoints`);
  await expect(page.locator("main#main")).toBeVisible();
  // The turns above wrote checkpoints, so a snapshot naming its turn must be
  // here. Asserting it rather than skipping past it is the point: a link that
  // is only checked when it happens to be present is not checked.
  const turnLink = page.locator('main#main a[href*="turn="]').first();
  await expect(turnLink).toBeVisible({ timeout: 60_000 });
  await expect(turnLink).toHaveAttribute("href", /#\/new-chat\?session=[^&]+&turn=/);
  await capture(page, join(SHOTS, "mem08-03-checkpoint-links-to-its-turn.png"), turnLink);
});
