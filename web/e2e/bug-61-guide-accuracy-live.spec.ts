/**
 * BUG-61 against a running `raiker-web` — the evidence behind the re-derived
 * **Known limits** sections of `docs/guide/`.
 *
 * FIXED-103 re-derived the README's Known limits. The user guide carried two
 * more of those sections, reached from the README's own Documentation list, and
 * not one entry in either was still true: it told a reader that Markdown is not
 * rendered, that there is no export, that an approved file write does not reach
 * the disk, that a background-agent failure has no user-visible reason, and that
 * task runs pollute RECENT CHATS. All five had shipped. Reading the rest of the
 * guide for the same drift found more: five runtime modes that FIXED-63 replaced
 * with one, and an MCP section still calling BUG-12 a current limit.
 *
 * Re-deriving those sections from the tree is half the fix. This spec is the
 * other half: each test holds up a claim the guide now makes, against the
 * running product rather than against the source it was read from.
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
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";

// Serial because every test shares one signed-in page. That is what this file
// needs and also what hid the defect above: a failure in one test stops the file,
// so the two tests that need a model to answer took the six that do not down with
// them on every host without one. `requiresModel` marks those two, so a round
// without a provider skips them *with the reason* and still runs the rest —
// the same shape `requireFirstRunWorkspace` uses for a spec that needs a fresh
// workspace (BUG-250).
test.describe.configure({ mode: "serial" });

/** Skip, with the reason, when no key was supplied for this round. */
function requiresModel(): void {
  test.skip(
    ANTHROPIC_KEY === "",
    "Needs a provider that answers. Set RAIKER_LIVE_ANTHROPIC_KEY — and, for an " +
      "identity-linked key, its workspace id — to run this one (BUG-273).",
  );
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
  await signInAsOwner(target, BASE);
}

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

