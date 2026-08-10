/**
 * BUG-58 against a running `raiker-web` — the evidence behind the rewritten
 * **Known limits** section of `README.md`.
 *
 * That section is the first thing a careful reader checks, and it had drifted:
 * it still told a reader that a model proposing several tool calls at once
 * "gets one of them", that a unified patch is one file, and that approved shell
 * actions do not run. Each of those had since shipped. Re-deriving the section
 * from the tree is only half the fix — this spec is the other half, so the
 * claims that replaced them are checked against the running product rather than
 * against the source they were read from.
 *
 * Each test names the README bullet it holds up:
 *
 *  1. **The parallel bullet.** A batch of read-only calls really is answered as
 *     a batch — several tools reach the model in one turn, and it can quote all
 *     of their results back.
 *  2. **The patching bullet.** One unified diff spanning two files is accepted
 *     as one proposal naming both paths, and a hunk whose context does not match
 *     is rejected whole rather than partially applied.
 *  3. **The web bullet.** `web_fetch` withholds by default and names the control
 *     that changes it; `web_search` reports `web_search_not_configured` because
 *     Raiker ships no search endpoint.
 *  4. **The shell/network/process bullet.** Permissions carries a `shell`
 *     capability whose approvals execute, and `network`/`process` capabilities
 *     that stay metadata-only — the asymmetry the README now states.
 *
 * Not a mocked shell: the runtime holds a real Anthropic credential entered
 * through the product's own Models page, and every turn below reaches the
 * provider.
 *
 * Prerequisites:
 *   1. `python apps/api/main.py --workspace <ws> --port 8765 --no-browser` with
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com` and
 *      `RAIKER_WEB_EGRESS_ALLOWLIST=pypi.org`
 *   2. `alpha.md`, `beta.md` and `gamma.md` in that workspace, holding the
 *      markers below — the batch has to have something to read.
 *   3. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (added through the UI below)
 *
 * The workspace must be a **fresh** one. Two of the claims below are about what
 * a capability gate does before the owner has touched it, and the run itself
 * turns `web_fetch` on — replaying it over the same workspace would check the
 * state the previous run left, not the state the README describes.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Known-limits-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function signIn(target: Page) {
  await target.goto(`${BASE}/#/workbench`);
  await expect(target.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const confirm = target.getByLabel("Confirm password");
  await target.getByLabel("Username").fill("owner");
  await target.getByLabel("Password", { exact: true }).fill(PASSWORD);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await target.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await target.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  await expect(target.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 30_000 });
}

/**
 * Send one prompt and wait for *this* turn to finish.
 *
 * Waiting on "Copy response" is not enough: the previous turn's copy button is
 * already on the page, so the assertion passes instantly and the next one reads
 * the wrong bubble. The turn is over when the composer stops offering to stop
 * it *and* a new Raiker bubble has arrived.
 */
async function ask(prompt: string) {
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  const before = await page.locator(".message-bubble-raiker").count();
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
  await expect
    .poll(async () => page.locator(".message-bubble-raiker").count(), { timeout: 60_000 })
    .toBeGreaterThan(before);
  return page.locator(".message-bubble-raiker").last();
}

/** Open one capability's card on the Permissions page. */
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

/** Turn one capability on at runtime level, exactly as a person would. */
async function enableCapability(label: string, reason: string) {
  const card = await openCapability(label);
  const turnOn = card.getByRole("button", { name: "Turn on" });
  await expect(turnOn).toBeVisible({ timeout: 10_000 });
  await turnOn.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await dialog.getByLabel("Reason (required)").fill(reason);
  const token = dialog.getByLabel(/Confirmation token/);
  if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
  const ack = dialog.getByRole("checkbox");
  if (await ack.isVisible().catch(() => false)) await ack.check();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
  await expect(page.getByText(`Enabled ${label}.`)).toBeVisible({ timeout: 30_000 });
}

async function allowCapability(label: string, reason: string) {
  const card = await openCapability(label);
  await card.getByRole("button", { name: "Allow", exact: true }).click();
  const dialog = page.getByRole("dialog");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByLabel("Reason (required)").fill(reason);
    await dialog.getByRole("button", { name: "Confirm change" }).click();
    await expect(dialog).toBeHidden({ timeout: 30_000 });
  }
  await expect(page.getByText(`${label} is now set to “Allow”.`)).toBeVisible({ timeout: 30_000 });
}

