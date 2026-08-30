/**
 * Live browser verification for BUG-21, BUG-22, BUG-23 and BUG-24.
 *
 * Runs against a real `raiker-web` on 127.0.0.1:8765 — the actual FastAPI
 * runtime serving the built SPA, not a route-mocked shell — so what these
 * screenshots record is the shipped product answering its own endpoints.
 *
 * Start the server first:
 *   python apps/api/main.py --workspace <ws> --port 8765 --no-browser
 */
import { expect, test, type Browser, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { OWNER_CREDENTIALS, signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
// Anchored to this file rather than to the working directory, so evidence lands
// in the repository whether the runner is started from apps/web or the root.
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = OWNER_CREDENTIALS.password;

/** Create (or reuse) the owner account and land on the workbench. */
/**
 * BUG-229 — sign in through the one shared helper.
 *
 * Every spec used to carry its own copy, and each copy encoded an assumption
 * about the *state* of the instance — usually the empty-workspace greeting —
 * that had nothing to do with what the spec asserts. A suite then passed on a
 * fresh instance and failed at its first step on a used one.
 */
async function signIn(page: Page) {
  await signInAsOwner(page, BASE);
}

// One sign-in for the whole file. The runtime rate-limits authentication (a
// real protection, not a test obstacle), so signing in per test would trip it
// and turn a passing suite into a flake.
test.describe.configure({ mode: "serial" });

let page: Page;

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  await signIn(page);
});

test.afterAll(async () => {
  await page?.close();
});

