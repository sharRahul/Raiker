/**
 * Quiet UI — the brand, Diagnostics and Recovery, the pages that already fit,
 * and the open items of earlier rounds (docs/plans/quiet-ui/README.md, round of
 * 2026-10-25), against a running host and a real hosted model.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `raiker-web --workspace <ws> --port 8765 --no-browser`.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *   3. For RT-QUI-66 only: `RAIKER_LIVE_WORKSPACE` (the served workspace) and
 *      `RAIKER_LIVE_PYTHON` (a Python with Raiker installed). The case moves a
 *      waiting approval's expiry into the past, which is what thirty unanswered
 *      minutes would do, and then lets the host's own sweep settle it.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Quiet UI brand,
 * Diagnostics and open items"): RT-QUI-57 … RT-QUI-70.
 */
import { execFileSync } from "node:child_process";

import { expect, test, type Locator, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, enableCapability, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";
import { measurePage, overBudget } from "./sizeBudgets";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-25-quiet-ui-polish";
const SERVED_WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "";

async function open(page: Page, hash: string): Promise<void> {
  await page.goto(`${BASE}/${hash}`);
  await settled(page);
}

async function start(page: Page, width = 1440, height = 900): Promise<void> {
  await page.setViewportSize({ width, height });
  await signInAsOwner(page, BASE);
}

async function finished(page: Page): Promise<Locator> {
  const answer = page.locator(".message-group-raiker").last();
  await expect(answer).toBeVisible({ timeout: 180_000 });
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeVisible({ timeout: 240_000 });
  await expect(answer.locator(".response-actions")).toBeVisible({ timeout: 240_000 });
  return answer;
}

/** Ask for one file to be written, in a new chat on Standard. */
async function askForAFile(page: Page, name: string): Promise<void> {
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page
    .getByLabel("Prompt", { exact: true })
    .fill(`Create a file named ${name} in my workspace containing the single word TEAL. Use the file tool; do not ask me first.`);
  await page.getByRole("button", { name: "Send", exact: true }).click();
}

async function pendingApprovalId(page: Page): Promise<string> {
  let id = "";
  await expect(async () => {
    const response = await page.request.get(`${BASE}/api/approvals`);
    const rows = (await response.json()) as { approval_id: string; is_expired?: boolean }[];
    id = rows.find((row) => !row.is_expired)?.approval_id ?? "";
    expect(id).not.toBe("");
  }).toPass({ timeout: 60_000 });
  return id;
}

test("RT-QUI-57 — the lock screen carries the open ring and the lowercase wordmark (QUI-V03, QUI-V04)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE}/`);
  await expect(page.getByText("Checking Raiker…")).toBeHidden({ timeout: 30_000 });
  const ring = page.getByRole("img", { name: "Raiker" });
  await expect(ring).toHaveCount(1);
  await expect(ring.locator("path")).toHaveAttribute("stroke-linecap", "round");
  await expect(page.locator(".lock-header .brand")).toHaveText("raiker");
  // The eye-orb render and its orbit rings are gone.
  await expect(page.locator(".orbit, .core-img")).toHaveCount(0);
  const icon = await page.request.get(`${BASE}/favicon-32x32.png`);
  expect(icon.ok()).toBe(true);
  await capture(page, `${SHOTS}/57-lock-screen-open-ring.png`);
});

test("RT-QUI-58 — Quick Entry before sign-in asks to sign in first", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 560, height: 120 } });
  const page = await context.newPage();
  await page.goto(`${BASE}/#/quick-entry`);
  await expect(page.getByText("Sign in to Raiker first.")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Unlock Raiker" })).toHaveCount(0);
  await capture(page, `${SHOTS}/58-quick-entry-signed-out.png`);
  // In a browser there is no main window to bring forward, so it opens Home.
  await page.getByRole("button", { name: "Open Raiker" }).click();
  await expect(page).toHaveURL(/#\/home$/);
  await context.close();
});

