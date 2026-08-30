/**
 * B6, B7 and B8 against a live model — the evidence behind those three entries.
 *
 * Not a mocked shell: the runtime holds a real Anthropic credential, the turns
 * below reach the provider, and every screenshot is the shipped product running
 * its own endpoints.
 *
 *   B6 — the model writes a plan with `update_plan`, the workspace renders it as a
 *        live checklist, and the runtime carries it into later turns.
 *   B7 — the model delegates a read-only search with `spawn_subagent`, and the
 *        transcript records that it ran without the findings entering it.
 *   B8 — a connected MCP server states whether the agent can actually call it,
 *        and once the decision mode allows it, a real MCP tool call answers.
 *
 * Prerequisites:
 *   1. `python apps/api/main.py --workspace <ws> --port 8765 --no-browser`
 *      with RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com
 *   2. RAIKER_LIVE_ANTHROPIC_KEY in the environment (added through the UI below)
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
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
  await signInAsOwner(target, BASE);
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

  await page.goto(`${BASE}/#/new-chat`);
  await page.getByPlaceholder("How can I help you today?").fill("Reply with exactly: PLAN LIVE");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("main").getByText("PLAN LIVE", { exact: true })).toBeVisible({
    timeout: 180_000,
  });
});

test("B6 — the model's plan renders as a live checklist and is carried into later turns", async () => {
  test.setTimeout(300_000);
  await page.goto(`${BASE}/#/build`);
  const prompt = page.getByPlaceholder(/Describe what you want built|Describe the change/);
  await expect(prompt).toBeVisible({ timeout: 30_000 });

  await prompt.fill(
    "Call the update_plan tool once with exactly these three steps, in this order, " +
      "with the first marked completed, the second in_progress and the third pending: " +
      "1) Survey the workspace 2) Draft the change 3) Run the checks. " +
      "Then reply with one short sentence and stop.",
  );
  await page.keyboard.press("Enter");

  // The checklist itself, above the transcript.
  const plan = page.locator("section.plan");
  await expect(plan).toBeVisible({ timeout: 180_000 });
  await expect(plan.getByText("Survey the workspace")).toBeVisible();
  await expect(plan.getByText("Draft the change")).toBeVisible();
  await expect(plan.getByText("Run the checks")).toBeVisible();
  // Progress is stated, not implied by colour alone.
  await expect(plan.getByText("1 of 3 done")).toBeVisible();
  await expect(plan.getByRole("progressbar", { name: "Plan progress" })).toHaveAttribute(
    "aria-valuenow",
    "33",
  );
  await capture(page, join(SHOTS, "b6-build-live-plan-checklist.png"));

  // A second turn revises the same plan rather than starting a new one.
  await prompt.fill(
    "Call update_plan again with the same three steps, but mark the first two completed " +
      "and the third in_progress. Then reply with one short sentence and stop.",
  );
  await page.keyboard.press("Enter");
  await expect(plan.getByText("2 of 3 done")).toBeVisible({ timeout: 180_000 });
  await capture(page, join(SHOTS, "b6-build-live-plan-advanced.png"));

  // The spine is a recovery point, which means the *model* has to get it back —
  // not just the screen. A third turn that calls no tool can only answer this
  // from the plan the runtime re-injected into its context.
  await prompt.fill(
    "Without calling any tool, list the titles of the steps in your current plan " +
      "and the status of each, exactly as you last recorded them.",
  );
  await page.keyboard.press("Enter");
  const lastAnswer = page.locator("article.turn .answer").last();
  await expect(lastAnswer).toContainText("Run the checks", { timeout: 180_000 });
  await expect(lastAnswer).toContainText("Survey the workspace");

  // And the governed record says the plan was carried in, rather than the model
  // having simply remembered it from the transcript above.
  const governance = page.locator("details.governance").last();
  await governance.evaluate((node: HTMLDetailsElement) => (node.open = true));
  await expect(
    governance.getByText("The standing plan for this conversation was carried into the turn."),
  ).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "b6-build-live-plan-recovered.png"));
});

test("B7 — a delegated read-only search returns findings without filling the transcript", async () => {
  test.setTimeout(300_000);
  await page.goto(`${BASE}/#/build`);
  const prompt = page.getByPlaceholder(/Describe what you want built|Describe the change/);
  await expect(prompt).toBeVisible({ timeout: 30_000 });

  await prompt.fill(
    "Use the spawn_subagent tool exactly once, with objective 'inventory the workspace' " +
      "and two steps: list_directory with arguments {} and glob with arguments " +
      '{"pattern": "*"}. Then tell me in one sentence what the subagent found.',
  );
  await page.keyboard.press("Enter");

  await expect(page.getByRole("button", { name: "Copy response" }).last()).toBeVisible({
    timeout: 240_000,
  });

  // The governed record says a subagent ran and which read-only tools it used.
  const governance = page.locator("details.governance").last();
  await governance.evaluate((node: HTMLDetailsElement) => (node.open = true));
  await expect(governance.getByText(/Subagent .*finished .* read-only step/)).toBeVisible({
    timeout: 30_000,
  });
  await capture(page, join(SHOTS, "b7-build-live-subagent.png"));
});

/** Turn one capability on at runtime level, exactly as a person would. */
async function enableCapability(label: string) {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByPlaceholder("Search capabilities…");
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill(label);
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await card.getByRole("button", { name: label }).click();
  const turnOn = card.getByRole("button", { name: "Turn on" });
  if (await turnOn.isVisible().catch(() => false)) {
    await turnOn.click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Reason (required)").fill("B8 live verification");
    const token = dialog.getByLabel(/Confirmation token/);
    if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
    const ack = dialog.getByRole("checkbox");
    if (await ack.isVisible().catch(() => false)) await ack.check();
    await dialog.getByRole("button", { name: "Confirm change" }).click();
    await expect(dialog).toBeHidden({ timeout: 30_000 });
  }
}

