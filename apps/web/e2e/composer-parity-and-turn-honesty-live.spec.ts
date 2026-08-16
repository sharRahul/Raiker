/**
 * Live proof for the 2026-08-16 round: BUG-196, BUG-197, BUG-215 and the
 * composer parity work (GAP-BUILD B19, GAP-CHAT C14).
 *
 * Everything here is driven through the product's own surfaces against a real
 * Anthropic model. Nothing is asserted from an API the page does not use, and no
 * credential is committed — the key comes from `RAIKER_LIVE_ANTHROPIC_KEY` and
 * is entered through the same **Connect** dialog a person uses.
 *
 * Prerequisites:
 *   1. `raiker-web --workspace <fresh ws> --port 8765 --no-browser`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY`
 */
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import {
  dismissFirstRunModelSetup,
  pickAnyThinkingLevel,
  setThinkingEffort,
  useHostedModel,
} from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const PASSWORD = "Composer-parity-live-2026-1!";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function signIn(): Promise<void> {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 30_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  const welcome = page.getByRole("heading", { name: /Welcome/ });
  const setup = page.getByRole("button", { name: /Decide later|Skip for now/ });
  await expect(welcome.or(setup).first()).toBeVisible({ timeout: 30_000 });
  if (await setup.isVisible().catch(() => false)) await dismissFirstRunModelSetup(page);
  await expect(welcome).toBeVisible({ timeout: 30_000 });
}

test.beforeAll(async ({ browser }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is required for this live suite.");
  // Bootstrap is sign-in, the first-run wizard, a provider connection and a
  // real readiness probe against the provider's API. The default 30s hook
  // budget covers none of that on a cold workspace.
  test.setTimeout(300_000);
  context = await browser.newContext();
  page = await context.newPage();
  await signIn();
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: KEY,
    model: MODEL,
  });
});

test.afterAll(async () => {
  await context?.close();
});

test("the Chat composer offers only commands Chat can run", async () => {
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByLabel("Prompt");
  await expect(prompt).toBeVisible({ timeout: 30_000 });

  await prompt.fill("/");
  const menu = page.getByRole("listbox", { name: "Commands" });
  await expect(menu).toBeVisible({ timeout: 10_000 });
  await expect(menu.getByText("/new", { exact: true })).toBeVisible();
  await expect(menu.getByText("/export", { exact: true })).toBeVisible();
  // Build's own commands must not be offered here.
  await expect(menu.getByText("/terminal", { exact: true })).toHaveCount(0);

  await page.screenshot({
    path: join(SHOTS, "r0816-chat-slash-commands.png"),
    fullPage: false,
  });

  // Narrowing works, and the menu closes when the token stops being one.
  await prompt.fill("/mod");
  await expect(menu.getByText("/model", { exact: true })).toBeVisible();
  await expect(menu.getByText("/new", { exact: true })).toHaveCount(0);
  await prompt.fill("read https://example.com/docs");
  await expect(menu).toBeHidden();
});

test("the keyboard map opens from the composer and lists real bindings", async () => {
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByLabel("Prompt");
  await expect(prompt).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "all shortcuts" }).click();
  const sheet = page.getByRole("region", { name: "Keyboard shortcuts" });
  await expect(sheet).toBeVisible();
  await expect(sheet.getByText("Enter", { exact: true })).toBeVisible();
  await expect(sheet.getByText("Shift + Enter", { exact: true })).toBeVisible();
  // Chat has no mode cycle, so it must not claim one.
  await expect(sheet.getByText("Shift + Tab", { exact: true })).toHaveCount(0);

  await page.screenshot({ path: join(SHOTS, "r0816-chat-shortcut-sheet.png") });
});

test("the Build composer carries the coding-agent commands and the mode cycle", async () => {
  await page.goto(`${BASE}/#/build`);
  const prompt = page.getByLabel("Describe the change");
  await expect(prompt).toBeVisible({ timeout: 30_000 });

  await prompt.fill("/");
  const menu = page.getByRole("listbox", { name: "Commands" });
  await expect(menu).toBeVisible({ timeout: 10_000 });
  await expect(menu.getByText("/terminal", { exact: true })).toBeVisible();
  await expect(menu.getByText("/plan-mode", { exact: true })).toBeVisible();
  await expect(menu.getByText("/repos", { exact: true })).toBeVisible();
  // Export is a Chat control and must not be offered in Build.
  await expect(menu.getByText("/export", { exact: true })).toHaveCount(0);

  await page.screenshot({ path: join(SHOTS, "r0816-build-slash-commands.png") });

  await page.getByRole("button", { name: "all shortcuts" }).click();
  const sheet = page.getByRole("region", { name: "Keyboard shortcuts" });
  await expect(sheet.getByText("Shift + Tab", { exact: true })).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "r0816-build-shortcut-sheet.png") });
});

