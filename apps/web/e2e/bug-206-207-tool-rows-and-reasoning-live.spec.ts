/**
 * BUG-206 and BUG-207 against a live model — the evidence behind both entries.
 *
 * Not a mocked shell: the runtime holds a real Anthropic credential, every turn
 * below reaches the provider, and each screenshot is the shipped product
 * running its own endpoints.
 *
 *   BUG-206 — a tool-using turn shows what it did: one row per call, in call
 *             order, `[icon] [tool] [action]`. Before this the transcript for a
 *             turn that read three files was identical to one that used no
 *             tools, because the broker's events reached the durable log and
 *             never the stream.
 *   BUG-207 — the model's own reasoning, where the turn produced any, instead
 *             of a disclosure labelled "See what Raiker is thinking" holding
 *             three fixed sentences chosen by lifecycle event type.
 *
 * Prerequisites:
 *   1. `python -m apps.api.main --workspace <ws> --port 8765 --no-browser`
 *   2. RAIKER_LIVE_ANTHROPIC_KEY in the environment (added through the UI below)
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { setThinkingEffort, useHostedModel } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Tool-rows-and-reasoning-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
// Haiku 4.5 refuses `thinking.type.adaptive` and names the budgeted spelling in
// the refusal, so this model is also what proves the negotiation in BUG-207
// slice B: the turn thinks rather than failing with a 400.
const MODEL = "claude-haiku-4-5-20251001";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function signIn(target: Page) {
  await target.goto(`${BASE}/#/workbench`);
  await expect(target.getByText("Verifying runtime…")).toBeHidden({ timeout: 60_000 });
  const confirm = target.getByLabel("Confirm password");
  await target.getByLabel("Username").fill("owner");
  await target.getByLabel("Password", { exact: true }).fill(PASSWORD);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await target.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await target.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  await expect(target.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 60_000 });
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
  test.setTimeout(300_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");

  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await expect(card.locator("code").filter({ hasText: /Haiku 4\.5/i })).toBeVisible({
    timeout: 60_000,
  });

  await page.goto(`${BASE}/#/new-chat`);
  await page.getByPlaceholder("How can I help you today?").fill("Reply with exactly: ROWS LIVE");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("main").getByText("ROWS LIVE", { exact: true })).toBeVisible({
    timeout: 240_000,
  });
});

test("BUG-206 — a tool-using turn shows one row per call, naming what it acted on", async () => {
  test.setTimeout(420_000);
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill(
    "List the files in the workspace root with list_directory, then read README.md " +
      "with read_file. Then reply with one short sentence and stop.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();

  const rows = page.locator(".tool-activity .tool-row");
  await expect(rows.first()).toBeVisible({ timeout: 240_000 });
  // Two calls, two lines, in the order they were made — not one card per call
  // and not a single "used tools" summary.
  await expect(rows).toHaveCount(2, { timeout: 240_000 });

  // The row is `[icon] [tool] [action]`: the tool in the owner's language, and
  // the action naming the object. Neither is the tool identifier.
  await expect(page.locator(".tool-row .tool-label").first()).toHaveText(/List folder|Read file/);
  await page.screenshot({
    path: join(SHOTS, "bug-206-live-tool-rows-streaming.png"),
    fullPage: true,
  });

  await expect(page.locator(".message-bubble-raiker").last()).toBeVisible({ timeout: 240_000 });
  await page.waitForTimeout(3000);

  const settled = await page.locator("div.turn").last().innerText();
  console.log("SETTLED TURN:\n" + settled.replace(/\n{2,}/g, "\n"));

  // Every element the turn produced, by class. BUG-206 captured this list on
  // 2026-08-15 and it held no tool row, because none could exist.
  const parts = await page.locator("div.turn").last().evaluate((node) => {
    const seen: string[] = [];
    node.querySelectorAll("*").forEach((el) => {
      const cls = (el.getAttribute("class") ?? "").trim();
      if (cls) seen.push(cls.split(/\s+/)[0]);
    });
    return [...new Set(seen)];
  });
  console.log("ELEMENT CLASSES IN ONE TURN: " + parts.join(", "));
  expect(parts).toContain("tool-row");

  // Every row settled: nothing is left pulsing after the turn ends.
  const states = await rows.evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("data-state")),
  );
  console.log("ROW STATES: " + states.join(", "));
  expect(states.every((state) => state !== "running")).toBe(true);

  // No raw argument JSON and no tool identifier reached the transcript.
  const activity = await page.locator(".tool-activity").last().innerText();
  console.log("TOOL ACTIVITY:\n" + activity);
  expect(activity).not.toContain("{");
  expect(activity).not.toContain("read_file");
  expect(activity).not.toContain("list_directory");

  await page.screenshot({ path: join(SHOTS, "bug-206-live-tool-rows-settled.png"), fullPage: true });
});

test("BUG-206 slice E — a call that stops for a decision is that same row, waiting", async () => {
  test.setTimeout(420_000);
  await page.getByRole("button", { name: "New chat" }).click();
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill(
    "Use write_file to create a file called notes.md containing exactly the line " +
      "'hello from the tool row test'. Then stop.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // The write needs a decision, so the row says so instead of pulsing as though
  // something were running. The approval card below it is where the decision is
  // made; the row is what says *which call* is waiting.
  const waiting = page.locator('.tool-row[data-state="waiting"]');
  await expect(waiting).toBeVisible({ timeout: 240_000 });
  await expect(waiting.locator(".tool-label")).toHaveText("Write file");
  await expect(waiting.locator(".tool-action")).toHaveText("notes.md");
  await expect(page.locator(".approval-card")).toBeVisible({ timeout: 60_000 });
  // Stated once. The sr-only copy is withheld for the states that say
  // themselves in visible text, so a screen reader hears it once too.
  const spoken = (await waiting.innerText()).replace(/\n/g, " · ");
  console.log("WAITING ROW: " + spoken);
  expect(spoken.match(/waiting for your decision/g)).toHaveLength(1);
  await page.screenshot({ path: join(SHOTS, "bug-206-live-tool-row-waiting.png"), fullPage: true });

  // The refusal card BUG-52 put at the bottom of the turn is gone: a refused or
  // parked call is a row now, in the place it happened.
  await expect(page.locator(".refusal-card")).toHaveCount(0);

  // And the row settles once the decision is made — the approved call is not
  // re-brokered on resume, so the runtime settles it from the outcome the
  // approval recorded and the client merges rather than replaces.
  //
  // **Not asserted here, deliberately.** Watching it settle needs the tab that
  // ran the turn to stay mounted while the decision is made somewhere else, and
  // five attempts at driving that second surface from this spec produced a
  // flaky step rather than evidence. Rebuilding the conversation instead is not
  // an option: a reopened turn carries no rows at all (BUG-215). The behaviour
  // is covered where it can be asserted deterministically —
  // `test_turn_model_binding.py` for the resolved call the gateway hands the
  // runtime, `resumed_call_row_status` for all three outcomes, and
  // `chatPresentation.test.ts` for the client merging the settled event into
  // the row it already opened.
});

test("BUG-207 — the turn shows the model's own reasoning, not three canned sentences", async () => {
  test.setTimeout(420_000);
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });

  // Reasoning is off unless the owner asks for it, so the control has to exist
  // for Anthropic at all — which it did not, because the composer only offered
  // an *effort* and Anthropic declares a *mode*.
  const chatComposer = page.locator("form").filter({ has: prompt });
  expect(
    await setThinkingEffort(chatComposer, page, "adaptive"),
    "Anthropic must publish a reasoning setting for this composer to offer one",
  ).toBe(true);

  await prompt.fill(
    "What is 17 times 23? Work it out carefully, then give the number and stop.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();

  const reasoning = page.locator("section.reasoning").last();
  await expect(reasoning).toBeVisible({ timeout: 240_000 });
  const body = reasoning.locator(".reasoning-body");
  await expect(body).toBeVisible({ timeout: 240_000 });

  // Read it open, while it is still filling in. This is the model's own
  // extended thinking — captured here rather than after the turn settles,
  // because it collapses the moment the answer starts. It is *reasoning about
  // this question*, so it names the numbers the owner typed; a fixed string
  // could not. Polled rather than sampled once: the block appears on the first
  // delta, and reading at that instant proves only that a delta arrived.
  await expect
    .poll(async () => await body.innerText(), { timeout: 240_000 })
    .toMatch(/17/);
  const thought = await body.innerText();
  console.log("REASONING WHILE STREAMING:\n" + thought);
  await page.screenshot({ path: join(SHOTS, "bug-207-live-reasoning-streaming.png"), fullPage: true });

  // The three fixed sentences the disclosure used to hold, and the label that
  // presented them as the model's thinking. None may return.
  expect(thought).not.toContain("Understanding what you need.");
  expect(thought).not.toContain("Reviewing the available context.");
  expect(thought).not.toContain("Putting together a response.");
  await expect(page.getByText("See what Raiker is thinking")).toHaveCount(0);
  expect(thought.length).toBeGreaterThan(40);

  await expect(page.locator(".message-bubble-raiker").last()).toBeVisible({ timeout: 240_000 });
  await page.waitForTimeout(3000);

  // Collapsed once the answer starts, so the answer is what the eye lands on —
  // and still there to open, because it is the record of how it was reached.
  await expect(reasoning.locator(".reasoning-body")).toHaveCount(0);
  await expect(reasoning.getByRole("button", { name: "Thinking" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  await page.screenshot({ path: join(SHOTS, "bug-207-live-reasoning-settled.png"), fullPage: true });
});

test("BUG-206 and BUG-207 — Build shows the same rows and the same reasoning", async () => {
  test.setTimeout(420_000);
  await page.goto(`${BASE}/#/build`);
  const prompt = page.locator("textarea#build-prompt");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  // Chat stays mounted behind Build, so its composer is still in the DOM and
  // every unscoped selector below would match both. `article.turn` is Build's
  // own transcript element; Chat's is a `div`.
  const composer = page.locator("form").filter({ has: prompt });
  await setThinkingEffort(composer, page, "adaptive");
  await prompt.fill(
    "Read README.md with read_file, then say in one sentence what this project is. Then stop.",
  );
  await page.keyboard.press("Enter");

  // Build is where a turn makes the most tool calls, and where a silent one was
  // hardest to account for. Same component, same data path, same row.
  const turn = page.locator("article.turn").last();
  const row = turn.locator(".tool-activity .tool-row").last();
  await expect(row).toBeVisible({ timeout: 240_000 });
  await expect(row.locator(".tool-label")).toHaveText("Read file");
  await expect(row.locator(".tool-action")).toHaveText("README.md");
  await expect(turn.locator("section.reasoning")).toBeVisible({ timeout: 240_000 });
  await expect(turn.locator(".answer").last()).toBeVisible({ timeout: 240_000 });
  await page.waitForTimeout(2500);
  console.log("BUILD TURN:\n" + (await turn.innerText()));
  await page.screenshot({ path: join(SHOTS, "bug-206-207-live-build-turn.png"), fullPage: true });
});

test("BUG-207 — a turn with reasoning off streams its answer with no block above it", async () => {
  test.setTimeout(300_000);
  // Coming back from Build, so the hash really changes and Chat opens fresh.
  // (Navigating to the hash the view is *already* showing changes nothing,
  // which is what the "New chat" control is for.)
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.locator("textarea#prompt-input");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  // Thinking is a composer preference and survives starting a new chat, so it
  // is put back deliberately — an earlier test turned it on. Scoped to Chat's
  // own composer: Build stays mounted behind it and has one of its own.
  const composer = page.locator("form").filter({ has: prompt });
  await setThinkingEffort(composer, page, "");

  await prompt.fill("Reply with exactly: NO REASONING");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  await expect(page.getByRole("main").getByText("NO REASONING", { exact: true })).toBeVisible({
    timeout: 240_000,
  });
  // Absent, not empty: nothing stands in for reasoning that was not produced,
  // and no tool row either, because the turn called nothing.
  const lastChatTurn = page.locator("div.turn").last();
  await expect(lastChatTurn.locator("section.reasoning")).toHaveCount(0);
  await expect(lastChatTurn.locator(".tool-activity")).toHaveCount(0);
  await page.screenshot({ path: join(SHOTS, "bug-207-live-no-reasoning.png"), fullPage: true });
});
