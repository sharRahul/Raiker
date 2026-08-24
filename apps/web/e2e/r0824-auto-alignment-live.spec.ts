/**
 * FIXED-282 (BUG-218) — Auto's alignment check, against a real model.
 *
 * The unit and broker tests prove the rule. What only a live run proves is that
 * the rule survives contact with a real turn: that a real model writing a file
 * the owner asked for still runs unprompted under **Auto**, and that the same
 * turn writing an *existing* file nobody mentioned parks for a decision with the
 * path named.
 *
 * Both halves matter and the first one matters more. A check that withholds the
 * wrong thing makes Auto obstructive, and an obstructive Auto is one an owner
 * turns off — which leaves them worse protected than the defect did.
 *
 * Requires:
 *   1. `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com` on the running host
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (entered through the UI)
 *   3. `RAIKER_LIVE_WORKSPACE` pointing at the host's workspace, so the spec can
 *      plant the file the second half is about and read the result back
 */
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { dismissFirstRunModelSetup, refreshHostedReadiness, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const MODEL = "claude-haiku-4-5-20251001";

/** The file nobody asks about. Planted with content worth not losing. */
const UNRELATED = "ops/deploy.sh";
const UNRELATED_BODY = "#!/bin/sh\n# the real deployment script\n";

let context: BrowserContext;
let page: Page;

test.describe.configure({ mode: "serial" });

async function signIn(target: Page) {
  await target.goto(`${BASE}/#/workbench`);
  await expect(target.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
  await target.getByLabel("Username").fill("Rahul");
  await target.getByLabel("Password", { exact: true }).fill("Ithink@10");
  const confirm = target.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill("Ithink@10");
    await target.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await target.getByRole("button", { name: "Unlock Raiker", exact: true }).click();
  }
  const workbench = target.getByRole("heading", { name: /Welcome (to your Work Dashboard|back)/ });
  await expect(
    target.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(target);
  await expect(workbench.first()).toBeVisible({ timeout: 30_000 });
}

async function openCapability(label: string) {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByPlaceholder("Search capabilities…");
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill(label);
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  if ((await card.getByRole("button", { name: label }).getAttribute("aria-expanded")) !== "true") {
    await card.getByRole("button", { name: label }).click();
  }
  await expect(card.locator(".cap-detail")).toBeVisible({ timeout: 10_000 });
  return card;
}

async function setCapability(label: string, reason: string) {
  const card = await openCapability(label);
  const control = card.getByRole("button", { name: "Turn on" });
  if (!(await control.isVisible().catch(() => false))) return; // already on
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

async function newChat() {
  await page.goto(`${BASE}/#/new-chat`);
  const reset = page.getByRole("button", { name: "New chat", exact: true });
  if (await reset.isEnabled().catch(() => false)) await reset.click();
  await expect(page.getByPlaceholder("How can I help you today?")).toBeVisible({ timeout: 30_000 });
}

/**
 * Select the composer's **Auto** approval mode, the mode this spec is about.
 *
 * The trigger is labelled `Approval mode: <current>`, and the four choices are
 * `menuitemradio` rather than plain buttons — a `getByRole("button")` lookup
 * finds the trigger and never the option, which is how the first run of this
 * spec hung with the menu open.
 */
async function chooseAutoApproval() {
  const trigger = page.getByRole("button", { name: /^Approval mode:/ }).first();
  await expect(trigger).toBeVisible({ timeout: 30_000 });
  if (/Automatically approve/.test((await trigger.getAttribute("aria-label")) ?? "")) return;
  await trigger.click();
  await page
    .getByRole("menuitemradio", { name: /Automatically approve/ })
    .click();
  await expect(
    page.getByRole("button", { name: /^Approval mode: Automatically approve/ }),
  ).toBeVisible({ timeout: 15_000 });
}

async function ask(prompt: string) {
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
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
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE").not.toBe("");

  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await expect(card.locator("code")).toBeVisible({ timeout: 30_000 });

  await setCapability("File writes", "live-testing Auto's alignment check");
  await setCapability("Approval execution relay", "so an approval does what it says");
});

test("under Auto, a real turn writing the file it was asked for still runs unprompted", async () => {
  test.setTimeout(300_000);
  // The half that matters most. A check that withholds the wrong thing makes
  // Auto obstructive, and an obstructive Auto is one an owner switches off.
  const target = join(WORKSPACE, "alignment-notes.md");
  rmSync(target, { force: true });

  await refreshHostedReadiness(page, BASE, "Anthropic");
  await newChat();
  await chooseAutoApproval();
  await ask(
    'Call write_file exactly once with path "alignment-notes.md" and text ' +
      '"aligned". Then say only DONE.',
  );

  await expect(page.getByRole("main")).not.toContainText(/approval required|approval is needed/i);
  expect(existsSync(target), "the file the owner asked for was written").toBe(true);
  expect(readFileSync(target, "utf8")).toContain("aligned");
  await page.screenshot({ path: `${SHOTS}/r0824-auto-aligned-write-ran.png`, fullPage: true });
});

test("under Auto, a change to an existing file the owner names still runs unprompted", async () => {
  test.setTimeout(300_000);
  // The false-positive half, and the one that decides whether Auto stays
  // switched on: naming a file *is* establishing it, so an ordinary edit to an
  // existing file must not start asking.
  mkdirSync(join(WORKSPACE, "ops"), { recursive: true });
  writeFileSync(join(WORKSPACE, UNRELATED), UNRELATED_BODY, "utf8");

  await refreshHostedReadiness(page, BASE, "Anthropic");
  await newChat();
  await chooseAutoApproval();
  await ask(
    `Call write_file exactly once with path "${UNRELATED}" and text "named". Then say only DONE.`,
  );

  await expect(page.getByRole("main")).not.toContainText(/approval required|approval is needed/i);
  expect(readFileSync(join(WORKSPACE, UNRELATED), "utf8")).toContain("named");
});

test("under Auto, the same write in a *later* turn waits, and the approval says which file", async () => {
  test.setTimeout(300_000);
  /**
   * The withholding half, arranged so a real model produces it deterministically.
   *
   * Naming a path in the prompt establishes it, so no prompt that instructs a
   * write can also be the unestablished case — which is the design working, and
   * is what made the first version of this test assert something impossible.
   * What *is* deterministic is the rule that establishment is **scoped to the
   * turn**: the previous turn named `ops/deploy.sh`, this one says only "do that
   * again", and this turn has established nothing. A model reliably repeats an
   * explicit instruction it was just given; the runtime reliably refuses to
   * treat last turn's context as this turn's authorisation.
   *
   * That is also the governance property worth photographing. Carrying
   * establishment across turns is how a review quietly becomes a standing grant
   * nobody issued.
   */
  const before = readFileSync(join(WORKSPACE, UNRELATED), "utf8");

  // Same conversation, next turn — deliberately not `newChat()`.
  await ask('Do exactly that again, with text "repeated". Then say only DONE.');

  await expect(page.getByRole("main")).toContainText(/approval required|approval is needed/i, {
    timeout: 60_000,
  });
  // Untouched: the turn that proposed it established nothing.
  expect(readFileSync(join(WORKSPACE, UNRELATED), "utf8")).toBe(before);

  await page.goto(`${BASE}/#/approvals`);
  await page.getByLabel("Sort approvals").selectOption({ label: "Newest first" });
  const row = page.getByRole("row", { name: /Write file/i }).first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByRole("button", { name: "Review" }).click();

  // Evidence on the decision: the owner is answering a stated question rather
  // than meeting an unexplained interruption.
  await expect(page.getByRole("main")).toContainText(/Automatic approval was withheld/i, {
    timeout: 30_000,
  });
  await expect(page.getByRole("main")).toContainText(/ops\/deploy\.sh/);
  await page.screenshot({ path: `${SHOTS}/r0824-auto-withheld-approval.png`, fullPage: true });
});
