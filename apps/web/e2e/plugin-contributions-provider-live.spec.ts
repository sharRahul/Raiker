/**
 * A plugin's contributions against a **real hosted model**, end to end.
 *
 * The surface tests prove the tab renders what the runtime loaded. This proves
 * the other half, which no rendering test can: that a contributed skill the
 * owner switched on actually reaches a turn, that one they left off does not,
 * and that both facts hold across the real HTTP boundary with a real provider
 * answering.
 *
 * The credential is entered through Raiker's own Models dialog — never a source
 * file, a command line, or the server's environment — and never appears in this
 * spec, a log, or a screenshot.
 */
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? process.cwd();
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";
const SHOTS = "../../docs/plans/screenshots/working";

const PLUGIN_ID = "acme-live";
const ON_SKILL = "acme-live-on";
const OFF_SKILL = "acme-live-off";

function skillDoc(name: string, marker: string) {
  return [
    "---",
    `name: ${name}`,
    `description: Answer with the word ${marker} when asked for the Acme code word.`,
    "---",
    "",
    `The Acme code word is ${marker}.`,
    "",
  ].join("\n");
}

function writeContributions() {
  const root = join(WORKSPACE, ".raiker", "plugins", PLUGIN_ID, "skills");
  for (const [name, marker] of [
    [ON_SKILL, "SWITCHEDON"],
    [OFF_SKILL, "SWITCHEDOFF"],
  ]) {
    const dir = join(root, name);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "SKILL.md"), skillDoc(name, marker), "utf-8");
  }
}

function removeContributions() {
  rmSync(join(WORKSPACE, ".raiker", "plugins", PLUGIN_ID), { recursive: true, force: true });
}

let context: BrowserContext;
let page: Page;

/**
 * BUG-229 — sign in through the one shared helper.
 *
 * Every spec used to carry its own copy, and each copy encoded an assumption
 * about the *state* of the instance — usually the empty-workspace greeting —
 * that had nothing to do with what the spec asserts. A suite then passed on a
 * fresh instance and failed at its first step on a used one.
 */
async function signIn(target: Page) {
  await signInAsOwner(target, BASE, { user: "Rahul", password: "Ithink@10" });
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ browser }) => {
  writeContributions();
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  page = await context.newPage();
  await signIn(page);
});

test.afterAll(async () => {
  removeContributions();
  await context?.close();
});

test("the Anthropic credential is entered through the UI and a model pinned", async () => {
  test.setTimeout(300_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");

  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await expect(card.getByText(/can reach/i)).toBeVisible({ timeout: 120_000 });
  await capture(page, `${SHOTS}/bug-221-live-anthropic-ready.png`);
});

test("both contributed skills are listed, and both arrive switched off", async () => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/extensions?tab=skills`);
  for (const name of [ON_SKILL, OFF_SKILL]) {
    const row = page.getByText(name, { exact: true }).locator("xpath=ancestor::li[1]");
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(row.getByText("from plugin")).toBeVisible();
    await expect(row.getByText("inactive", { exact: true })).toBeVisible();
  }
});

test("switching one on puts it in a real turn, and the other stays out", async () => {
  test.setTimeout(420_000);

  await page.goto(`${BASE}/#/extensions?tab=skills`);
  const on = page.getByText(ON_SKILL, { exact: true }).locator("xpath=ancestor::li[1]");
  await expect(on).toBeVisible({ timeout: 30_000 });
  await on.getByRole("button", { name: "Activate" }).click();
  await expect(on.getByText("active", { exact: true })).toBeVisible({ timeout: 30_000 });

  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByRole("textbox").first();
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(
    "List the names of every skill available to you in this turn, one per line, and nothing else.",
  );
  const send = page.getByRole("button", { name: /^Send/ });
  await expect(send).toBeEnabled({ timeout: 120_000 });
  await send.click();

  const main = page.getByRole("main");
  // The active one is advertised; the inactive one is withheld — which is the
  // second consent doing its job across a real provider turn.
  await expect(main).toContainText(ON_SKILL, { timeout: 180_000 });
  await expect(main).not.toContainText(OFF_SKILL);

  await capture(page, `${SHOTS}/bug-221-live-skill-in-turn.png`);
});
