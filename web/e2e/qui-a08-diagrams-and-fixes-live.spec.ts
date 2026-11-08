/**
 * QUI-A08 diagrams and the 2026-11-08 small-fixes round, against a running
 * host and a real hosted model.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `raiker-web --workspace <ws> --port 8765 --no-browser`
 *      (`scripts/reset_live_workspace.py` first).
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own Models dialog; none is written here.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "QUI-A08 diagrams and
 * the small-fixes round"): RT-DGM-01 … RT-DGM-05, RT-FIX-01 … RT-FIX-05.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";

import { modelName } from "../src/lib/modelPresentation";
import { settled } from "./destinations";
import { chooseModelForTurn, hostedProviderCard, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../output/playwright/2026-11-08-qui-a08-diagrams";

async function open(page: Page, hash: string): Promise<void> {
  await page.goto(`${BASE}/${hash}`);
  await settled(page);
}

async function shot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false });
}

/** Send one prompt in a new chat and return the answer once it has finished. */
async function ask(page: Page, prompt: string): Promise<Locator> {
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const answer = page.locator(".message-group-raiker").last();
  await expect(answer).toBeVisible({ timeout: 180_000 });
  await expect(answer.locator(".response-actions")).toBeVisible({ timeout: 240_000 });
  return answer;
}

function verbatim(...fences: string[]): string {
  return (
    "I am checking how Raiker draws answer blocks, using my own data. Please show me these " +
    "blocks in this conversation by sending them back unchanged, with no other text:\n\n" +
    fences.join("\n\n")
  );
}

function fence(kind: string, payload: unknown): string {
  return "```raiker:" + kind + "\n" + JSON.stringify(payload) + "\n```";
}

const SIGN_IN = {
  caption: "Signing in on another device",
  direction: "down",
  nodes: [
    { id: "start", label: "Open Raiker", shape: "round" },
    { id: "password", label: "Password right?", shape: "diamond" },
    { id: "code", label: "Ask for the two-step code" },
    { id: "valid", label: "Code right?", shape: "diamond" },
    { id: "in", label: "Signed in", shape: "round" },
  ],
  edges: [
    { from: "start", to: "password" },
    { from: "password", to: "code", label: "yes" },
    { from: "password", to: "start", label: "no" },
    { from: "code", to: "valid" },
    { from: "valid", to: "in", label: "yes" },
    { from: "valid", to: "code", label: "no" },
  ],
};