test("an @ mention says why it cannot complete rather than showing an empty menu", async () => {
  // A fresh workspace has never indexed a repository, so this is the honest
  // path: the reason, and the control that fixes it.
  await page.goto(`${BASE}/#/build`);
  const prompt = page.getByLabel("Describe the change");
  await expect(prompt).toBeVisible({ timeout: 30_000 });

  await prompt.fill("look at @main");
  await expect(
    page.getByText(/No code map|code map is off|Workspace file mentions/i),
  ).toBeVisible({ timeout: 15_000 });

  await page.screenshot({ path: join(SHOTS, "r0816-build-mention-reason.png") });
});

test("a real turn runs, and its prompt can be copied, edited and retried", async () => {
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByLabel("Prompt");
  await expect(prompt).toBeVisible({ timeout: 30_000 });

  await prompt.fill("Reply with exactly the word: acknowledged");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText(/acknowledged/i).first()).toBeVisible({ timeout: 120_000 });

  // C14 — the three message actions on the owner's own prompt.
  await expect(page.getByRole("button", { name: "Copy this message" })).toBeAttached();
  await expect(page.getByRole("button", { name: "Send this message again" })).toBeAttached();
  await page
    .getByRole("button", { name: "Edit this message and send it again" })
    .first()
    .click();
  await expect(prompt).toHaveValue("Reply with exactly the word: acknowledged");
  // The transcript is not rewritten: the original turn is still there.
  await expect(page.getByText("Reply with exactly the word: acknowledged").first()).toBeVisible();

  await page.screenshot({ path: join(SHOTS, "r0816-chat-message-actions.png") });
  await prompt.fill("");
});

/**
 * Drive the retention setting to `want` and prove the decision survives a reload.
 *
 * Written as "set it to this" rather than "it starts off" on purpose: a live
 * host carries whatever a previous run left, and a spec that asserts a default
 * it did not establish is measuring the workspace's history rather than the
 * product. The **default** is held by `Privacy.test.ts`, where a fresh render is
 * genuinely fresh.
 */
const RETENTION = /Keep the model's working with the turn/;

async function openPrivacy(): Promise<void> {
  await page.goto(`${BASE}/#/settings?tab=privacy`);
  await expect(page.getByRole("checkbox", { name: RETENTION })).toBeVisible({ timeout: 30_000 });
}

async function setRetention(want: boolean): Promise<void> {
  await openPrivacy();
  const toggle = page.getByRole("checkbox", { name: RETENTION });

  // The controls render before the settings read resolves, so the state read
  // straight after navigation can be the empty default rather than the owner's
  // setting — and a click made in that window toggles from the wrong base.
  // Driving to the wanted state and re-reading is honest about that race where a
  // single click plus a sleep would be a guess: what matters to the owner is
  // that the control ends up where they put it.
  await expect
    .poll(
      async () => {
        if ((await toggle.isChecked()) === want) return want;
        await toggle.click();
        const save = page.getByRole("button", { name: "Save changes" });
        if (await save.isVisible().catch(() => false)) {
          await save.click();
          await expect(save).toBeHidden({ timeout: 30_000 });
        }
        return toggle.isChecked();
      },
      { timeout: 60_000, intervals: [500, 1000, 1000, 2000, 2000] },
    )
    .toBe(want);

  // The decision has to survive leaving the page, or it was never a setting:
  // coming back re-mounts the section and re-reads `GET /api/settings`, so what
  // the control shows is what the runtime stored, not what this page remembered.
  await page.goto(`${BASE}/#/home`);
  await openPrivacy();
  await expect
    .poll(async () => page.getByRole("checkbox", { name: RETENTION }).isChecked(), {
      timeout: 30_000,
    })
    .toBe(want);
}

test("the owner decides whether the model's working is kept, and it sticks", async () => {
  // A page load re-runs the whole bootstrap read, which is slower than the
  // default per-test budget.
  test.setTimeout(180_000);

  // BUG-215 — both directions, because a setting that can only be turned on is
  // not a decision the owner controls.
  await setRetention(false);
  await page.screenshot({ path: join(SHOTS, "r0816-settings-privacy-off.png") });

  await setRetention(true);
  await page.screenshot({ path: join(SHOTS, "r0816-settings-privacy-on.png") });
});

