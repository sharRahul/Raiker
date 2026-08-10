/**
 * Live browser verification for BUG-37, BUG-39, BUG-40 and BUG-41.
 *
 * Runs against a real `raiker-web` on 127.0.0.1:8765 — the actual FastAPI
 * runtime serving the built SPA, answering its own endpoints, holding a real
 * Anthropic credential entered through the product UI. Nothing here is
 * route-mocked; that suite is `composer.spec.ts`, and it is the one CI runs.
 *
 * Start the server first:
 *   npm --prefix apps/web run build
 *   python apps/api/main.py --workspace <ws> --port 8765 --no-browser \
 *     --rate-limit-per-minute 6000
 *   RAIKER_LIVE_ANTHROPIC_KEY=… RAIKER_LIVE_WORKSPACE=<ws> \
 *     npm --prefix apps/web run test:e2e:live
 *
 * The raised rate limit is not a workaround for a defect. The visual audit below
 * loads every route at four widths in two themes — 136 page loads, each firing
 * its own reads — which is far more traffic in a minute than a person generates
 * and more than the 120/min per-IP default is meant to allow. The default is a
 * real protection and is left exactly as it is in the product; the audit simply
 * cannot run under it.
 *
 * What each part proves:
 *
 * * **BUG-37** — every route is walked at 375 / 768 / 1024 / 1440 px in both
 *   themes and checked for horizontal overflow and console errors, the type
 *   scale and motion tokens are read back off the running document, and Compact
 *   density is shown to actually shorten a table row rather than only the gaps
 *   around it.
 * * **BUG-39** — the Tasks card for a parked scheduled run states that
 *   approving continues it automatically, and demotes *Continue now* to the
 *   quiet recovery affordance. The signal itself is a server-side race that a
 *   browser cannot observe directly; it is covered by
 *   `tests/test_scheduler_wakeup.py`.
 * * **BUG-40** — the Host control reports state, names the platform mechanism
 *   that would start Raiker in the background, states what a quit would
 *   interrupt, and pauses and resumes the host for real.
 * * **BUG-41** — not verified here by construction: its whole point is that the
 *   *mocked* suite is trustworthy and runs in CI. `npm run test:e2e:mocked` is
 *   its evidence.
 *
 * Quit is deliberately not pressed. With nothing in flight it would succeed,
 * which would stop the host this suite is running against; both of its branches
 * — the waiting-work report and the confirmed stop — are covered by
 * `tests/test_api_host.py`.
 */
import { execFileSync } from "node:child_process";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const REPO = join(import.meta.dirname, "..", "..", "..");
const PASSWORD = "Bug-37-41-live-password-C1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";

// Every route the app has. Walked at four widths in two themes, which is the
// audit BUG-37 asks for and the part no amount of token discipline replaces.
const ROUTES = [
  "workbench", "new-chat", "build", "search-chat", "tasks", "projects", "memory", "brain",
  "approvals", "capabilities", "models", "extensions?tab=connectors", "extensions?tab=mcp",
  "observe?tab=overview", "observe?tab=sessions", "observe?tab=diagnostics", "settings",
] as const;
const WIDTHS = [375, 768, 1024, 1440] as const;

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  // An explicit context, so the wide-viewport audit can open its own tab in the
  // same signed-in session rather than sweeping the tab everything else uses.
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  page = await context.newPage();
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 20_000 });
  const confirm = page.getByLabel("Confirm password");
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 20_000 });
});

test.afterAll(async () => await context?.close());

