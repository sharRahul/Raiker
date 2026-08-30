/**
 * B9 against a running `raiker-web` — the repository code map.
 *
 * The gap this closes is that every turn started cold. Build knew the workspace
 * root and nothing about what was in it, so finding where something is defined
 * meant guessing a search pattern and reading the misses. This spec drives the
 * whole path through the product with a real provider:
 *
 *   1. connecting a repository builds its map, and Build says what the map holds;
 *   2. a real turn calls `code_map_search` and quotes back the file and the line
 *      range the declaration is actually on — a fact no model could invent;
 *   3. the owner's off switch is real: with the capability turned off the same
 *      prompt is refused by name, not answered from a stale index;
 *   4. after an approved write, the map describes the file as it is now.
 *
 * Prerequisites:
 *   1. `raiker-web --workspace <fresh ws> --port 8765 --no-browser` with
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (added through the UI below)
 *   3. `RAIKER_LIVE_WORKSPACE` pointing at that same workspace directory
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Code-map-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const MODEL = "claude-haiku-4-5-20251001";

// The declaration everything below turns on. Its name appears nowhere else, and
// its line range is a fact about the file rather than something a model could
// produce from training — so an answer that states it came from the index.
const SYMBOL = "reconcile_meridian_ledger";

test.describe.configure({ mode: "serial" });

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
  await signInAsOwner(target, BASE, { user: "owner", password: PASSWORD });
}

async function openCapability(label: string) {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByPlaceholder("Search capabilities…");
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill(label);
  // Exact match: "Code map" is a prefix of other capability labels, and toggling
  // a neighbouring capability would make this spec assert nothing.
  const header = page.getByRole("button", { name: label, exact: true });
  await expect(header).toBeVisible({ timeout: 30_000 });
  const card = page.locator(".cap.card").filter({ has: header });
  if ((await header.getAttribute("aria-expanded")) !== "true") await header.click();
  await expect(card.locator(".cap-detail")).toBeVisible({ timeout: 10_000 });
  return card;
}

async function setCapability(label: string, action: "Turn on" | "Turn off", reason: string) {
  const card = await openCapability(label);
  const control = card.getByRole("button", { name: action });
  await expect(control).toBeVisible({ timeout: 10_000 });
  await control.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await dialog.getByLabel("Reason (required)").fill(reason);
  const token = dialog.getByLabel(/Confirmation token/);
  if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
  const ack = dialog.getByRole("checkbox");
  if (await ack.isVisible().catch(() => false)) await ack.check();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

async function buildComposer() {
  return page.getByPlaceholder(/Describe what you want built|Describe the change in/i).first();
}

async function setCapabilityIfOffered(
  label: string,
  action: "Turn on" | "Turn off",
  reason: string,
) {
  const card = await openCapability(label);
  if (await card.getByRole("button", { name: action }).isVisible().catch(() => false)) {
    await setCapability(label, action, reason);
  }
}

async function newBuild() {
  await page.goto(`${BASE}/#/build`);
  await expect(await buildComposer()).toBeVisible({ timeout: 30_000 });
  // The repositories panel sits above the transcript and stays open across
  // navigation, so close it before a turn: the answer is what the next
  // assertions and screenshots are about.
  const close = page.getByRole("button", { name: "Close repositories" });
  if (await close.isVisible().catch(() => false)) await close.click();
}

async function ask(prompt: string) {
  const answers = page.locator(".answer");
  const before = await answers.count();
  const composer = await buildComposer();
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
  await expect.poll(async () => answers.count(), { timeout: 60_000 }).toBeGreaterThan(before);
  return answers.last();
}

async function openRepositories() {
  await newBuild();
  const panel = page.getByRole("region", { name: "Repositories" });
  // Idempotent: the panel's open state survives navigation within the app, so a
  // blind click would close a panel an earlier scenario left open.
  if (!(await panel.isVisible().catch(() => false))) {
    await page.locator("button.repo-button").click();
  }
  await expect(panel).toBeVisible({ timeout: 30_000 });
  return panel;
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  await signIn(page);
});

test.afterAll(async () => await context?.close());

test("a provider key is added through the UI and a model selected", async () => {
  test.setTimeout(240_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");

  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await expect(card.locator("code").filter({ hasText: /Haiku 4\.5/i })).toBeVisible({
    timeout: 30_000,
  });
  await capture(page, join(SHOTS, "b9-model-connected.png"));
});

test("the code map is off until the owner turns it on, and Build says so", async () => {
  test.setTimeout(240_000);

  // An account with no decision recorded is fail-closed: Raiker does not index
  // the owner's tree because it could. Turning it off explicitly first makes the
  // scenario repeatable against a workspace an earlier run already touched,
  // while asserting the same thing — off means the panel says so and offers
  // nothing to press.
  // On a fresh workspace the capability is already off and there is nothing to
  // press; on one an earlier run touched, turning it off restores that resting
  // state. Either way the assertion below is about the same thing.
  await setCapabilityIfOffered("Code map", "Turn off", "checking the resting state of the code map");

  const panel = await openRepositories();
  const map = panel.getByRole("region", { name: "Code map" });
  await expect(map).toContainText(/indexing is off/i, { timeout: 30_000 });
  await expect(map.getByRole("button", { name: /build index/i })).toBeDisabled();
  await capture(page, join(SHOTS, "b9-code-map-off-by-default.png"));

  await setCapability("Code map", "Turn on", "indexing this repository so Build can find code");
});

test("connecting a repository builds its map, and Build says what the map holds", async () => {
  test.setTimeout(240_000);
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE").not.toBe("");

  // A small repository with the target declaration buried in it, plus a decoy
  // file that *mentions* the name without declaring it — so an answer that
  // names the right file and line range came from an index of declarations
  // rather than from a substring match.
  mkdirSync(join(WORKSPACE, "ledger-app", "services"), { recursive: true });
  // The last scenario adds a file through the product. Removing it here is what
  // keeps the counts below exact on a workspace an earlier run already used —
  // and the counts are the point: they prove the scan really read the tree.
  rmSync(join(WORKSPACE, "ledger-app", "services", "audit.py"), { force: true });
  writeFileSync(
    join(WORKSPACE, "ledger-app", "services", "ledger.py"),
    [
      '"""Ledger reconciliation."""',
      "",
      "",
      "class LedgerReconciler:",
      '    """Reconciles ledgers."""',
      "",
      "    def totals(self) -> int:",
      "        return 0",
      "",
      "",
      `def ${SYMBOL}(period: str) -> int:`,
      '    """Reconcile the Meridian ledger for one period."""',
      "    return LedgerReconciler().totals()",
      "",
    ].join("\n"),
    "utf-8",
  );
  writeFileSync(
    join(WORKSPACE, "ledger-app", "README.md"),
    `# Ledger app\n\nSee ${SYMBOL} in the services package.\n`,
    "utf-8",
  );

  const panel = await openRepositories();
  const row = panel.locator("li.repo").filter({ hasText: "ledger-app" });
  const alreadyConnected = (await row.count()) > 0;
  if (!alreadyConnected) {
    await panel.getByLabel(/folder inside this workspace/i).fill("ledger-app");
    await panel.getByRole("button", { name: /connect repository/i }).click();
    await expect(row).toBeVisible({ timeout: 60_000 });
  }

  // Point Build at it. The card describes the repository Build is actually
  // working in, which is the one the git tools and the agent's own reads resolve
  // against — so selecting is what makes it the subject.
  const use = row.getByRole("button", { name: "Use", exact: true });
  if (await use.isVisible().catch(() => false)) await use.click();
  await expect(row.getByText("Active")).toBeVisible({ timeout: 30_000 });

  const map = panel.getByRole("region", { name: "Code map" });
  await expect(map).toBeVisible({ timeout: 60_000 });
  await expect(map).toContainText(/ledger-app/, { timeout: 60_000 });
  if (alreadyConnected) {
    // The repository was connected by an earlier run, so its map was built then
    // and still describes the tree as it was. Pressing the owner's own rebuild
    // control is what makes the counts below about *this* run's files.
    await map.getByRole("button", { name: /rebuild index/i }).click();
  }
  await expect(map).toContainText(/2 files, 3 declarations/i, { timeout: 60_000 });
  await capture(page, join(SHOTS, "b9-code-map-built-on-connect.png"));
});

test("a real turn finds the declaration by name and quotes back its line range", async () => {
  test.setTimeout(420_000);
  await newBuild();
  const answer = await ask(
    `Use the code_map_search tool to find where ${SYMBOL} is defined in this repository. ` +
      "Then tell me, in one sentence, the exact file path and the line range the tool " +
      "reported. Do not read any file.",
  );

  // The file the declaration is really in — not the README that mentions it.
  await expect(answer).toContainText(/services\/ledger\.py/, { timeout: 60_000 });
  // Lines 11–13 of the file written above. A model that had not been handed the
  // index could not produce this.
  await expect(answer).toContainText(/11/, { timeout: 60_000 });
  await capture(page, join(SHOTS, "b9-code-map-search-answer.png"));
});

test("with the capability turned off the same prompt is refused by name", async () => {
  test.setTimeout(420_000);
  await setCapability("Code map", "Turn off", "checking the owner's off switch really holds");

  await newBuild();
  const answer = await ask(
    `Call code_map_search once for ${SYMBOL} and tell me exactly what the tool returned, ` +
      "verbatim, including any error type.",
  );

  await expect(answer).toContainText(/code_map_gate_disabled/i, { timeout: 60_000 });
  await capture(page, join(SHOTS, "b9-code-map-gate-off.png"));

  await setCapability("Code map", "Turn on", "restoring the code map for the refresh check");
});

test("after an approved write the map describes the file as it is now", async () => {
  test.setTimeout(420_000);
  // The write has to be able to happen at all: an account with no decision
  // recorded is fail-closed, so the approval would otherwise be record-only and
  // there would be no landed change for the map to catch up with.
  await setCapability("Approval execution relay", "Turn on", "approvals should do what they say");
  await setCapability("File writes", "Turn on", "letting the approved write really land");

  await newBuild();
  await ask(
    "Use write_file to create ledger-app/services/audit.py containing exactly:\n" +
      "def audit_meridian_trail():\n    return True\n",
  );

  // Approve the write the turn proposed. The map refresh happens at the single
  // point an approved file mutation is known to have really landed.
  await page.goto(`${BASE}/#/approvals`);
  await page.getByLabel("Sort approvals").selectOption({ label: "Newest first" });
  const row = page
    .getByRole("row", { name: /write_file|File write/i })
    .filter({ hasText: /pending/i })
    .first();
  await expect(row).toBeVisible({ timeout: 60_000 });
  await row.getByRole("button", { name: "Review" }).click();
  await expect(page.getByRole("heading", { name: /^Review / })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Approve and execute once" }).click();
  await expect(page.getByText(/Executed once/i).first()).toBeVisible({ timeout: 120_000 });

  await newBuild();
  const answer = await ask(
    "Use code_map_search to find audit_meridian_trail, then tell me in one sentence the " +
      "file path the tool reported. Do not read any file.",
  );

  await expect(answer).toContainText(/services\/audit\.py/, { timeout: 60_000 });
  await capture(page, join(SHOTS, "b9-code-map-refreshed-after-write.png"));
});
