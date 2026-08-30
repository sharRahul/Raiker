/**
 * BUG-62 against a running `raiker-web` — approving a proposed task creates it.
 *
 * The defect was a worse shape than a missing feature: the model called
 * `create_task`, the runtime raised a real high-risk **Create task** approval
 * naming the task, and approving it answered *"Recorded: approved. The action
 * was NOT executed (metadata-only)"* — no task anywhere, and a receipt pointing
 * at a Tasks page that would not have it. This spec drives the whole path
 * through the product: the owner turning the capability on, the sentence they
 * read before deciding, the decision itself, the task that exists afterwards,
 * and the off switch that returns it honestly to record-only.
 *
 * Prerequisites:
 *   1. `raiker-web --workspace <fresh ws> --port 8765 --no-browser` with
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (added through the UI below)
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Task-approval-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";
const TASK_TITLE = "Draft the weekly summary";

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
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  if ((await card.getByRole("button", { name: label }).getAttribute("aria-expanded")) !== "true") {
    await card.getByRole("button", { name: label }).click();
  }
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
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
}

async function openNewestCreateTaskApproval() {
  await page.goto(`${BASE}/#/approvals`);
  await page.getByLabel("Sort approvals").selectOption({ label: "Newest first" });
  const row = page.getByRole("row", { name: /Create task/i }).first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByRole("button", { name: "Review" }).click();
  await expect(page.getByRole("heading", { name: /Review Create task/i })).toBeVisible({
    timeout: 30_000,
  });
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
  await capture(page, join(SHOTS, "bug-62-model-connected.png"));
});

test("Task creation is an owner control on the Permissions page", async () => {
  test.setTimeout(180_000);
  // BUG-62's capability is the owner's, not the runtime's: it ships as a named
  // switch beside the file and memory ones, and nothing below works until the
  // owner turns it — and the relay that carries out any approval — on.
  await setCapability("Approval execution relay", "Turn on", "approvals should do what they say");
  await setCapability("Task creation", "Turn on", "let an approved task really be created");
  const card = await openCapability("Task creation");
  await expect(card).toContainText(/Create a task in Tasks when you approve one the agent proposed/i);
  await capture(page, join(SHOTS, "bug-62-capability-control.png"));
});

test("asking for a task in Chat raises an approval that says it will create it", async () => {
  test.setTimeout(300_000);
  await newChat();
  await ask(
    `Call create_task once with the title "${TASK_TITLE}" and a one-line description, ` +
      "then tell me exactly what the tool returned.",
  );
  await expect(page.getByRole("main")).toContainText(/approval required|approval is needed/i, {
    timeout: 60_000,
  });

  await openNewestCreateTaskApproval();
  // The defect's first half: the owner used to be told, correctly, that this
  // decision executed nothing — for a tool whose whole point was to create one.
  const detail = page.getByRole("main");
  await expect(detail).toContainText(/Approving this creates the task above in Tasks, once/i);
  await expect(detail).not.toContainText(/does NOT execute the action/i);
  await expect(page.getByRole("button", { name: "Approve and execute once" })).toBeVisible();
  await capture(page, join(SHOTS, "bug-62-approval-will-create.png"));
});

test("approving it creates the task, and the inbox links to it", async () => {
  test.setTimeout(300_000);
  await page.getByRole("button", { name: "Approve and execute once" }).click();

  // The defect itself, closed: "Recorded … NOT executed (metadata-only)" is
  // replaced by the thing that now exists, with the route to it.
  const notice = page.locator(".notice-ok").first();
  await expect(notice).toContainText(/Executed once/i, { timeout: 60_000 });
  await expect(notice).toContainText(TASK_TITLE);
  await expect(notice).not.toContainText(/metadata-only/i);
  await expect(notice.getByRole("link", { name: "Review in Tasks" })).toBeVisible();
  await capture(page, join(SHOTS, "bug-62-approved-and-executed.png"));
});

test("the task is in Tasks", async () => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/tasks`);
  await expect(page.getByText(TASK_TITLE).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "bug-62-task-in-tasks.png"));
});

test("the owner's off switch still wins, and says so before the decision", async () => {
  test.setTimeout(300_000);
  // Security posture: this is not prevention-by-restriction — the capability is
  // the owner's to hold. But an owner who turns it off must get the honest
  // record-only answer back, stated before they decide rather than after.
  await setCapability("Task creation", "Turn off", "checking the off switch still holds");

  await newChat();
  await ask(
    'Call create_task once with the title "Second summary" and a one-line description, ' +
      "then tell me exactly what the tool returned.",
  );
  await openNewestCreateTaskApproval();
  await expect(page.getByRole("main")).toContainText(/does NOT execute the action/i, {
    timeout: 30_000,
  });
  await expect(page.getByRole("button", { name: "Approve (record only)" })).toBeVisible();
  await capture(page, join(SHOTS, "bug-62-gate-off-record-only.png"));
});
