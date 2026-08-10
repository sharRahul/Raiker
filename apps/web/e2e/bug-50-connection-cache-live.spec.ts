/**
 * BUG-50 against a running `raiker-web` — the evidence behind that entry.
 *
 * FIXED-91 caches one keyed SQLCipher connection per workspace and worker
 * thread, so a burst of cheap reads pays key derivation once. It had explicit
 * invalidation but no eviction: the cache was keyed by workspace and grew
 * without bound. BUG-50's own words for who that hurts are "a long-lived host
 * serving many instances, each of which is its own workspace" — and that is
 * exactly what this spec builds, through the product's own surface.
 *
 * `POST /api/instances` is the shipped, loopback-only endpoint behind the login
 * screen's instance form. Each call creates an isolated workspace, mounts its
 * own ASGI app inside this host, and registers its first account — which opens
 * that workspace's SQLCipher database in *this* process. Thirty of them is a
 * host that has served many instances, in one run.
 *
 * What is asserted:
 *
 *  1. The host's open file descriptors stay bounded while it serves thirty more
 *     instance workspaces. Before the bound, fifty workspaces in one process
 *     took a process from 4 open descriptors to 154 and released none.
 *  2. The owner's own workspace still works afterwards, across every route and
 *     with its data intact — the bound evicts stale workspaces, it does not
 *     break the one in use. That is the whole of BUG-50's "UI when closed": no
 *     user-visible change under normal use.
 *
 * The descriptor count is read from `/proc/<pid>/fd`, which is why that test is
 * Linux-only and skips elsewhere: a browser cannot screenshot a file descriptor,
 * but the run either keeps the host bounded or it does not. The screenshots
 * record the product surface on either side of it.
 *
 * **On the hosted model.** The last test drives a real hosted turn and is the
 * only part of this file that needs a provider credential. It skips, with the
 * reason stated in the run, when `RAIKER_LIVE_ANTHROPIC_KEY` is absent or the
 * provider rejects it — nothing above it depends on a model, because what BUG-50
 * changes is below the model entirely.
 *
 * Prerequisites:
 *   npm --prefix apps/web run build
 *   RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com \
 *     python apps/api/main.py --workspace <ws> --port 8765 --no-browser \
 *     --rate-limit-per-minute 6000
 *   RAIKER_LIVE_HOST_PID=<pid of that host> [RAIKER_LIVE_ANTHROPIC_KEY=…] \
 *     npm --prefix apps/web run test:e2e:live
 */
import { readdirSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { hostedProviderCard } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Connection-cache-live-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";
const HOST_PID = process.env.RAIKER_LIVE_HOST_PID ?? "";

/** How many extra instance workspaces this host is made to serve. */
const INSTANCES = 30;

/**
 * The dashboard's own heading, matched exactly. The lock screen's heading is
 * "Welcome to Raiker", so a loose /Welcome/ is satisfied by a *signed-out* page
 * — which is how the first version of this spec screenshotted the login screen
 * and called it a working host.
 */
const DASHBOARD = /^Welcome (to your Work Dashboard|back)$/;

/** Routes the owner's own workspace has to keep serving after all of that. */
const ROUTES = ["workbench", "new-chat", "build", "tasks", "sessions", "memory", "models"];

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;
let consoleErrors: string[] = [];

/** The host process's open file descriptors, read the only way a test can. */
function hostDescriptors(): number {
  return readdirSync(`/proc/${HOST_PID}/fd`).length;
}

/** Land on the owner's dashboard, settled — not on the lock screen behind it. */
async function openDashboard(target: Page) {
  await target.goto(`${BASE}/#/workbench`);
  await expect(target.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  await expect(target.getByRole("heading", { name: DASHBOARD })).toBeVisible({ timeout: 30_000 });
  await expect(target.getByText("Loading status…")).toBeHidden({ timeout: 30_000 });
  await expect(target.getByText("Updating…")).toBeHidden({ timeout: 30_000 });
}

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
  await expect(target.getByRole("heading", { name: DASHBOARD })).toBeVisible({ timeout: 30_000 });
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await signIn(page);
});

test.afterAll(async () => await context?.close());

test("the owner's workspace is a working host before any of this", async () => {
  test.setTimeout(120_000);
  expect(HOST_PID, "set RAIKER_LIVE_HOST_PID to the raiker-web process id").not.toBe("");
  // Read from /proc before anything else, so a wrong pid fails here and not
  // three tests later inside the measurement.
  expect(hostDescriptors()).toBeGreaterThan(0);

  await openDashboard(page);
  await page.screenshot({
    path: join(SHOTS, "bug-50-host-before-many-instances.png"),
    fullPage: true,
  });
});