test("a provider key is added through the UI and a real turn answers", async () => {
  requiresModel();
  test.setTimeout(240_000);

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

test("working-in-chat — a reply is rendered Markdown, not raw text", async () => {
  requiresModel();
  test.setTimeout(300_000);
  await newChat();
  // The guide used to say "Markdown is not rendered (BUG-03) — headings, tables,
  // lists and fenced code appear as raw text". FIXED-06 shipped the renderer.
  const answer = await ask(
    "Reply with exactly this Markdown and nothing else: a level-2 heading reading " +
      "GUIDE CHECK, then a two-item bulleted list, then a fenced ts code block " +
      "containing `const guide = 1;`.",
  );
  await expect(answer.locator("h2")).toContainText("GUIDE CHECK", { timeout: 30_000 });
  await expect(answer.locator("li")).toHaveCount(2);
  await expect(answer.locator("pre code")).toContainText("const guide = 1;");
  // The same section's claim about every code block carrying its language and a
  // keyboard-reachable copy control.
  await expect(answer.getByText("TypeScript", { exact: false })).toBeVisible();
  await expect(answer.getByRole("button", { name: /Copy code/i })).toBeVisible();
  await capture(page, join(SHOTS, "bug-61-markdown-rendered.png"));
});

test("working-in-chat — the transcript offers export, in three formats", async () => {
  // Not because export needs a model, but because there is nothing to export
  // until a turn has produced a conversation.
  requiresModel();
  test.setTimeout(120_000);
  // "No export (BUG-08) — no download, PDF or print control" was the guide's
  // second stale line. FIXED-12, superseded by FIXED-19 and FIXED-54, shipped it.
  await page.getByRole("button", { name: /Conversation actions/i }).click();
  const exportItem = page.getByRole("menuitem", { name: /Export conversation/i });
  await expect(exportItem).toBeVisible({ timeout: 10_000 });
  await exportItem.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await expect(dialog).toContainText(/HTML/);
  await expect(dialog).toContainText(/Markdown/);
  await expect(dialog).toContainText(/PDF/);
  await capture(page, join(SHOTS, "bug-61-export-review.png"));
  await page.keyboard.press("Escape");
});

test("permissions — one runtime, not a five-mode picker", async () => {
  test.setTimeout(120_000);
  // The guide's "Runtime modes" table listed Development preview, Local single
  // user safe, Local single user runtime, Multi user local runtime and Hosted or
  // networked runtime, and told a reader to activate one in Settings → General
  // before a gate could mean anything. FIXED-63 replaced all five with one.
  await page.goto(`${BASE}/#/settings`);
  const runtime = page.getByText(/Runtime/).first();
  await expect(runtime).toBeVisible({ timeout: 30_000 });
  const body = page.getByRole("main");
  await expect(body).not.toContainText("Development preview");
  await expect(body).not.toContainText("Multi user local runtime");
  await expect(body).not.toContainText("Hosted or networked runtime");
  await capture(page, join(SHOTS, "bug-61-single-runtime.png"));
});

test("getting-started — every destination is where the guide says it is", async () => {
  test.setTimeout(120_000);
  // The guide's "What you get" table had Sessions under Work and "Brain" under
  // Knowledge. Sessions is a tab inside Observability now, and Brain is the
  // Knowledge Map.
  //
  // **This test had itself gone stale, and could not say so.** It asserted that
  // Permissions, Models, Extensions, Observability and Settings are links in the
  // navigation rail. They left it when the sidebar kept only the work and
  // everything you set up once moved behind the gear — so the assertion had been
  // false since that change, and nobody saw it, because two model-dependent
  // tests sit above it in a `mode: "serial"` file and this host has no model
  // that can answer. A guard that cannot run is not a guard, which is the other
  // half of what FIXED-416 found in the sweeps.
  //
  // So it asserts the split rather than one flat list: what is on the rail, and
  // what is behind the gear. That is the fact an owner needs and the one
  // `getting-started.md` now states (FIXED-417).
  await page.goto(`${BASE}/#/workbench`);
  const nav = page.getByRole("navigation", { name: "All navigation" });
  await expect(nav).toBeVisible({ timeout: 30_000 });

  // The rail: the work. "Threads" since C18 made this the board as well as the
  // search; the guide once called it "Search Chat".
  for (const label of [
    "Workbench", "Chat", "Build", "Design", "Threads", "Tasks", "Projects",
    "Approvals", "Messaging", "Memory", "Knowledge Map",
  ]) {
    await expect(nav.getByRole("link", { name: label, exact: true })).toHaveCount(1);
  }
  await expect(nav.getByRole("link", { name: "Sessions", exact: true })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Brain", exact: true })).toHaveCount(0);
  await capture(page, join(SHOTS, "bug-61-navigation.png"));

  // The gear: what you set up once. Reachable, and reachable from here — a
  // destination that left the rail and landed nowhere would pass the loop above.
  //
  // "Settings" itself is deliberately not a row: its ten sections are the rows,
  // because a bare link would open General while sitting above a row that says
  // General. Writing this assertion the obvious way — expecting a "Settings"
  // link — is what found the defect underneath: those ten rows emitted
  // `?section=` while the router read `?tab=`, so every one of them opened
  // General anyway (FIXED-418).
  await page.getByRole("button", { name: "Settings and pages" }).click();
  const allPages = page.getByRole("dialog");
  await expect(allPages).toBeVisible({ timeout: 30_000 });
  for (const label of ["Permissions", "Models", "Extensions", "Observability", "Guide"]) {
    await expect(allPages.getByRole("link", { name: label, exact: true })).toHaveCount(1);
  }
  await expect(allPages.getByRole("link", { name: "Settings", exact: true })).toHaveCount(0);
  await capture(page, join(SHOTS, "bug-61-all-pages.png"));

  // And a section row opens *that section*, not the one above it.
  await allPages.getByRole("link", { name: "Privacy", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Privacy", exact: true })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("Retained working")).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "bug-61-settings-section-deep-link.png"));
});

test("extensions-and-mcp — the page states whether the agent can call a server", async () => {
  test.setTimeout(120_000);
  // "Current limit (BUG-12): a connected server's tools are not offered to the
  // model in Chat" was the guide's claim. FIXED-17 made them callable and
  // FIXED-96 made the page say so — including, as here with the gate still off,
  // the reason it cannot and the control that changes it.
  //
  // **This assertion had gone stale too, and could not say so** — it wanted the
  // sentence *"Raiker cannot call any MCP tool: the MCP connector capability is
  // not enabled at runtime level."* `McpView` deliberately suppresses that one
  // when the gate's own block already says it, because a closed connector used
  // to draw two amber notices one under the other saying the same fact in
  // different words and naming the same page by two different names. The
  // improvement landed, its unit test asserts it, and this spec kept asking for
  // the duplicate — unseen, because two model-dependent tests above it stop the
  // file on a host with no provider.
  //
  // So it asserts the claim rather than the wording: the page names the
  // capability that is off, and offers the control that changes it. A reword
  // still passes; the page going silent does not.
  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  const access = page
    .locator(".notice")
    .filter({ hasText: /MCP connector/i })
    .first();
  await expect(access).toBeVisible({ timeout: 30_000 });
  await expect(access).toContainText(/turned off|not enabled|cannot call/i);
  await expect(access.getByRole("link", { name: /Permissions/i })).toBeVisible();
  await capture(page, join(SHOTS, "bug-61-mcp-agent-access.png"));
});

test("tasks-and-projects — a task run does not appear in RECENT CHATS", async () => {
  // Creating a task with instructions goes through the model-readiness check.
  requiresModel();
  test.setTimeout(300_000);
  // "Task runs create sessions that appear in the sidebar's RECENT CHATS
  // alongside real conversations (BUG-10)" — closed by FIXED-15.
  await page.goto(`${BASE}/#/tasks`);
  await expect(page.getByRole("heading", { name: "Plan work" })).toBeVisible({ timeout: 30_000 });
  await page.getByLabel("Task title").fill("Guide accuracy task");
  await page.getByLabel("Instructions").fill("Reply with the single word DONE.");
  await page.getByRole("button", { name: "Create task", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Guide accuracy task", exact: true }),
  ).toBeVisible({ timeout: 60_000 });

  // The session the run creates is a task session, and the sidebar's recent-chat
  // list is conversations only.
  const recents = page.getByLabel("Recent chats").getByText("Guide accuracy task");
  await expect(recents).toHaveCount(0);
  await capture(page, join(SHOTS, "bug-61-task-not-in-recents.png"));
});

test("tasks-and-projects — asking for a task in Chat raises a real decision", async () => {
  requiresModel();
  test.setTimeout(300_000);
  // The one line the guide carried on trust: "Creating a task by asking for one
  // in Chat is specified but not shipped — the governed create_task tool exists,
  // the conversational flow around it does not." FIXED-98 put `create_task` on
  // the approval path it was built for, so the flow is the approval flow.
  await newChat();
  await ask(
    'Call create_task once with the title "Draft the weekly summary" and a one-line ' +
      "description, then tell me exactly what the tool returned.",
  );
  const transcript = page.getByRole("main");
  await expect(transcript).toContainText(/approval required/i, { timeout: 60_000 });

  await page.goto(`${BASE}/#/approvals`);
  await page.getByLabel("Sort approvals").selectOption({ label: "Newest first" });
  const row = page.getByRole("row", { name: /Create task/i }).first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "bug-61-chat-created-task.png"));

  // How far the flow actually goes is the part the guide has to state, so it is
  // read off the product rather than assumed. When BUG-61 was written it stopped
  // at the decision: `create_task` was not in `EXECUTABLE_ON_APPROVAL`, so
  // approving it recorded a decision and created nothing. FIXED-106 closed that,
  // and the reachable end of the flow — with `task_management_runtime` still off,
  // as it is on a fresh instance — is the honest record-only answer, stated
  // before the owner decides.
  await row.getByRole("button", { name: "Review" }).click();
  await expect(page.getByRole("heading", { name: /Review Create task/i })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByRole("main")).toContainText(/does NOT execute the action/i);
  await page.getByRole("button", { name: "Approve (record only)" }).click();
  await expect(page.getByText(/was NOT executed \(metadata-only\)/i)).toBeVisible({
    timeout: 60_000,
  });
  await capture(page, join(SHOTS, "bug-61-chat-task-record-only.png"));

  // And with the capability off, the task really is not there. Turning it on is
  // one control away — `bug-62-task-approval-executes-live.spec.ts` drives that.
  await page.goto(`${BASE}/#/tasks`);
  await expect(page.getByRole("heading", { name: "Plan work" })).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByRole("heading", { name: "Draft the weekly summary", exact: true }),
  ).toHaveCount(0);
});