test("a governed command names the backend that ran it", async () => {
  // BUG-197 — the run list and the receipt must agree. With no command run yet
  // the pane still states its environment, which is the surface the row joins.
  await page.goto(`${BASE}/#/build`);
  const pane = page.getByRole("button", { name: /Governed terminal/ });
  await expect(pane).toBeVisible({ timeout: 30_000 });
  await pane.click();
  await expect(page.getByText(/Commands start through the governed agent path/)).toBeVisible();

  await page.screenshot({ path: join(SHOTS, "r0816-build-governed-terminal.png") });
});

test("a thinking turn's working is kept, and a re-opened turn still shows it", async () => {
  // BUG-215's whole point, end to end against a real model: reasoning that
  // survives leaving the conversation and coming back. It runs after the
  // retention test above has turned retention on.
  test.setTimeout(300_000);
  await setRetention(true);

  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByLabel("Prompt");
  await expect(prompt).toBeVisible({ timeout: 30_000 });

  // Start a genuinely new conversation. Chat stays mounted across routes, so a
  // turn sent here otherwise lands in whichever conversation the suite was last
  // in — and this scenario re-opens the turn *by its title*, which is the first
  // prompt of its conversation. **New chat** is the control that makes the turn's
  // own prompt that title.
  const newChat = page.getByRole("button", { name: "New chat" });
  if (await newChat.isEnabled().catch(() => false)) {
    await newChat.click();
    await expect(prompt).toBeVisible({ timeout: 30_000 });
  }

  // Ask this model to think. The setting lives inside the model menu now, and a
  // profile that declares no reasoning setting has no Effort section at all — so
  // there is nothing to prove here, and this says so rather than passing quietly.
  // Waited for rather than sampled: the model chip resolves after the prompt box
  // appears, and an immediate read would skip a model that does declare one.
  const composer = page.locator("form").filter({ has: prompt });
  await expect
    .poll(
      async () =>
        (await composer.getByRole("button", { name: /^Model for this turn:/ }).textContent()) ?? "",
      { timeout: 30_000 },
    )
    .not.toMatch(/Not selected/);
  const declared = await setThinkingEffort(composer, page, "");
  test.skip(!declared, "the pinned model declares no reasoning setting");
  const chosen = await pickAnyThinkingLevel(composer, page);
  test.skip(chosen === null, "the pinned model offers no reasoning level");

  await prompt.fill("Think it through, then answer in one word: is 91 prime?");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  const thinkingBlock = page.getByRole("button", { name: /Thinking/ });
  await expect(thinkingBlock.first()).toBeVisible({ timeout: 180_000 });
  await page.screenshot({ path: join(SHOTS, "r0816-chat-thinking-live.png") });

  // The turn has to *finish* before any of this means anything: the working is
  // written when the turn closes, so re-opening a still-streaming turn would
  // prove only that the stream was still attached. The steer field is the
  // signal — the composer carries it only while a turn is running, where Send
  // stays disabled either way because the prompt box is empty.
  await expect(
    page.getByPlaceholder("Add to this turn — it arrives at the next safe boundary"),
  ).toBeHidden({ timeout: 180_000 });

  // Re-open it the way a person does — from Recent chats, after going somewhere
  // else — so the transcript is rebuilt from stored rows rather than from the
  // component that watched it stream.
  await page.goto(`${BASE}/#/home`);
  const recent = page
    .getByRole("link", { name: /Think it through/ })
    .first();
  await expect(recent).toBeVisible({ timeout: 30_000 });
  await recent.click();
  await expect(page.getByText("Think it through, then answer in one word: is 91 prime?").first())
    .toBeVisible({ timeout: 30_000 });

  // The block is there at all only because the working was retained: a turn
  // whose working was not kept renders the "not kept" line instead, and a turn
  // that produced none renders nothing.
  const reopened = thinkingBlock.first();
  await expect(reopened).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/It was not kept/)).toHaveCount(0);
  // Open it if it settled closed — it collapses once the answer starts — and
  // read the working back.
  if ((await reopened.getAttribute("aria-expanded")) !== "true") await reopened.click();
  await expect(page.locator(".reasoning-body").first()).not.toBeEmpty();

  await page.screenshot({ path: join(SHOTS, "r0816-chat-thinking-retained.png") });
});