test("the instance surface this exercises is the product's own", async () => {
  test.setTimeout(120_000);
  // The endpoint driven below is the one behind this form; recorded so the
  // measurement is read against a real surface rather than an internal call.
  const login = await context.newPage();
  await login.goto(`${BASE}/#/`);
  await expect(login.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  await login.locator("button.instance-button").click();
  await expect(login.getByLabel("Instance name")).toBeVisible({ timeout: 30_000 });
  await login.screenshot({
    path: join(SHOTS, "bug-50-instance-creation-surface.png"),
    fullPage: true,
  });
  await login.close();
});

test("serving thirty more instance workspaces keeps the host's descriptors bounded", async () => {
  test.setTimeout(300_000);
  test.skip(process.platform !== "linux", "the descriptor count is read from /proc");

  const before = hostDescriptors();
  const stamp = Date.now().toString(36);

  for (let index = 0; index < INSTANCES; index += 1) {
    const name = `bug50-${stamp}-${index}`;
    const created = await page.request.post(`${BASE}/api/instances`, {
      data: { name, username: `owner${index}`, password: `Instance-live-${index}-A1!` },
    });
    expect(created.ok(), `instance ${name}: ${created.status()}`).toBeTruthy();
    // Serve the mounted instance too, so its own app is exercised and not just
    // created — this is the "host serving many instances" BUG-50 names.
    const served = await page.request.get(`${BASE}/instances/${name}/api/health`);
    expect(served.ok()).toBeTruthy();
  }

  const after = hostDescriptors();
  // Recorded in the run, not only in an assertion message: the number is the
  // evidence, and a passing test that prints nothing proves it to nobody.
  test.info().annotations.push({
    type: "descriptors",
    description: `${before} → ${after} while serving ${INSTANCES} instance workspaces`,
  });
  // Unbounded, each retained workspace cost roughly three descriptors and never
  // gave them back. The bound is the process ceiling, not the workspace count,
  // so the growth here has to stay far below what thirty retained handles cost.
  expect(
    after - before,
    `descriptors grew ${before} → ${after} while serving ${INSTANCES} instances`,
  ).toBeLessThan(INSTANCES * 2);
});

test("the owner's own workspace is untouched by the eviction", async () => {
  test.setTimeout(180_000);
  consoleErrors = [];

  for (const route of ROUTES) {
    await page.goto(`${BASE}/#/${route}`);
    await expect(page.locator("main")).toBeVisible({ timeout: 30_000 });
  }

  // The owner's session, account and stored state all live in the workspace the
  // cache was evicting *around*. A reload proves the store still answers for it,
  // and the dashboard is only settled once its status panel has resolved — that
  // panel is read straight out of this workspace's database.
  await openDashboard(page);
  expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);
  await page.screenshot({
    path: join(SHOTS, "bug-50-host-after-many-instances.png"),
    fullPage: true,
  });
});

test("a real hosted turn still answers on the host that served them", async () => {
  test.setTimeout(300_000);
  test.skip(ANTHROPIC_KEY === "", "no RAIKER_LIVE_ANTHROPIC_KEY for a hosted turn");

  const card = await hostedProviderCard(page, BASE, "Anthropic");
  await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
  await page.getByLabel("Anthropic API key").fill(ANTHROPIC_KEY);
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connected")).toBeVisible({ timeout: 60_000 });

  await card.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = card.getByLabel("Available models");
  const reachable = await catalogue.isVisible({ timeout: 60_000 }).catch(() => false);
  // A credential the provider itself rejects is not a finding about this host.
  // The product says so on the card; the turn below simply cannot be driven.
  test.skip(!reachable, "the provider rejected this credential — no live catalogue");

  await catalogue.selectOption(MODEL);
  await card.getByRole("button", { name: "Use model" }).click();
  await expect(card.locator("code").filter({ hasText: /Haiku 4\.5/i })).toBeVisible({
    timeout: 30_000,
  });

  await page.goto(`${BASE}/#/new-chat`);
  await page.getByPlaceholder("How can I help you today?").fill("Reply with exactly: CACHE LIVE");
  await page.getByRole("button", { name: "Send" }).click();
  // Scoped to the transcript: the prompt is echoed in the sent bubble and in the
  // recent-chat rail, and neither of those is an answer.
  await expect(page.getByRole("main").getByText("CACHE LIVE", { exact: true })).toBeVisible({
    timeout: 180_000,
  });
  await page.screenshot({
    path: join(SHOTS, "bug-50-hosted-turn-after-many-instances.png"),
    fullPage: true,
  });
});