test("RT-QUI-59 — Home offers the model Chat already uses as the default (BUG-357)", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await start(page);
  await open(page, "#/models");
  await page.getByRole("button", { name: "Add model" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Add model" });
  await dialog.getByRole("button", { name: /An account I have/ }).click();
  const card = dialog.locator("article.provider-card").filter({ hasText: "Anthropic" }).first();
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    if (WORKSPACE_ID) {
      await page.getByRole("button", { name: "Advanced" }).last().click();
      await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE_ID);
    }
    await page.locator(".signin-connect").click();
  }
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 90_000 });
  await keepModelAvailable(page, card, MODEL);
  // Deliberately not made the default here: the default is what this case is about.
  const review = dialog.getByRole("region", { name: "3 · Review" });
  await review.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden();

  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  // QUI-16 follow-up — only one readiness line under the composer, and never
  // the "no readiness check exists" sentence beside a model that answers.
  await expect(page.getByText(/No readiness check exists for this exact model/)).toHaveCount(0);
  expect(await page.locator(".rechecking, .readiness-strip").count()).toBeLessThanOrEqual(1);
  await page.getByLabel("Prompt", { exact: true }).fill("Reply with the single word OK.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await finished(page);

  await open(page, "#/home");
  const gaps = page.getByRole("list", { name: "Setup Raiker still needs" });
  const offer = gaps.getByRole("button", { name: /^Use .*, as in Chat$/ });
  await expect(offer).toBeVisible({ timeout: 60_000 });
  await capture(page, `${SHOTS}/59-home-use-chat-model-as-default.png`, gaps);
  await offer.click();
  await expect(page.getByText("No default model is chosen.")).toHaveCount(0, { timeout: 60_000 });
});

test("RT-QUI-60 — a Careful conversation is Careful on another device (QUI-P02, decided 2026-10-25)", async ({ page, browser }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(360_000);
  await start(page);
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  const chip = page.getByRole("button", { name: /^How much Raiker does without asking:/ });
  await chip.click();
  await page.getByRole("radio", { name: /Careful/ }).click();
  await expect(chip).toHaveAttribute("aria-label", /Careful$/);
  await page.getByLabel("Prompt", { exact: true }).fill("Reply with the single word CAREFUL.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await finished(page);
  const session = new URL(page.url()).hash.match(/session=([^&]+)/)?.[1] ?? "";
  expect(session).not.toBe("");

  // A second browser with nothing in its storage: the choice comes from the
  // conversation's own record.
  const other = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const second = await other.newPage();
  await signInAsOwner(second, BASE);
  await second.goto(`${BASE}/#/new-chat?session=${session}`);
  await settled(second);
  const otherChip = second.getByRole("button", { name: /^How much Raiker does without asking:/ });
  await expect(otherChip).toHaveAttribute("aria-label", /Careful$/, { timeout: 60_000 });
  await capture(second, `${SHOTS}/60-careful-on-a-second-browser.png`, second.locator(".footer-facts"));
  await other.close();
});

test("RT-QUI-61 — Diagnostics leads with what needs attention; Recovery is named (QUI-L11)", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  await open(page, "#/observe");
  await expect(page.getByRole("heading", { name: "What needs attention", level: 2 })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/^Checked /).first()).toBeVisible();
  await expect(page.getByText("What is working")).toBeVisible();
  // No hero-metric tiles any more.
  await expect(page.locator("article.tile")).toHaveCount(0);
  await page.getByText("What is working").click();
  await expect(page.locator(".healthy-rows dt", { hasText: "Permissions" })).toBeVisible();
  await capture(page, `${SHOTS}/61-diagnostics-overview.png`);
  await page.getByRole("tab", { name: "Recovery" }).click();
  await expect(page.getByText(/Nothing to recover|Preview restore/).first()).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/61-recovery.png`);
});

test("RT-QUI-62 — Memory: Recall is part of Controls and the map opens from a search (QUI-L12)", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  await open(page, "#/memory");
  const tabs = page.getByRole("tablist", { name: "Memory sections" });
  await expect(tabs.getByRole("tab")).toHaveText(["Overview", "Memories", "Suggestions", "Sources", "Controls"]);
  await open(page, "#/memory?tab=recall");
  await expect(page.getByRole("tab", { name: "Controls" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Incognito session")).toBeVisible();
  await expect(page.getByText("What Raiker has learned to do")).toBeVisible();
  await capture(page, `${SHOTS}/62-memory-controls-with-recall.png`);
  await open(page, "#/memory?tab=memories");
  await page.getByRole("link", { name: "See on the map" }).click();
  await expect(page.getByRole("heading", { name: "Knowledge Map" })).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("main a.back-link")).toHaveAttribute("href", "#/memory?tab=memories");
  await capture(page, `${SHOTS}/62-map-from-memories.png`);
});

test("RT-QUI-63 — Settings › General, Privacy and Advanced fit at 1280×800 (QUI-G01)", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page, 1280, 800);
  const over: string[] = [];
  for (const route of ["settings?tab=general", "settings?tab=privacy", "settings?tab=advanced", "observe"]) {
    await open(page, `#/${route}`);
    await page.waitForTimeout(500);
    const size = await measurePage(page);
    const problems = overBudget(route, size, { height: 800, screens: 1.25 });
    if (problems.length > 0) over.push(`${route}: ${problems.join(", ")}`);
    await capture(page, `${SHOTS}/63-${route.replace(/[^a-z]+/g, "-")}-1280.png`);
  }
  expect(over).toEqual([]);
});

