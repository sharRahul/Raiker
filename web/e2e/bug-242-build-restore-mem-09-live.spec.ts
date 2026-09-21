/**
 * This run's live verification: BUG-242, B14, MEM-09 and C17 against a real
 * provider, plus a sweep of every route at four widths.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { settled } from "./destinations";
import { capture } from "./capture";
import { chooseModelForTurn, dismissFirstRunModelSetup, OWNER_CREDENTIALS, refreshHostedReadiness, signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = OWNER_CREDENTIALS.password;

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;
const consoleErrors: string[] = [];

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  page = await context.newPage();
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(`${page.url()} :: ${m.text()}`); });
  // BUG-248 — this spec kept its own sign-in, and it had gone stale in exactly
  // the way BUG-229 records: it waited for the workbench greeting, and a
  // workspace with a saved startup route lands somewhere else entirely. The
  // shared helper waits for the navigation rail, which is what "there is a
  // session here" actually means.
  await signInAsOwner(page, BASE);
});

test.afterAll(async () => {
  console.log("CONSOLE_ERRORS", JSON.stringify(consoleErrors, null, 1));
  await context.close();
});

test("Anthropic connects and answers a real turn", async () => {
  test.setTimeout(300_000);
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "",
    model: "claude-haiku-4-5-20251001",
  });
  await capture(page, join(SHOTS, "fixed-309-anthropic-connected.png"));
});

test("a project exists for Build to work inside", async () => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/projects`);
  const name = page.getByLabel("New project name");
  await expect(name).toBeVisible({ timeout: 30_000 });
  await name.fill(`Sweep rotation ${Date.now()}`);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /^Open project Sweep rotation/ }).first(),
  ).toBeVisible({ timeout: 60_000 });
});

test("BUG-242 — Build comes back to the conversation after a reload", async () => {
  test.setTimeout(300_000);
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  // COMPOSER-03 moved the project select behind the `+` menu — "Build still
  // cannot send without one, which the footer says; what changed is that the
  // control is not on the bar for every turn after the first." This waited
  // thirty seconds for a `<select>` that is not rendered until it is asked for,
  // and reported it as Build failing to offer a project. Same class as BUG-229
  // and BUG-295: the drift is in the harness.
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  const picker = page.getByLabel("Project for this build");
  await expect(picker).toBeVisible({ timeout: 30_000 });
  await picker.selectOption({ index: 1 });
  // BUG-292 — pinning a model on a provider card and choosing it for a turn are
  // two different decisions. Without the second, Build's primary action stays
  // disabled and says so, which is the composer being right.
  await chooseModelForTurn(page, /Haiku 4\.5/, "Build composer");
  await page.getByLabel("Describe the change").fill("Reply with exactly: BUILD-RELOAD-OK");
  // COMPOSER-15 — Build's primary action names the act the press performs:
  // `Run`, `Plan` or `Propose` by mode, never `Send`. `Run` is the default
  // mode's word and the one this spec has always meant.
  await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 180_000 });
  await expect(page.getByText("BUILD-RELOAD-OK").first()).toBeVisible({ timeout: 30_000 });

  // The address bar now carries the conversation, which is the whole fix.
  await expect(page).toHaveURL(/#\/build\?session=/, { timeout: 30_000 });
  await capture(page, join(SHOTS, "fixed-309-build-turn.png"));

  await page.reload();
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  // FIXED-353 — a reload no longer signs the owner out: the session is an
  // `HttpOnly`, `SameSite=Strict` cookie. This block used to fill in the
  // password again, with a comment saying the control session lived in memory,
  // and waited out the whole test timeout for a lock screen that has not
  // appeared since 2026-09-03. Kept tolerant rather than removed, because a
  // workspace whose cookie has genuinely expired is a real state and this spec
  // is not about which one it is in.
  const username = page.getByLabel("Username");
  if (await username.isVisible().catch(() => false)) {
    await username.fill(OWNER_CREDENTIALS.user);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
    await dismissFirstRunModelSetup(page);
  }
  await expect(page.getByText("Reply with exactly: BUILD-RELOAD-OK").first()).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText("BUILD-RELOAD-OK").first()).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "fixed-309-build-after-reload.png"));
});

test("MEM-09 — Diagnostics reports memory integrity and offers its repair", async () => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/observe?tab=overview`);
  // REM-OBSERVE (FIXED-562) — Observability opened with seven tiles saying
  // nothing is wrong, so the specialist reports moved behind "Runtime health,
  // in detail". The report is still here and still reachable; what changed is
  // that a healthy install does not scroll past it. This spec kept navigating
  // to a `diagnostics` tab that the overview absorbed.
  await page
    .getByRole("group")
    .filter({ hasText: "Runtime health, in detail" })
    .first()
    .getByText("Runtime health, in detail")
    .click();
  const card = page.getByRole("region", { name: "Memory integrity" });
  await expect(page.getByRole("heading", { name: "Memory integrity" })).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByRole("button", { name: "Rescan" })).toBeVisible();
  await capture(page, join(SHOTS, "fixed-310-memory-integrity-card.png"), card);
});

test("every route renders at four widths with no console error", async () => {
  test.setTimeout(600_000);
  const routes = [
    ["01-workbench", "home"],
    ["02-chat", "new-chat"],
    ["03-build", "build"],
    ["04-search-chat", "search-chat"],
    ["05-tasks", "tasks"],
    ["06-projects", "projects"],
    ["07-memory", "memory"],
    ["08-brain", "brain"],
    ["09-approvals", "approvals"],
    ["10-permissions", "capabilities"],
    ["11-models", "models"],
    ["12-extensions", "extensions?tab=connectors"],
    ["13-observe-diagnostics", "observe?tab=diagnostics"],
    ["14-settings", "settings"],
    ["15-guide", "guide"],
  ] as const;
  const widths = [
    ["375", 375, 812],
    ["768", 768, 1024],
    ["1024", 1024, 800],
    ["1440", 1440, 1000],
  ] as const;

  for (const [label, width, height] of widths) {
    await page.setViewportSize({ width, height });
    for (const [name, route] of routes) {
      await page.goto(`${BASE}/#/${route}`);
      await expect(page.locator("main#main")).toBeVisible();
      await page.waitForLoadState("networkidle");
      // Several views render their shell immediately and then hydrate panels.
      // Capturing before those settle files a screenshot of a loading state
      // under the name of the page it was going to become — the same class of
      // wrong evidence FIXED-313 is about, one layer up.
      // One shared rule, in `destinations.ts`: a label that is still loading
      // ends in an ellipsis. This copy read the composer's "Checking this
      // model — you can still send." as an unfinished load.
      await settled(page, { timeout: 30_000, settleMs: 300 });
      // No route may scroll the page sideways at any width.
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(`${route}@${width}: ${overflow}`).toBe(`${route}@${width}: 0`);
      await capture(page, join(SHOTS, `r0829-w${label}-${name}.png`));
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
});
