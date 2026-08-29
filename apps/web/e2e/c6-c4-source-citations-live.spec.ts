/**
 * C6 and C4 against a running `raiker-web` — an answer that says where it came
 * from, and a source that opens at the passage it used.
 *
 * The gap this closes is a correctness one, not a polish one: Chat could read
 * the owner's real material and then answer as if it had simply known, so an
 * answer drawn from a document was indistinguishable from an answer invented
 * whole. This spec drives the whole path through the product with a real
 * provider — the material entering the turn, the marker the model writes, the
 * ledger under the answer, and the passage opening in the inspector — plus the
 * property that makes any of it worth trusting: a marker the runtime never
 * recorded resolves to nothing.
 *
 * Prerequisites:
 *   1. `raiker-web --workspace <fresh ws> --port 8765 --no-browser` with
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (added through the UI below)
 *   3. `RAIKER_LIVE_WORKSPACE` pointing at that same workspace directory, so the
 *      spec can put a file where the agent's read tools will find it
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Source-citations-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const MODEL = "claude-haiku-4-5-20251001";

// The one sentence everything below turns on. It is deliberately a fact no
// model could produce from training: if it appears in the answer, it came from
// the file, and the citation is checkable rather than decorative.
const FACT = "The Meridian licence renews on 14 March 2029.";

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

async function newChat() {
  await page.goto(`${BASE}/#/new-chat`);
  const reset = page.getByRole("button", { name: "New chat", exact: true });
  if (await reset.isEnabled().catch(() => false)) await reset.click();
  await expect(page.getByPlaceholder("How can I help you today?")).toBeVisible({ timeout: 30_000 });
}

async function ask(prompt: string) {
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
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
});

test("an answer drawn from a workspace file cites it, and the ledger is under the answer", async () => {
  test.setTimeout(420_000);
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE").not.toBe("");
  mkdirSync(join(WORKSPACE, "contracts"), { recursive: true });
  writeFileSync(
    join(WORKSPACE, "contracts", "meridian.md"),
    `# Meridian\n\nOwner: Facilities.\n\n${FACT}\n\nRenewal is handled by Legal.\n`,
    "utf-8",
  );

  await newChat();
  await ask(
    "Read the file contracts/meridian.md with the read_file tool, then tell me in one " +
      "sentence when the Meridian licence renews. Cite the source.",
  );

  // The answer is really drawn from the file.
  await expect(page.getByRole("main")).toContainText(/14 March 2029/, { timeout: 60_000 });

  // C6 — the ledger: what this turn actually read, under the answer that used
  // it. It exists because the runtime recorded a call, not because the model
  // mentioned anything.
  const strip = page.getByRole("region", { name: "Sources this answer used" }).last();
  await expect(strip).toBeVisible({ timeout: 60_000 });
  await expect(strip.getByRole("button", { name: /meridian\.md/ })).toBeVisible();
  await capture(page, join(SHOTS, "c6-source-ledger-under-answer.png"));
});

test("the inline marker the model wrote is a chip, and it opens the source at the passage", async () => {
  test.setTimeout(180_000);
  // C6 — `[s1]` in the answer is rendered as a control, not left as characters.
  const chip = page.locator(".message-bubble-raiker .md-cite").first();
  await expect(chip).toBeVisible({ timeout: 30_000 });
  await chip.click();

  // C4 — the pane opens on the document *and* marks the passage the turn used,
  // rather than making the owner find it again by eye.
  const inspector = page.getByRole("complementary", { name: "File preview" });
  await expect(inspector).toBeVisible({ timeout: 60_000 });
  await expect(inspector.locator("mark")).toContainText(/14 March 2029/, { timeout: 60_000 });
  await capture(page, join(SHOTS, "c4-source-opened-at-passage.png"));
  await inspector.getByRole("button", { name: "Close file preview" }).click();
});

test("a chip in the ledger opens the same source", async () => {
  test.setTimeout(180_000);
  const strip = page.getByRole("region", { name: "Sources this answer used" }).last();
  await strip.getByRole("button", { name: /meridian\.md/ }).click();
  const inspector = page.getByRole("complementary", { name: "File preview" });
  await expect(inspector).toBeVisible({ timeout: 60_000 });
  await expect(inspector.locator("mark")).toContainText(/14 March 2029/, { timeout: 60_000 });
  await inspector.getByRole("button", { name: "Close file preview" }).click();
});

test("an attached document is citable, and opens at the passage it contributed", async () => {
  test.setTimeout(420_000);
  const attachment = {
    name: "quarter-note.md",
    mimeType: "text/markdown",
    buffer: Buffer.from(
      "# Quarter note\n\nThe Northwind pilot shipped to 41 sites in week nine.\n",
    ),
  };
  await newChat();
  await page.getByRole("button", { name: "Add attachment" }).click();
  await page.getByLabel("Upload document").setInputFiles(attachment);
  await expect(
    page.locator(".attachment-row > .attachment-card").filter({ hasText: "quarter-note.md" }),
  ).toBeVisible({ timeout: 30_000 });
  await ask("How many sites did the Northwind pilot ship to? Answer in one sentence and cite it.");

  await expect(page.getByRole("main")).toContainText(/41 sites/, { timeout: 60_000 });
  const strip = page.getByRole("region", { name: "Sources this answer used" }).last();
  await expect(strip.getByRole("button", { name: /quarter-note\.md/ })).toBeVisible({
    timeout: 60_000,
  });
  await strip.getByRole("button", { name: /quarter-note\.md/ }).click();

  const inspector = page.getByRole("complementary", { name: "File preview" });
  await expect(inspector).toBeVisible({ timeout: 60_000 });
  await expect(inspector.locator("mark")).toContainText(/41 sites/, { timeout: 60_000 });
  await capture(page, join(SHOTS, "c4-attachment-opened-at-passage.png"));
  await inspector.getByRole("button", { name: "Close file preview" }).click();
});

test("Build gets the same account, opened where the citation is", async () => {
  test.setTimeout(420_000);
  // Build receives the same `cite_as` markers as Chat, so it owes the same
  // answer. It has no inspector pane (B13/B14), so the passage opens inline
  // under the citation rather than in a pane that does not exist.
  await page.goto(`${BASE}/#/build`);
  const composer = page.getByLabel("Describe the change");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(
    "Read contracts/meridian.md with read_file, then state in one sentence when the " +
      "Meridian licence renews. Cite the source.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });

  const strip = page.getByRole("region", { name: "Sources this answer used" }).last();
  await expect(strip.getByRole("button", { name: /meridian\.md/ })).toBeVisible({
    timeout: 60_000,
  });
  await strip.getByRole("button", { name: /meridian\.md/ }).click();
  const panel = page.getByRole("region", { name: "Cited source" });
  await expect(panel).toBeVisible({ timeout: 60_000 });
  await expect(panel.locator("mark")).toContainText(/14 March 2029/, { timeout: 60_000 });
  await capture(page, join(SHOTS, "c6-build-source-inline.png"));
});

test("a marker the runtime never recorded is not a citation", async () => {
  test.setTimeout(300_000);
  // The property the whole feature rests on: a citation is something the
  // runtime recorded, never something a model can simply assert. `[s7]` here is
  // the model's own text about a source that does not exist, so it must stay
  // the characters it is.
  await newChat();
  await ask(
    "Without calling any tool, reply with exactly this line and nothing else: " +
      "Nothing was read here [s7].",
  );
  const answer = page.locator(".message-bubble-raiker").last();
  await expect(answer).toContainText("[s7]", { timeout: 60_000 });
  await expect(answer.locator(".md-cite")).toHaveCount(0);
  await capture(page, join(SHOTS, "c6-uncited-marker-stays-text.png"));
});