test("a real Anthropic turn answers, so the rest of this file is evidence", async () => {
  test.setTimeout(240_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");

  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  // The card's own model line, not the option still sitting in the open picker.
  await expect(card.locator("code").filter({ hasText: /Haiku 4\.5/i })).toBeVisible({
    timeout: 30_000,
  });

  await page.goto(`${BASE}/#/new-chat`);
  await page.getByPlaceholder("How can I help you today?").fill("Reply with exactly: VISUAL LIVE");
  await page.getByRole("button", { name: "Send" }).click();
  // Substring, not exact: the answer is a real model's, and a live turn that
  // adds a trailing word is still a live turn. What is being proved here is that
  // the credential, the egress policy and the streaming path all work.
  await expect(page.getByText(/VISUAL LIVE/).last()).toBeVisible({ timeout: 180_000 });
  await page.screenshot({ path: join(SHOTS, "185-live-turn-visual-language.png"), fullPage: true });
});

// ── BUG-37 ───────────────────────────────────────────────────────────────

test("the type scale, motion set and density tokens are live on the document", async () => {
  test.setTimeout(60_000);
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible();

  const tokens = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    const read = (name: string) => style.getPropertyValue(name).trim();
    const headings = ["h1", "h2", "h3"].map((tag) => {
      const node = document.createElement(tag);
      node.textContent = "x";
      document.body.append(node);
      const size = parseFloat(getComputedStyle(node).fontSize);
      node.remove();
      return size;
    });
    return {
      scale: [
        "--text-2xs", "--text-xs", "--text-sm", "--text-md", "--text-base",
        "--text-lg", "--text-xl", "--text-2xl", "--text-display",
      ].map(read),
      motion: ["--motion-enter", "--motion-exit", "--motion-emphasis"].map(read),
      density: [read("--control-y"), read("--row-y")],
      headings,
      serif: read("--font-serif"),
    };
  });

  expect(tokens.scale.every(Boolean)).toBe(true);
  // Read as milliseconds: the production minifier rewrites `180ms` as `.18s`,
  // and the durations are what matter, not how they are spelled in the bundle.
  const ms = (value: string) =>
    value.endsWith("ms") ? parseFloat(value) : parseFloat(value) * 1000;
  expect(tokens.motion.map(ms)).toEqual([180, 120, 240]);
  expect(tokens.density.every(Boolean)).toBe(true);
  expect(tokens.serif).toContain("Source Serif");
  // The ladder the old 1.45 / 1.08 / 0.95rem headings did not have: each level
  // is a visible interval, so heading rank is carried by size, not weight alone.
  const [h1, h2, h3] = tokens.headings;
  expect(h1 / h2).toBeGreaterThan(1.15);
  expect(h2 / h3).toBeGreaterThan(1.15);
});

test("every page holds up at 375, 768, 1024 and 1440 in both themes", async () => {
  test.setTimeout(900_000);
  // The signed-in tab, not a new one: the bearer token is held in memory only
  // (a deliberate security property), so a second tab is a signed-out tab.
  const sweep = page;
  const errors: string[] = [];
  const overflowing: string[] = [];
  sweep.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  sweep.on("pageerror", (error) => errors.push(error.message));

  try {
    for (const theme of ["light", "dark"] as const) {
      await sweep.goto(`${BASE}/#/workbench`);
      await sweep.evaluate((choice) => {
        localStorage.setItem("raiker.theme", choice);
        document.documentElement.dataset.theme = choice;
      }, theme);
      for (const width of WIDTHS) {
        await sweep.setViewportSize({ width, height: 1000 });
        for (const route of ROUTES) {
          await sweep.goto(`${BASE}/#/${route}`);
          await expect(sweep.locator("main#main")).toBeVisible({ timeout: 20_000 });
          // A page that could not load its data proves nothing about its layout,
          // and silently measuring an error card as if it were the page is how
          // an audit passes without auditing anything.
          await expect(sweep.getByText("Unavailable (429)")).toHaveCount(0);
          // Let the route's own reads land before measuring — measuring the
          // shell before its content arrives audits a loading state, not a page
          // — and pace the sweep. Hash navigation fires no load event, so
          // without this the next route starts while the previous one's reads
          // are still in flight, and 136 routes queue about a thousand requests
          // the host then spends minutes draining.
          await sweep.waitForTimeout(220);
          // The shell must never scroll sideways. Wide content (tables,
          // diagrams) scrolls inside its own container; the page body does not.
          const overflow = await sweep.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
          );
          if (overflow > 1) overflowing.push(`${theme} ${width}px ${route} (+${overflow}px)`);
        }
      }
    }
  } finally {
    await sweep.setViewportSize({ width: 1440, height: 1000 });
  }

  expect(overflowing).toEqual([]);
  expect(errors).toEqual([]);
});