test("RT-QUI-64 — a streaming answer never shows a raiker: block as raw JSON (04)", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(360_000);
  await start(page);
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(
    "From these figures I give you — ThinkPad 15 h battery, MacBook Air 18 h battery — answer with one short sentence, " +
      'then a raiker:figures block with both, unit "h", and source "figures the user gave", then one closing sentence.',
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const answer = page.locator(".message-group-raiker").last();
  await expect(answer).toBeVisible({ timeout: 180_000 });
  const samples: string[] = [];
  while (!(await answer.locator(".response-actions").isVisible().catch(() => false))) {
    samples.push((await answer.innerText().catch(() => "")) ?? "");
    await page.waitForTimeout(120);
    if (samples.length > 2000) break;
  }
  const raw = samples.filter((text) => /raiker:figures|"items"\s*:/.test(text));
  expect(raw, "a sample showed the block's raw JSON while streaming").toEqual([]);
  await expect(answer.locator("figure.key-figures, .refused, .unsourced").first()).toBeVisible({ timeout: 60_000 });
  await capture(page, `${SHOTS}/64-figures-after-streaming.png`, answer);
});

test("RT-QUI-65 — deciding an approval marks its notice read", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await start(page);
  await enableCapability(page, BASE, "File writes", "Live round: Quiet UI polish");
  await enableCapability(page, BASE, "Approval execution relay", "Live round: Quiet UI polish");
  await askForAFile(page, "notice-read.txt");
  const card = page.getByRole("region", { name: "Raiker Safety" }).last();
  await expect(card.getByText("Waiting for your decision")).toBeVisible({ timeout: 240_000 });
  const approvalId = await pendingApprovalId(page);
  const unreadFor = async () => {
    const response = await page.request.get(`${BASE}/api/notifications`);
    const rows = (await response.json()) as { subject_id: string | null; read: number | boolean }[];
    return rows.filter((row) => row.subject_id === approvalId && !row.read).length;
  };
  expect(await unreadFor()).toBe(1);
  await card.getByRole("button", { name: "Decline" }).click();
  // The turn picks up the decision and the card is settled.
  await expect(
    page.getByRole("region", { name: "Raiker Safety" }).filter({ hasText: "Waiting for your decision" }),
  ).toHaveCount(0, { timeout: 120_000 });
  await expect.poll(unreadFor, { timeout: 30_000 }).toBe(0);
  await capture(page, `${SHOTS}/65-declined-notice-settled.png`, page.locator(".message-group-raiker").last());
});

