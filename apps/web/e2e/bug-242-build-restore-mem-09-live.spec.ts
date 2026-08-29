/**
 * This run's live verification: BUG-242, B14, MEM-09 and C17 against a real
 * provider, plus a sweep of every route at four widths.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import {
  dismissFirstRunModelSetup,
  refreshHostedReadiness,
  useHostedModel,
} from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Ithink@10";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;
const consoleErrors: string[] = [];

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  page = await context.newPage();
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(`${page.url()} :: ${m.text()}`); });
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const username = page.getByLabel("Username");
  await username.fill("Rahul");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /Sign in|Unlock/ }).click();
  }
  await expect(
    page.getByRole("button", { name: "Decide later" })
      .or(page.getByRole("heading", { name: "Welcome to your Work Dashboard" }))
      .first(),
  ).toBeVisible({ timeout: 90_000 });
  await dismissFirstRunModelSetup(page);
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
  const picker = page.getByLabel("Project for this build");
  await expect(picker).toBeVisible({ timeout: 30_000 });
  await picker.selectOption({ index: 1 });
  await page.getByLabel("Describe the change").fill("Reply with exactly: BUILD-RELOAD-OK");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 180_000 });
  await expect(page.getByText("BUILD-RELOAD-OK").first()).toBeVisible({ timeout: 30_000 });

  // The address bar now carries the conversation, which is the whole fix.
  await expect(page).toHaveURL(/#\/build\?session=/, { timeout: 30_000 });
  await capture(page, join(SHOTS, "fixed-309-build-turn.png"));

  await page.reload();
  // The control session lives in memory, so a reload asks for the password
  // again — and the URL survives it, which is what carries the owner back to
  // the conversation they were in rather than to an empty one.
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  await page.getByLabel("Username").fill("Rahul");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Unlock Raiker", exact: true }).click();
  await dismissFirstRunModelSetup(page);
  await expect(page.getByText("Reply with exactly: BUILD-RELOAD-OK").first()).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText("BUILD-RELOAD-OK").first()).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "fixed-309-build-after-reload.png"));
});

test("MEM-09 — Diagnostics reports memory integrity and offers its repair", async () => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/observe?tab=diagnostics`);
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
      await page.waitForFunction(
        () =>
          ![...document.querySelectorAll("main#main *")].some((element) => {
            const node = element as HTMLElement;
            const visible = node.offsetWidth > 0 || node.offsetHeight > 0;
            return visible && /^(loading|reading|checking|verifying)\b/i.test(
              (node.textContent ?? "").trim(),
            );
          }),
        undefined,
        { timeout: 30_000 },
      );
      await page.waitForTimeout(300);
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