test("B8 — MCP: a connected server says whether the agent can call it, then does", async () => {
  test.setTimeout(300_000);

  await enableCapability("MCP builder");
  await enableCapability("MCP connector");

  // Build and connect the reviewed echo server from the MCP page.
  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  await expect(page.getByRole("heading", { name: "MCP Servers" })).toBeVisible({ timeout: 30_000 });
  const card = page.locator("li.card").filter({ hasText: "echo" }).first();
  if (!(await card.isVisible().catch(() => false))) {
    await page.getByLabel("Server name").fill("echo");
    await page.getByRole("button", { name: "Create server" }).click();
  }
  await expect(card).toBeVisible({ timeout: 30_000 });
  await card.getByRole("button", { name: "Test" }).click();
  await expect(card.locator(".status")).toHaveText(/Connected/, { timeout: 60_000 });
  // The handshake really enumerated the server's own tools.
  await expect(card.locator(".tools .chip", { hasText: "workspace_ping" })).toBeVisible();

  // The state B8 was reported for: connected, tools listed, and still not
  // reachable — now said out loud instead of implied by a green dot.
  await expect(page.locator(".notice-warn")).toContainText("withheld from every turn", {
    timeout: 30_000,
  });
  await expect(card.getByText("Not callable yet — see above")).toBeVisible();
  await capture(page, join(SHOTS, "b8-mcp-live-withheld.png"));

  // Raise the decision mode, which is exactly what the banner told the owner to do.
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByPlaceholder("Search capabilities…");
  await search.fill("MCP connector");
  const mcpCard = page.locator(".cap.card").filter({ hasText: "MCP connector" }).first();
  await mcpCard.getByRole("button", { name: "Allow", exact: true }).click();
  // Loosening a decision mode is a step-up decision, recorded with a reason.
  const modeDialog = page.getByRole("dialog");
  await modeDialog.getByLabel("Reason (required)").fill("B8 live verification");
  await modeDialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(modeDialog).toBeHidden({ timeout: 30_000 });

  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  await expect(page.locator(".notice-ok")).toContainText(
    "available to Raiker in Chat and Build",
    { timeout: 30_000 },
  );
  const connected = page.locator("li.card").filter({ hasText: "echo" }).first();
  await expect(connected.getByText("Callable by Raiker")).toBeVisible();
  await capture(page, join(SHOTS, "b8-mcp-live-callable.png"));

  // And the claim holds: the model really calls the server's tool. Asserted on
  // the *answer* bubble, never on `main` — the prompt is echoed in the sent
  // bubble and in the recent-chat rail, and neither of those is an answer.
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 30_000 });
  await prompt.fill(
    'Call the tool named mcp__echo__echo with arguments {"text": "MCP REACHED"} ' +
      "and then quote back exactly what it returned.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copy response" }).last()).toBeVisible({
    timeout: 180_000,
  });
  await expect(page.locator(".message-bubble-raiker").last()).toContainText("MCP REACHED");
  await capture(page, join(SHOTS, "b8-mcp-live-tool-call.png"));
});