test("RT-QUI-66 — an approval past its time limit is settled by the host, with its event", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.skip(SERVED_WORKSPACE === "" || PYTHON === "", "RAIKER_LIVE_WORKSPACE / RAIKER_LIVE_PYTHON are unset");
  test.setTimeout(480_000);
  await start(page);
  await askForAFile(page, "expired-sweep.txt");
  const card = page.getByRole("region", { name: "Raiker Safety" }).last();
  await expect(card.getByText("Waiting for your decision")).toBeVisible({ timeout: 240_000 });
  const approvalId = await pendingApprovalId(page);
  // Thirty unanswered minutes, without waiting them out.
  execFileSync(PYTHON, [
    "-c",
    [
      "import sys",
      "from raiker.storage.sqlite import SQLiteStore",
      "store = SQLiteStore(sys.argv[1])",
      "with store.connect() as c:",
      "    c.execute(\"UPDATE approvals SET expires_at='2000-01-01T00:00:00Z' WHERE approval_id=?\", (sys.argv[2],))",
    ].join("\n"),
    SERVED_WORKSPACE,
    approvalId,
  ]);
  // The host's sweep runs every fifteen seconds; nothing tries to decide it.
  await expect
    .poll(async () => {
      const response = await page.request.get(`${BASE}/api/approvals/${approvalId}`);
      const body = (await response.json()) as { approval?: { status?: string } };
      return body.approval?.status ?? "";
    }, { timeout: 90_000, intervals: [3_000] })
    .toBe("expired");
  const events = await page.request.get(`${BASE}/api/events?event_type=approval_expired&limit=20`);
  expect(JSON.stringify(await events.json())).toContain("approval_expired");
  await page.reload();
  await settled(page);
  const expired = page.getByRole("region", { name: "Raiker Safety" }).last();
  await expect(expired.getByText("Not done: no decision")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("waiting for your decision", { exact: true })).toHaveCount(0);
  await expect(page.getByText("not done — no decision")).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/66-expired-by-the-sweep.png`, page.locator(".message-group-raiker").last());
});

test("RT-QUI-67 — Build's postures are Plan, Suggest changes and Run within limits (QUI-L13)", async ({ page }) => {
  test.setTimeout(120_000);
  await start(page);
  await open(page, "#/build");
  await page.getByRole("button", { name: /^How much Raiker may do this turn:/ }).click();
  const menu = page.getByRole("menu", { name: "Mode" });
  for (const option of ["Plan", "Suggest changes", "Run within limits"]) {
    await expect(menu.getByRole("menuitemradio", { name: new RegExp(`^${option}`) })).toBeVisible();
  }
  await capture(page, `${SHOTS}/67-build-postures.png`, menu);
  await page.keyboard.press("Escape");
});

test("RT-QUI-68 — Connections has one Add connection while nothing is connected", async ({ page }) => {
  test.setTimeout(120_000);
  await start(page);
  await open(page, "#/connections");
  await expect(page.getByRole("button", { name: "Add connection" })).toHaveCount(1, { timeout: 30_000 });
  await capture(page, `${SHOTS}/68-connections-one-action.png`);
});

test("RT-QUI-69 — a planned turn's status line is not covered by the Plan card", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(360_000);
  await start(page);
  await open(page, "#/new-chat");
  await chooseModelForTurn(page, /Haiku|claude/i);
  await page.getByLabel("Prompt", { exact: true }).fill(
    "Use the plan tool to set a three-step plan for tidying a desk, mark every step done, then answer in one sentence.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const answer = await finished(page);
  const plan = page.locator(".plan-slot");
  const line = answer.locator(".outcome-line").first();
  if ((await plan.count()) > 0 && (await line.count()) > 0) {
    await line.scrollIntoViewIfNeeded();
    const planBox = await plan.boundingBox();
    const lineBox = await line.boundingBox();
    expect(planBox && lineBox ? lineBox.y >= planBox.y + planBox.height - 1 : true).toBe(true);
  }
  await capture(page, `${SHOTS}/69-plan-and-status-line.png`);
});

test("RT-QUI-70 — every destination in the dark theme", async ({ page }) => {
  test.setTimeout(300_000);
  await page.emulateMedia({ colorScheme: "dark" });
  await start(page);
  for (const route of ["home", "new-chat", "build", "design", "work", "memory", "approvals", "capabilities", "models", "connections", "observe", "settings"]) {
    await open(page, `#/${route}`);
    await capture(page, `${SHOTS}/70-dark-${route}.png`);
  }
});
