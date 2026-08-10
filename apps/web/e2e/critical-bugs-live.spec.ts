/**
 * Live browser evidence for the 2026-08-10 round: FIXED-150 (the SQLCipher
 * lockout and the screen that contradicted itself), FIXED-151 (the empty audit
 * log), FIXED-152 (the Knowledge Map picker that browsed the whole
 * installation), and the six skills Raiker now ships.
 *
 * Runs against a real `raiker-web` holding a real Anthropic credential entered
 * through the product's own dialog — not a route-mocked shell. Start it first:
 *
 *   npm --prefix apps/web run build
 *   python apps/api/main.py --workspace <ws> --port 8765 --no-browser \
 *     --rate-limit-per-minute 6000
 *   RAIKER_LIVE_ANTHROPIC_KEY=… npm --prefix apps/web run test:e2e:live
 *
 * The one exception is the store-unavailable screen. A store that will not open
 * cannot be produced by driving the product — the platform has to refuse to
 * lock pages — so that scenario intercepts `/api/health` and asserts what the
 * *page* does with the answer the server would give. Everything else is real.
 */
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { useHostedModel, dismissFirstRunModelSetup } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const REPO = join(import.meta.dirname, "..", "..", "..");
const SHOTS = join(REPO, "docs", "plans", "screenshots", "working");
const PASSWORD = "Critical-bugs-live-password-F4!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";

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
  // The workspace shell mounting is the signal, not the greeting: a returning
  // owner's Workbench does not open with "Welcome", so waiting for that made
  // the second run of this suite fail on a sign-in that had in fact worked.
  await expect(target.getByRole("navigation", { name: "All navigation" }))
    .toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(target);
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  // The hook's own default is 30s, which is shorter than the sign-in it
  // performs — a slow first bootstrap would abort the suite before the page
  // had a chance to answer.
  test.setTimeout(180_000);
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  page = await context.newPage();
  await signIn(page);
});

test.afterAll(async () => await context?.close());

test("FIXED-150 — the lock screen's strip and its message describe the same store", async () => {
  test.setTimeout(120_000);
  const probe = await context.newPage();
  try {
    // Healthy: the strip says operational, and it is entitled to, because the
    // probe it read opened the store.
    await probe.goto(`${BASE}/#/workbench`);
    await expect(probe.getByText("Runtime operational")).toBeVisible({ timeout: 30_000 });
    await expect(probe.getByRole("button", { name: /unlock|sign in|Create a User Account/i }).first())
      .toBeEnabled();
    await probe.screenshot({ path: join(SHOTS, "215-FIXED-150-store-healthy-live.png") });

    // Unavailable: the same screen must not go on calling the runtime
    // operational. The server cannot be made to refuse locked pages on demand,
    // so this is the answer it would give, and the assertion is about what the
    // page does with it.
    await probe.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "degraded",
          store: "unavailable",
          reason: "store_memory_lock_unavailable",
          detail:
            "This machine would not lock the memory pages SQLCipher holds the workspace key in.",
          cipher_memory_security: "on",
          memory_security_reason: "requested_on",
        }),
      }),
    );
    await probe.reload();
    await expect(probe.getByText("Encrypted store unavailable")).toBeVisible({ timeout: 30_000 });
    await expect(probe.getByText("Runtime operational")).toHaveCount(0);
    await expect(probe.getByRole("alert")).toContainText(/encrypted store could not be opened/i);
    // No password can answer a store that will not open, so the form does not
    // invite one.
    await expect(probe.getByLabel("Username")).toBeDisabled();
    await probe.screenshot({ path: join(SHOTS, "216-FIXED-150-store-unavailable-live.png") });
  } finally {
    await probe.close();
  }
});

test("FIXED-151 — connecting a provider and pinning a model appear in the audit log", async () => {
  test.setTimeout(300_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");

  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await expect(card.locator("code")).toBeVisible({ timeout: 30_000 });

  // These are governed steps taken outside any conversation. Before the fix the
  // page showed "No events match" with no filters set, immediately after them.
  await page.goto(`${BASE}/#/observe?tab=activity`);
  const rows = page.locator("table.table tbody tr");
  await expect(rows.first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("No events match")).toHaveCount(0);
  await expect(page.getByText(/every governed step in this account/i)).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "217-FIXED-151-audit-log-live.png"), fullPage: true });

  // Overview reads the same source, so it must agree with it.
  await page.goto(`${BASE}/#/observe?tab=overview`);
  await expect(page.getByText("No events recorded yet.")).toHaveCount(0);
});

test("FIXED-152 — the Knowledge Map picker opens on named places, not the installation", async () => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/brain`);
  await page.getByRole("button", { name: "Add workspace source" }).click();
  const dialog = page.getByRole("dialog", { name: "Add a source" });
  await expect(dialog).toBeVisible({ timeout: 30_000 });

  // The boundary is named. Raiker's own tree — the thing the picker used to
  // list — is not reachable from here at all.
  await expect(dialog.getByRole("button", { name: /Generated files/ })).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Approved memory/ })).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Raiker database/ })).toBeVisible();
  await expect(dialog.getByText(/Chat, Build, Tasks, Schedules/)).toBeVisible();
  for (const stray of ["raiker", "apps", "docs", "scripts", "pyproject.toml"]) {
    await expect(dialog.getByRole("button", { name: new RegExp(`^\\s*(Folder|File)\\s*${stray}\\s*$`) }))
      .toHaveCount(0);
  }
  // The database is a statement, not a folder to walk.
  await expect(dialog.getByRole("button", { name: /Raiker database/ })).toBeDisabled();
  await page.screenshot({ path: join(SHOTS, "218-FIXED-152-knowledge-boundary-live.png") });

  // Both ways in from the computer are offered, and they say which is which.
  await expect(dialog.getByText(/Grant a folder/)).toBeVisible();
  await expect(dialog.getByLabel("Folder to grant")).toBeVisible();
  await expect(dialog.getByText(/Or add a single file/)).toBeVisible();

  // Granting a folder reads it where it is.
  const granted = mkdtempSync(join(tmpdir(), "raiker-granted-"));
  writeFileSync(join(granted, "research.md"), "# research\n", "utf-8");
  try {
    await dialog.getByLabel("Folder to grant").fill(granted);
    await dialog.getByRole("button", { name: "Grant folder access" }).click();
    await expect(dialog.getByRole("button", { name: /research\.md/ })).toBeVisible({ timeout: 30_000 });
    await dialog.getByRole("button", { name: /research\.md/ }).click();
    await dialog.getByRole("button", { name: "Review indexing plan" }).click();
    await expect(dialog.getByRole("heading", { name: "Indexing plan" })).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: join(SHOTS, "219-FIXED-152-granted-folder-live.png") });
    await dialog.getByRole("button", { name: "Add reviewed source" }).click();
    await expect(dialog).toBeHidden({ timeout: 30_000 });
  } finally {
    rmSync(granted, { recursive: true, force: true });
  }
});

test("the six shipped skills install on first visit", async () => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/extensions?tab=skills`);
  await expect(page.getByRole("heading", { name: "Skills", level: 2 })).toBeVisible({ timeout: 30_000 });
  for (const name of [
    "algorithm-creator",
    "code-review",
    "mcp-builder",
    "plugin-dev",
    "security-review",
    "skill-creator",
  ]) {
    await expect(page.getByText(name, { exact: true })).toBeVisible();
  }
  // The tab must not imply an authority the runtime does not enforce.
  await expect(page.getByText(/grants no capability/i)).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "220-six-shipped-skills-live.png"), fullPage: true });
});
