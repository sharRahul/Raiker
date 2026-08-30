/**
 * BUG-57 against a running `raiker-web` — a capability the owner enabled must
 * not be argued away by the turn's own context.
 *
 * The defect was not in the gate. With `web_fetch` enabled and its decision mode
 * at Allow, a live turn declined to call the tool and explained itself:
 *
 * > I cannot call web_fetch because the web_fetch capability gate is disabled in
 * > the current runtime environment. According to the capability status in the
 * > workspace context, `network_execution_enabled` is false…
 *
 * Two separate untruths did that. `CAPABILITY_FLAGS` reported eighteen
 * `*_enabled: false` lines on every turn whatever the owner had switched on, and
 * `_workspace_summary` asserted `runtime_mode: local_read_only_planning` and
 * "all unsafe runtime flags remain false" — the first naming one of the five
 * modes FIXED-63 replaced with a single runtime. The model then reasoned across
 * names, from `network_execution` to a neighbouring capability that shares no
 * gate with it.
 *
 * A unit test can assert the bundle now reads from the store. Only a live turn
 * can show the thing the owner actually cared about: that the model no longer
 * talks itself out of a tool it has. So each test below is a real turn against a
 * real provider.
 *
 * Prerequisites:
 *   1. `raiker-web --workspace <fresh ws> --port 8765 --no-browser` with
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com` and
 *      `RAIKER_WEB_EGRESS_ALLOWLIST=pypi.org`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (added through the UI below)
 *
 * The workspace must be **fresh**: the first test below is about what the
 * context says before the owner has touched a gate, and a later one turns
 * `web_fetch` on.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Capability-context-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";

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

/** Send one prompt and wait for *this* turn to finish. */
async function ask(prompt: string) {
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  const before = await page.locator(".message-bubble-raiker").count();
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
  await expect
    .poll(async () => page.locator(".message-bubble-raiker").count(), { timeout: 60_000 })
    .toBeGreaterThan(before);
  return page.locator(".message-bubble-raiker").last();
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

async function newChat() {
  await page.goto(`${BASE}/#/new-chat`);
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
  await capture(page, join(SHOTS, "bug-57-model-connected.png"));

  await newChat();
  const answer = await ask("Reply with exactly: CAPABILITY CONTEXT LIVE");
  await expect(answer).toContainText("CAPABILITY CONTEXT LIVE");
});

test("before the owner touches a gate, the context says disabled and names the gate", async () => {
  test.setTimeout(300_000);
  await newChat();
  // The bundle is still allowed to report a capability as off — that is the
  // fail-closed truth on a fresh workspace. What it may no longer do is report
  // it in a vocabulary the model has to translate. The model is asked to read
  // its own context back, so the *shape* of what it was told is on the page.
  const answer = await ask(
    "Look at the capability-gate lines in your workspace context. In at most three " +
      "lines, state the exact gate name that governs the web_fetch tool and whether " +
      "that line says enabled or disabled. Quote the line verbatim. Do not guess.",
  );
  await expect(answer).toContainText(/web_fetch/);
  await expect(answer).toContainText(/disabled/i);
  // The eighteen fixed `*_enabled: false` names are gone, so the model cannot
  // quote one back.
  await expect(answer).not.toContainText("network_execution_enabled");
  await expect(answer).not.toContainText("runtime_execution_enabled");
  await capture(page, join(SHOTS, "bug-57-gate-disabled-named.png"));
});

test("the workspace summary no longer claims a read-only planning runtime", async () => {
  test.setTimeout(300_000);
  await newChat();
  // `runtime_mode: local_read_only_planning` was a fixed string naming a mode
  // that FIXED-63 deleted. A model asked what runtime it is on used to read it
  // and conclude it could do nothing at all.
  const answer = await ask(
    "In the workspace summary in your context, exactly one line describes the agent " +
      "runtime's state. Reply with that whole line copied character for character, " +
      "including its key and its colon. Add no other text.",
  );
  await expect(answer).toContainText(/agent_runtime/);
  await expect(answer).toContainText(/active/i);
  await expect(answer).not.toContainText("local_read_only_planning");
  await expect(answer).not.toContainText("all unsafe runtime flags remain false");
  await capture(page, join(SHOTS, "bug-57-runtime-status-live.png"));
});

test("BUG-57 itself — an enabled capability is used, not argued away", async () => {
  test.setTimeout(420_000);
  await enableCapability("Web fetch", "BUG-57 live verification");
  await allowCapability("Web fetch", "BUG-57 live verification");
  await capture(page, join(SHOTS, "bug-57-web-fetch-enabled.png"));

  await newChat();
  // The reproduction, exactly: the gate is on, the mode is Allow, the host is
  // allowlisted. Before the fix the model refused here and cited
  // `network_execution_enabled` — a different capability — from its context.
  const answer = await ask(
    "Call web_fetch for https://pypi.org/ and reply with the one sentence on that " +
      "page that begins with the words \"Find, install\", copied exactly. If you " +
      "decide not to call the tool, say exactly why instead and quote the context " +
      "line you based that decision on.",
  );
  await expect(answer).toContainText(/Find, install and publish Python packages/i, {
    timeout: 30_000,
  });
  await expect(answer).not.toContainText("network_execution_enabled");
  await capture(page, join(SHOTS, "bug-57-web-fetch-used.png"));
});

test("the enabled gate reads back as enabled, and its neighbours still do not", async () => {
  test.setTimeout(300_000);
  await newChat();
  // The other half of the fix: turning one gate on must not read as turning a
  // neighbouring one on. `shell_execution` was never touched by this run.
  const answer = await ask(
    "From the capability-gate lines in your workspace context only, answer in two " +
      "lines: line 1 is the web_fetch line verbatim, line 2 is the shell_execution " +
      "line verbatim. Do not add anything else.",
  );
  await expect(answer).toContainText(/web_fetch: enabled/);
  await expect(answer).toContainText(/shell_execution: disabled/);
  await capture(page, join(SHOTS, "bug-57-gates-read-back.png"));
});