test("the finished visual language is recorded in both themes", async () => {
  test.setTimeout(180_000);
  const pages: [string, string, RegExp][] = [
    ["workbench", "186-visual-workbench", /Welcome/],
    ["models?tab=pricing", "187-visual-models-pricing", /Pricing|Choose where Raiker thinks/],
    ["settings", "188-visual-settings-density", /Settings/],
    ["tasks", "189-visual-tasks", /Plan work/],
  ];
  for (const theme of ["light", "dark"] as const) {
    await page.evaluate((choice) => {
      localStorage.setItem("raiker.theme", choice);
      document.documentElement.dataset.theme = choice;
    }, theme);
    for (const [route, name, heading] of pages) {
      await page.goto(`${BASE}/#/${route}`);
      // Models is the slow one: it reloads the provider catalogue and can run a
      // due capacity refresh against every configured runtime before rendering.
      await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible({ timeout: 90_000 });
      if (route === "settings") {
        await page.getByRole("button", { name: "Personalisation" }).click();
        await expect(page.getByRole("radiogroup", { name: "Density" })).toBeVisible();
      }
      await page.waitForTimeout(250);
      await page.screenshot({ path: join(SHOTS, `${name}-${theme}.png`), fullPage: true });
    }
  }
  await page.evaluate(() => {
    localStorage.setItem("raiker.theme", "light");
    document.documentElement.dataset.theme = "light";
  });
});

test("Compact density shortens a real row, not only the gaps around it", async () => {
  test.setTimeout(120_000);
  // Observe → Sessions is a plain shared `.table` with real rows in it, which is
  // exactly the surface the old density setting left untouched.
  const rowHeight = async () => {
    await page.goto(`${BASE}/#/observe?tab=sessions`);
    const row = page.locator("table.table tbody tr").first();
    await expect(row).toBeVisible({ timeout: 30_000 });
    return (await row.boundingBox())?.height ?? 0;
  };

  // Settings is save-on-confirm, not save-on-click: choosing a density marks the
  // page dirty and the owner presses Save. Nothing is applied until then, which
  // is the correct behaviour and the thing a test has to honour rather than
  // assume away.
  const choose = async (mode: string, screenshot?: string) => {
    const loaded = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/settings") && response.request().method() === "GET",
    );
    await page.goto(`${BASE}/#/settings`);
    // Wait for the page's own read to land before touching a control. Choosing
    // while that read is still in flight used to be silently discarded when it
    // resolved — the control showed the new value and the save wrote the old
    // one. That was FIXED-85, found here; waiting keeps this test measuring
    // density rather than re-testing the fix.
    await loaded.catch(() => undefined);
    await page.getByRole("button", { name: "Personalisation" }).click();
    const density = page.getByRole("radiogroup", { name: "Density" });
    await density.getByRole("radio", { name: new RegExp(mode) }).click();
    await expect(density.getByRole("radio", { name: new RegExp(mode) })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    if (screenshot) await page.screenshot({ path: join(SHOTS, screenshot), fullPage: true });
    // Choosing clears any previous confirmation, so waiting for that to go is
    // what stops the assertion below from matching the *last* save's banner and
    // reporting a write that never happened.
    await expect(page.getByText("All changes saved.")).toHaveCount(0);
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByText("All changes saved.")).toBeVisible({ timeout: 20_000 });
  };

  await choose("Comfortable");
  const comfortable = await rowHeight();

  await choose("Compact", "190-BUG-37-density-compact-live.png");
  await expect(page.locator("html")).toHaveAttribute("data-spacing", "compact", { timeout: 20_000 });
  const compact = await rowHeight();

  expect(compact).toBeGreaterThan(0);
  // The defect was that density moved only the spacing scale, so a table stayed
  // exactly as tall while the space around it changed.
  expect(compact).toBeLessThan(comfortable);

  await choose("Comfortable");
});