test("RT-DGM-01 — Anthropic connects through Add model with its workspace ID", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(360_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
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

test("RT-DGM-02 — a declared diagram is drawn: boxes, arrows, a dashed loop back, a list for screen readers", async ({ page }) => {
  test.setTimeout(360_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const answer = await ask(page, verbatim(fence("diagram", SIGN_IN)));
  const block = answer.locator('section.answer-block[data-block="diagram"]');
  await expect(block).toBeVisible({ timeout: 60_000 });
  await expect(block.locator("figure.diagram svg")).toHaveAttribute("aria-hidden", "true");
  await expect(block.locator("g.node")).toHaveCount(5);
  await expect(block.locator("path.edge")).toHaveCount(6);
  await expect(block.locator("path.edge.back")).toHaveCount(2);
  await expect(block.locator("polygon.shape")).toHaveCount(2);
  await expect(block.locator("ol.sr-only li").first()).toHaveText(/Open Raiker: leads to Password right\?/);
  await expect(block.getByRole("button", { name: "PNG" })).toBeVisible();
  await expect(block.getByRole("button", { name: "CSV" })).toHaveCount(0);
  await block.scrollIntoViewIfNeeded();
  await shot(page, "01-diagram-light");

  await block.getByRole("button", { name: "Show as text" }).click();
  await expect(block.getByText(/Password right\? → Ask for the two-step code \(yes\); Open Raiker \(no\)/)).toBeVisible();
  await shot(page, "02-diagram-as-text");
  await block.getByRole("button", { name: "Show as block" }).click();

  const download = page.waitForEvent("download");
  await block.getByRole("button", { name: "PNG" }).click();
  expect((await download).suggestedFilename()).toBe("signing-in-on-another-device.png");

  await page.emulateMedia({ colorScheme: "dark" });
  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
  await block.scrollIntoViewIfNeeded();
  await shot(page, "03-diagram-dark");
  await page.evaluate(() => document.documentElement.removeAttribute("data-theme"));
  await page.emulateMedia({ colorScheme: "light" });

  // Pin, for RT-DGM-05: a stored turn's block files into the Library.
  const unpin = block.getByRole("button", { name: "Unpin" });
  if (!(await unpin.isVisible().catch(() => false))) await block.getByRole("button", { name: /^Pin/ }).click();
  await expect(unpin).toBeVisible({ timeout: 30_000 });
});

test("RT-DGM-03 — a malformed diagram keeps its prose and says why it was not drawn", async ({ page }) => {
  test.setTimeout(360_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const broken = { nodes: [{ id: "a", label: "Start" }], edges: [{ from: "a", to: "nowhere" }] };
  const answer = await ask(page, verbatim(fence("diagram", broken)));
  await expect(answer.getByText("An arrow pointed at a box the diagram did not have.")).toBeVisible({ timeout: 60_000 });
  await expect(answer.locator(".refused .code")).toHaveText("diagram_edge_unknown_node");
  await shot(page, "04-diagram-refused");
});

test("RT-DGM-04 — the model chooses a diagram for a branching flow", async ({ page }) => {
  test.setTimeout(360_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const answer = await ask(
    page,
    "Show me, as a diagram, how a pull request goes from opened to merged when review can ask for changes and CI can fail. Keep it to at most eight steps.",
  );
  const block = answer.locator('section.answer-block[data-block="diagram"]');
  await expect(block).toBeVisible({ timeout: 60_000 });
  expect(await block.locator("g.node").count()).toBeGreaterThanOrEqual(3);
  await block.scrollIntoViewIfNeeded();
  await shot(page, "05-diagram-model-chosen");
});

test("RT-DGM-05 — the diagram pinned in RT-DGM-02 is drawn in the Library", async ({ page }) => {
  test.setTimeout(360_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/work?tab=library");
  const row = page.getByText("Signing in on another device").first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.click();
  await expect(page.locator('section.answer-block[data-block="diagram"] figure.diagram svg').first()).toBeVisible({ timeout: 30_000 });
  await shot(page, "06-library-pinned-diagram");
});

test("RT-FIX-01 — a stopped turn says it was stopped once", async ({ page }) => {
  test.setTimeout(360_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(
    "Write a detailed 1,500-word essay on the history of the printing press, in plain prose.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const stop = page.getByRole("button", { name: /^Stop/ }).first();
  await expect(stop).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(2_500);
  await stop.click();
  await expect(page.locator(".stopped-line")).toHaveCount(1, { timeout: 60_000 });
  const last = page.locator(".message-group-raiker").last();
  await expect(last.getByText("Stopped by user at a safe boundary.")).toHaveCount(0);
  await expect(last.getByText("Stopped at your request, at a safe boundary.")).toHaveCount(0);
  await shot(page, "07-stopped-once");
});

test("RT-FIX-02 — Sessions opens a record from the keyboard", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/sessions");
  const title = page.locator("tr.row-btn button.session-title").first();
  await expect(title).toBeVisible({ timeout: 30_000 });
  await title.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("link", { name: "View audit events" })).toBeVisible({ timeout: 30_000 });
  await expect(title).toHaveAttribute("aria-current", "true");
  await shot(page, "08-sessions-keyboard");
});

test("RT-FIX-03 — Build says nothing about standing permissions before its read answers", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await open(page, "#/build");
  await page.waitForTimeout(3_000);
  await expect(page.getByText("Raiker could not read your standing permissions for this turn.")).toHaveCount(0);
  await shot(page, "09-build-fresh-load");
});

test("RT-FIX-04 — Settings lets the owner leave the instant a save answers", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  page.on("dialog", (dialog) => void dialog.dismiss());
  await open(page, "#/settings?tab=general");
  const select = page.getByRole("combobox", { name: "Answer style" });
  await expect(select).toBeEnabled({ timeout: 30_000 });
  const current = await select.inputValue();
  const options = await select.locator("option").evaluateAll((els) => els.map((el) => (el as HTMLOptionElement).value));
  await select.selectOption(options.find((value) => value !== current)!);
  const saved = page.waitForResponse((r) => r.url().includes("/api/settings") && r.request().method() === "PUT");
  await page.getByRole("button", { name: "Save changes" }).click();
  await saved;
  await page.evaluate(() => (window.location.hash = "#/new-chat"));
  await expect(page).toHaveURL(/#\/new-chat/, { timeout: 10_000 });
  await expect(page.getByLabel("Prompt", { exact: true })).toBeVisible({ timeout: 30_000 });
  await shot(page, "10-settings-left-after-save");
});

test("RT-FIX-05 — keeping a model a workspace already keeps completes instead of timing out", async ({ page }) => {
  // The harness half of `useAnthropic`: RT-DGM-01 already kept the model, so
  // this is the workspace the web-access spec could not set up on.
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  await keepModelAvailable(page, card, MODEL);
  await expect(card.locator("code").filter({ hasText: modelName(MODEL) })).toHaveCount(1, { timeout: 30_000 });
});