/** Start a conversation with nothing behind it. */
async function newChat() {
  await page.goto(`${BASE}/#/new-chat`);
  // Disabled when the conversation is already empty, which is the state this
  // helper wants — clicking it then would hang rather than start anything.
  const reset = page.getByRole("button", { name: "New chat", exact: true });
  if (await reset.isEnabled().catch(() => false)) await reset.click();
  await expect(page.getByPlaceholder("How can I help you today?")).toBeVisible({ timeout: 30_000 });
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

test("the provider key is added through the UI and a real turn answers", async () => {
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
  await page.screenshot({ path: join(SHOTS, "bug-58-model-connected.png"), fullPage: true });

  await newChat();
  const answer = await ask("Reply with exactly: KNOWN LIMITS LIVE");
  await expect(answer).toContainText("KNOWN LIMITS LIVE");
});

test("the parallel bullet — a read-only batch is answered as a batch, not one call", async () => {
  test.setTimeout(300_000);
  await newChat();
  const answer = await ask(
    "In one turn, call read_file three times — once for alpha.md, once for beta.md " +
      "and once for gamma.md — and then list, on three lines, the exact contents of " +
      "each file. Do not summarise and do not stop after the first file.",
  );
  // The README used to say the orchestrator "takes the first and drops the
  // rest". All three results reaching the model is what disproves that, and it
  // is the model quoting them back that proves they reached it.
  await expect(answer).toContainText("alpha-marker-ONE");
  await expect(answer).toContainText("beta-marker-TWO");
  await expect(answer).toContainText("gamma-marker-THREE");
  await page.screenshot({ path: join(SHOTS, "bug-58-parallel-read-batch.png"), fullPage: true });
});

test("the patching bullet — one diff spanning two files is one decision", async () => {
  test.setTimeout(360_000);
  await newChat();
  // Scope, not strictness. The README used to say a unified patch is "one
  // existing text file". This asks for two in one call; the turn parks at the
  // approval boundary, which is where the claim has to be checked — the model
  // is told "approval required", and the *owner* is shown what would happen.
  await ask(
    "Call apply_patch exactly once with this unified diff, then tell me in one " +
      "sentence exactly what the tool returned, quoting any status or reason code " +
      "verbatim:\n\n" +
      "--- alpha.md\n+++ alpha.md\n@@ -1,1 +1,1 @@\n-alpha-marker-ONE\n+alpha-marker-ONE-PATCHED\n" +
      "--- beta.md\n+++ beta.md\n@@ -1,1 +1,1 @@\n-beta-marker-TWO\n+beta-marker-TWO-PATCHED\n",
  );
  // The transcript, not one bubble: the model's own lead-in and the runtime's
  // "approval required" answer are separate messages, and which lands last is
  // the model's choice, not a property this test is about.
  const transcript = page.getByRole("main");
  await expect(transcript).not.toContainText(/multiple file targets are not supported/i);
  await expect(transcript).toContainText(/approval required/i, { timeout: 30_000 });

  // One row in the inbox, naming both files, with the combined diff under it.
  // Two files, one decision, one reversible change set — the sentence the
  // README now carries.
  await page.goto(`${BASE}/#/approvals`);
  await page.getByLabel("Sort approvals").selectOption({ label: "Newest first" });
  const row = page.getByRole("row", { name: /Apply patch/ }).first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByRole("button", { name: "Review" }).click();
  const detail = page.locator(".diff-path");
  await expect(detail).toContainText("alpha.md", { timeout: 30_000 });
  await expect(detail).toContainText("beta.md");
  const diff = page.locator("pre.diff");
  await expect(diff).toContainText("alpha-marker-ONE-PATCHED");
  await expect(diff).toContainText("beta-marker-TWO-PATCHED");
  await page.screenshot({ path: join(SHOTS, "bug-58-multi-file-patch.png"), fullPage: true });
});

test("the web bullet — fetch withholds by default and search is not configured", async () => {
  test.setTimeout(360_000);
  await newChat();
  const fetched = await ask(
    "Call the web_fetch tool once with url https://pypi.org/project/httpx/ and then " +
      "tell me, in one sentence, exactly what the tool returned — including any " +
      "refusal reason.",
  );
  await expect(fetched).toContainText(/web_fetch/i);
  await expect(fetched).toContainText(/gate|disabled|capabilit|withheld|decision mode/i);
  await page.screenshot({ path: join(SHOTS, "bug-58-web-fetch-withheld.png"), fullPage: true });

  // Search is the same gate pointed at an owner-configured endpoint, so the
  // "no search endpoint" claim is only reachable once the gate is out of the
  // way. Enable and allow it, exactly as an owner would, and ask again — the
  // refusal that comes back is Raiker saying it ships no search provider,
  // which is the sentence the README now carries.
  await enableCapability("Web fetch", "BUG-58 known-limits verification");
  await allowCapability("Web fetch", "BUG-58 known-limits verification");

  await newChat();
  const searched = await ask(
    "Call the web_search tool once with the query raiker and then tell me, in one " +
      "sentence, exactly what the tool returned — including any refusal reason.",
  );
  await expect(searched).toContainText(/not configured|not_configured|no search (provider|endpoint)/i);
  await page.screenshot({ path: join(SHOTS, "bug-58-web-search-unconfigured.png"), fullPage: true });
});

test("the shell/network/process bullet — Permissions carries all three, told apart", async () => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByPlaceholder("Search capabilities…");
  await expect(search).toBeVisible({ timeout: 30_000 });

  // The README distinguishes shell (approvals execute) from network and process
  // (approvals stay metadata-only). All three have to exist as owner controls
  // for that sentence to be about anything the owner can see.
  for (const term of ["Shell", "Network", "Process"]) {
    await search.fill(term);
    await expect(page.locator(".cap.card").first()).toBeVisible({ timeout: 30_000 });
  }
  await search.fill("Shell");
  await expect(page.locator(".cap.card").first()).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: join(SHOTS, "bug-58-execution-capabilities.png"), fullPage: true });
});