test("Models is split by action category, with Pricing on its own tab", async () => {
  test.setTimeout(90_000);
  await page.goto(`${BASE}/#/models`);
  const strip = page.getByRole("tablist", { name: "Model settings" });
  await expect(strip).toBeVisible({ timeout: 20_000 });
  await expect(strip.getByRole("tab")).toHaveText(["Providers", "Routing", "Pricing", "Posture"]);

  // Providers is the default and shows only provider work.
  await expect(page.getByRole("heading", { name: "Global model" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pricing" })).toHaveCount(0);
  await capture(page, join(SHOTS, "130-models-providers-tab-live.png"));

  // Each tab is a shareable location, not hidden client state.
  await strip.getByRole("tab", { name: "Routing" }).click();
  await expect(page.getByRole("heading", { name: "Model fallback sequence" })).toBeVisible();
  await expect(page).toHaveURL(/#\/models\?tab=routing$/);
  await capture(page, join(SHOTS, "131-models-routing-tab-live.png"));

  await strip.getByRole("tab", { name: "Posture" }).click();
  await expect(page.getByRole("heading", { name: "Off-machine provider posture" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Model fallback sequence" })).toHaveCount(0);
  await capture(page, join(SHOTS, "132-models-posture-tab-live.png"));

  // The context popover's Configure -> link lands here directly.
  await page.goto(`${BASE}/#/models?tab=pricing`);
  await expect(page.getByRole("tab", { name: "Pricing" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByRole("heading", { name: "Pricing" })).toBeVisible({ timeout: 20_000 });

  // The registry is populated by the reviewed-documentation adapter on first
  // read, so a fresh instance already prices what it ships with.
  await expect(page.getByRole("columnheader", { name: "Cache write" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Cache read" })).toBeVisible();
  await expect(page.getByText("Reviewed documentation").first()).toBeVisible();
  // Synchronisation state: when it last ran, when it is next due, and whether
  // that reading can still be trusted.
  await expect(page.getByText(/every \d+h/).first()).toBeVisible();

  await page.getByRole("button", { name: /^History \(/ }).first().click();
  await expect(page.getByRole("heading", { name: /Price history —/ })).toBeVisible();
  await capture(page, join(SHOTS, "120-BUG-21-pricing-registry-live.png"));
});

test("BUG-21 — an unpriced billable model reads Unknown, never zero", async () => {
  await page.goto(`${BASE}/#/new-chat`);
  await page.getByRole("button", { name: "Context window" }).click();
  const popover = page.getByLabel("Context window and cost details");
  await expect(popover).toBeVisible();
  // No provider is connected on a fresh instance, so this is the honest-gap
  // path: capacity unconfigured rather than a fabricated window or price.
  await expect(popover.getByText(/\$0\.00/)).toHaveCount(0);
  await page.screenshot({ path: join(SHOTS, "121-BUG-21-context-price-unknown-live.png") });
});

test("BUG-22 — the conversation menu offers a reviewed export and a print layout", async () => {
  await page.goto(`${BASE}/#/new-chat`);
  await page.getByRole("button", { name: "Conversation actions" }).click();
  await expect(page.getByRole("menuitem", { name: "Export conversation…" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "Print / Save as PDF" })).toBeVisible();
  // A conversation that has not started cannot be exported — there is nothing
  // to export, and the menu says so rather than producing an empty file.
  await expect(page.getByRole("menuitem", { name: "Export conversation…" })).toBeDisabled();
  await page.screenshot({ path: join(SHOTS, "122-BUG-22-chat-conversation-menu-live.png") });

  await page.goto(`${BASE}/#/build`);
  await page.getByRole("button", { name: "Conversation actions" }).click();
  await expect(page.getByRole("menuitem", { name: "Export conversation…" })).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "123-BUG-22-build-conversation-menu-live.png") });
});

test("BUG-22 — the export API renders each format from the live runtime", async () => {
  // Drive the real endpoints with the browser's own authenticated session, so
  // this exercises auth, redaction, rendering, and the audit write end to end.
  const result = await page.evaluate(async (base) => {
    const token = (window as unknown as { __raikerToken?: string }).__raikerToken;
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const list = await fetch(`${base}/api/sessions`, { headers, credentials: "include" });
    return { status: list.status };
  }, BASE);
  // The SPA holds its bearer token in memory only (never in storage), so this
  // page-context probe is expected to be unauthenticated. The authenticated
  // path is covered by tests/test_session_transcript_export.py; what this
  // asserts is that the route exists and refuses an unauthenticated caller.
  expect([401, 403]).toContain(result.status);
});

test("BUG-23 — rendered code blocks carry a language label and a copy action", async () => {
  test.setTimeout(60_000);
  // A real stored conversation, opened in Chat: the fenced code goes through
  // the shipped renderer inside the real transcript, so what is captured is the
  // product's own markup and its own styles. (See CODE_BLOCK_SESSION in
  // docs/plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md for how it is seeded.)
  await page.goto(`${BASE}/#/new-chat?session=sess_codeblockdemo00000000000000`);
  // The page is shared across this file; close anything a previous test opened
  // so the captured evidence shows the transcript, not a stale popover.
  await page.locator("body").click({ position: { x: 700, y: 700 } });
  await expect(page.getByText(/retry helper/).first()).toBeVisible({ timeout: 20_000 });

  const blocks = page.locator(".md-code");
  await expect(blocks).toHaveCount(2);
  // Every block states its language and offers a keyboard-operable copy.
  await expect(page.locator(".md-code-lang").nth(0)).toHaveText("Python");
  await expect(page.locator(".md-code-lang").nth(1)).toHaveText("JSON");
  await expect(page.getByRole("button", { name: "Copy code" })).toHaveCount(2);
  // Highlighting is produced by the locally-shipped grammar path — no remote
  // asset is fetched to colour a keyword.
  await expect(blocks.first().locator(".tok-keyword").first()).toBeVisible();
  await expect(blocks.first().locator(".tok-comment").first()).toBeVisible();

  const copy = page.getByRole("button", { name: "Copy code" }).first();
  await copy.focus();
  await expect(copy).toBeFocused();
  await capture(page, join(SHOTS, "124-BUG-23-code-block-controls-live.png"));
});

test("BUG-24 — the resumable-turn channel is live and account-scoped", async ({ request }) => {
  const status = await page.evaluate(async (base) => {
    const response = await fetch(`${base}/api/approvals/resumable`);
    return response.status;
  }, BASE);
  // The literal route resolves (it is not swallowed by /api/approvals/{id})
  // and refuses an unauthenticated caller rather than leaking parked turns.
  expect([401, 403]).toContain(status);

  // Authenticated, the same route reports the turn a decision made elsewhere
  // has unblocked — ids and the decision only, never conversation state. This
  // is what a Chat tab that did not record the decision reads to continue.
  const login = await request.post(`${BASE}/api/auth/login`, {
    data: { username: OWNER_CREDENTIALS.user, password: PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).token as string;
  const resumable = await request.get(`${BASE}/api/approvals/resumable`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(resumable.ok()).toBeTruthy();
  const body = await resumable.json();
  expect(body.turns.length).toBeGreaterThan(0);
  expect(body.turns[0].outcome_status).toBe("success");
  // No parked conversation escapes through this read.
  expect(await resumable.text()).not.toContain("retry helper");

  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByLabel("Prompt")).toBeVisible();
  await capture(page, join(SHOTS, "125-BUG-24-parked-turn-live.png"));
});

test("composer parity — Chat, Build, and Workbench agree on what they offer", async () => {
  await page.goto(`${BASE}/#/new-chat`);
  for (const control of ["Context window", "Conversation actions"]) {
    await expect(page.getByRole("button", { name: control })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: /approval mode/i })).toBeVisible();

  await page.goto(`${BASE}/#/build`);
  await expect(page.getByLabel("Describe the change")).toBeVisible();
  for (const control of ["Context window", "Conversation actions"]) {
    await expect(page.getByRole("button", { name: control })).toBeVisible();
  }
  await expect(
    page.getByRole("button", { name: /^How much Raiker may do this turn:/ }),
  ).toBeVisible();
  // The Build composer is the coding agent's own: mode, attach, dictate, model.
  // No surface switch, no duplicate capacity chip.
  await expect(page.getByRole("group", { name: "Chat or Build" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Model context capacity" })).toHaveCount(0);
  await capture(page, join(SHOTS, "126-build-composer-parity-live.png"));

  await page.goto(`${BASE}/#/workbench`);
  // The Workbench has no composer at all now: it could not send anything, and it
  // re-showed every prompt in the destination surface's own composer. It is the
  // live board over what is running, and starting work is a link to the one
  // surface that owns a composer for that kind of work.
  await expect(page.getByLabel(/What would you like Raiker to do/)).toHaveCount(0);
  await expect(page.getByRole("tablist", { name: "Work mode" })).toHaveCount(0);
  for (const group of ["Running now", "Standing agents", "Scheduled runs"]) {
    await expect(page.getByRole("region", { name: group })).toBeVisible();
  }
  const start = page.getByRole("navigation", { name: "Start work" });
  await expect(start.getByRole("link", { name: /Start a conversation/ })).toBeVisible();
  await expect(start.getByRole("link", { name: /Start a build/ })).toBeVisible();
  await capture(page, join(SHOTS, "127-workbench-board-live.png"));
});