// ── BUG-39 ───────────────────────────────────────────────────────────────

test("a parked scheduled run says approving continues it, and offers a recovery", async () => {
  test.setTimeout(120_000);
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE to the running host's workspace").not.toBe("");

  // The card's *parked* state is what this test is about, and reaching it
  // through a full approval round trip needs the model to propose a governed
  // write and then stop — long, expensive, and flaky as a screenshot source.
  // The state is written here by `TaskManager`, which is the same code the
  // scheduler itself calls, so the card being read is the real card. The signal
  // that continues the run is a server-side race a browser cannot see, and is
  // covered by `tests/test_scheduler_wakeup.py`.
  execFileSync(
    "python",
    [
      "-c",
      [
        "import sys",
        "from raiker.events.writer import EventLogWriter",
        "from raiker.storage.sqlite import SQLiteStore",
        "from raiker.tasks.manager import TaskManager",
        "store = SQLiteStore(sys.argv[1])",
        "owner = store.original_account_principal_id()",
        "session = f'sess_inbox_{owner}'",
        "store.create_session(session, sys.argv[1], title='Inbox')",
        "manager = TaskManager(store, EventLogWriter(store))",
        // Idempotent: re-running this suite must not stack another parked run,
        // or the counts the Host control reports stop being reproducible.
        "parked = store.list_tasks(status='waiting_for_approval')",
        "if not parked:",
        "    task = manager.create_task(session_id=session, title='Nightly release note',"
          + " objective='Draft and file the nightly release note.')",
        "    manager.block_task_on_approval(task.task_id,"
          + " 'Waiting for your approval before this run can continue.')",
      ].join("\n"),
      WORKSPACE,
    ],
    { cwd: REPO, stdio: "inherit" },
  );

  await page.goto(`${BASE}/#/tasks`);
  await expect(page.getByRole("heading", { name: "Open work" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("waiting for approval").first()).toBeVisible();
  await expect(
    page.getByText("Approving continues this run automatically.").first(),
  ).toBeVisible();
  // Demoted to a recovery affordance: still there, no longer the fast path.
  await expect(page.getByRole("button", { name: "Continue now" }).first()).toHaveClass(/btn-ghost/);
  await page.screenshot({ path: join(SHOTS, "193-BUG-39-approval-continues-live.png"), fullPage: true });
});

// ── BUG-40 ───────────────────────────────────────────────────────────────

test("the Host control reports the host, and pauses and resumes it", async () => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/workbench`);
  await page.getByRole("button", { name: /^Host/ }).click();

  // This runs after the BUG-39 seed, so there is a parked run in the workspace
  // and "needs attention" is the honest state — a control reading "running"
  // while an approval blocks every scheduled routine tells the truth about the
  // process and lies about the product.
  const panel = page.getByRole("region", { name: "Host control" });
  await expect(panel.getByText("Raiker host")).toBeVisible();
  await expect(panel.getByText("needs attention", { exact: true })).toBeVisible();
  // Both the summary line and the background-work list say it, which is the
  // point: the state pill and the work list have to agree.
  await expect(panel.getByText("1 run is waiting for your approval.")).toBeVisible();
  await expect(
    panel.getByText("1 run is waiting for your approval", { exact: true }),
  ).toBeVisible();
  // Named platform mechanism, not a Raiker daemon of its own.
  await expect(panel.getByText(/systemd --user|launchd|Windows per-user startup/)).toBeVisible();
  await expect(panel.getByRole("button", { name: "Quit" })).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "191-BUG-40-host-control-live.png"), fullPage: true });

  await panel.getByRole("button", { name: "Pause" }).click();
  await expect(panel.getByText("paused", { exact: true })).toBeVisible({ timeout: 20_000 });
  await expect(panel.getByText(/Scheduled work will not start until you resume/)).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "192-BUG-40-host-paused-live.png"), fullPage: true });

  await panel.getByRole("button", { name: "Resume" }).click();
  await expect(panel.getByText("needs attention", { exact: true })).toBeVisible({ timeout: 20_000 });
  await page.keyboard.press("Escape");
});
