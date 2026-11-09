/**
 * Quiet UI 02 — Allow with limits, the Within limits profile, rule suggestions,
 * connection presets and permissions shown everywhere without a reload,
 * against a running host.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `raiker-web --workspace <ws> --port 8765 --no-browser`.
 *   2. `RAIKER_LIVE_WORKSPACE` naming that workspace, and `RAIKER_LIVE_SEED`
 *      naming a script that parks one approval in it the way the tool broker
 *      does (`<script> <workspace> write|send <key>` printing the approval id).
 *      Parking needs a model turn otherwise; every decision after it is made
 *      through the product's own controls.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Allow with limits"):
 * RT-LIM-01 … RT-LIM-06.
 */
import { execFileSync } from "node:child_process";

import { expect, test, type Page } from "@playwright/test";

import { settled } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const SEED = process.env.RAIKER_LIVE_SEED ?? "";
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../output/playwright/2026-11-08-allow-with-limits";

function park(kind: "write" | "send", key: string): string {
  return execFileSync(PYTHON, [SEED, WORKSPACE, kind, key], { cwd: "..", encoding: "utf-8" }).trim();
}

async function open(page: Page, hash: string): Promise<void> {
  await page.goto(`${BASE}/${hash}`);
  await settled(page);
}

async function start(page: Page): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
}

async function call(page: Page, method: string, path: string, body?: unknown): Promise<number> {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/);
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (csrf) headers["X-Raiker-CSRF"] = decodeURIComponent(csrf[1]);
      const response = await fetch(path, {
        method, headers, credentials: "same-origin", body: body === undefined ? undefined : JSON.stringify(body),
      });
      return response.status;
    },
    { method, path, body },
  );
}

test.beforeAll(() => {
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE").not.toBe("");
  expect(SEED, "set RAIKER_LIVE_SEED").not.toBe("");
});

test("RT-LIM-01 — Allow for this task: the limits are required, and the rule is kept in words", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  const approvalId = park("write", "limit_task");
  await open(page, `#/approvals?item=${approvalId}`);
  await page.getByRole("button", { name: "Allow for this task…" }).click();
  const form = page.getByRole("form", { name: "Allow for this task" });
  await expect(form.getByRole("radio", { name: "This conversation" })).toBeChecked({ timeout: 30_000 });
  await expect(form.getByLabel("Sensitive content still asks")).toBeChecked();
  await expect(form.getByLabel("Attachments still ask")).toBeChecked();
  await expect(page.getByText(/Always allow/i)).toHaveCount(0);
  // Future work with nowhere named is refused before anything is asked.
  await form.getByRole("radio", { name: "Future work" }).click();
  await form.getByRole("button", { name: "Allow and keep these limits" }).click();
  await expect(form.getByRole("alert")).toHaveText(/name who or where/);
  await form.getByRole("radio", { name: "This conversation" }).click();
  await form.getByLabel("At most").fill("3");
  await form.getByLabel("For").selectOption({ label: "1 hour" });
  await page.screenshot({ path: `${SHOTS}/01-allow-for-this-task-form.png` });
  await form.getByRole("button", { name: "Allow and keep these limits" }).click();
  await expect(page.getByText(/Rule kept: Only in the conversation it was allowed in · 3 of 3 uses left/)).toBeVisible({
    timeout: 60_000,
  });
  await page.screenshot({ path: `${SHOTS}/02-rule-kept.png` });
});

test("RT-LIM-02 — the rule reads the same in Memory › Controls and Settings › Security", async ({ page }) => {
  test.setTimeout(120_000);
  await start(page);
  await open(page, "#/memory?tab=controls");
  const controls = page.locator("#panel-controls");
  await expect(controls.getByText(/Only in the conversation it was allowed in · 3 of 3 uses left/)).toBeVisible({
    timeout: 30_000,
  });
  await page.screenshot({ path: `${SHOTS}/03-memory-controls.png` });
});

test("RT-LIM-03 — Within limits is offered in the composer, with what it means", async ({ page }) => {
  test.setTimeout(120_000);
  await start(page);
  await open(page, "#/new-chat");
  await page.getByRole("button", { name: /without asking: Standard/ }).click();
  await expect(page.getByRole("radio", { name: /Within limits/ })).toBeVisible();
  await expect(page.getByText(/plus the rules you made with Allow with limits/)).toBeVisible();
  await page.waitForTimeout(600); // the menu fades in
  await page.screenshot({ path: `${SHOTS}/04-within-limits-chip.png` });
  await page.getByRole("radio", { name: /Within limits/ }).click();
  await expect(page.getByRole("button", { name: /without asking: Within limits/ })).toBeVisible();
});

test("RT-LIM-04 — the same narrow action, allowed three times, is suggested and never made", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  for (const key of ["send_a", "send_b", "send_c"]) park("send", key);
  await open(page, "#/approvals");
  const suggestion = page.getByRole("region", { name: "Rules you could make" });
  await expect(suggestion.getByText(/to launch\s+3 times this week/)).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: `${SHOTS}/05-suggestion.png` });
  await suggestion.getByRole("button", { name: "Make this a rule" }).click();
  await expect(suggestion.getByText(/Rule kept\. In conversations set to Within limits · Only to launch/)).toBeVisible({
    timeout: 30_000,
  });
});

test("RT-LIM-05 — a new connection starts Read only; the owner chooses Ask before changes", async ({ page }) => {
  test.setTimeout(180_000);
  await start(page);
  expect(await call(page, "POST", "/api/connector-store/github/install")).toBe(200);
  await open(page, "#/connections?tab=services");
  await page.getByRole("option", { name: /GitHub/ }).first().click();
  await expect(page.getByRole("radio", { name: /Read only/ })).toBeChecked({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Recent activity" })).toBeVisible();
  await expect(page.getByText("Nothing yet.")).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: `${SHOTS}/06-connection-read-only.png` });
  await page.getByRole("radio", { name: /Ask before changes/ }).click();
  await expect(page.getByRole("radio", { name: /Ask before changes/ })).toBeChecked();
  await page.reload();
  await settled(page);
  await page.getByRole("option", { name: /GitHub/ }).first().click();
  await expect(page.getByRole("radio", { name: /Ask before changes/ })).toBeChecked({ timeout: 30_000 });
  await expect(page.getByText("Nothing yet.")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Recent activity could not be read.")).toHaveCount(0);
  await page.screenshot({ path: `${SHOTS}/07-connection-ask.png` });
});

test("RT-LIM-06 — a rule revoked in one tab leaves the other tab's list without a reload", async ({ page, context }) => {
  test.setTimeout(180_000);
  await start(page);
  await open(page, "#/memory?tab=controls");
  const controls = page.locator("#panel-controls");
  const rule = controls.locator("li").filter({ hasText: /Only to launch/ });
  await expect(rule).toBeVisible({ timeout: 30_000 });
  const other = await context.newPage();
  await other.setViewportSize({ width: 1440, height: 900 });
  await other.goto(`${BASE}/#/settings?tab=security`);
  await settled(other);
  await other
    .locator(".setting-row")
    .filter({ has: other.getByRole("heading", { name: "Standing approval grants" }) })
    .getByRole("button", { name: "Manage" })
    .click();
  const row = other.locator("ul.grants li").filter({ hasText: /Only to launch/ });
  await row.getByRole("button", { name: "Revoke" }).click();
  await expect(row.getByText("Revoked")).toBeVisible({ timeout: 30_000 });
  // The first tab was never reloaded.
  await expect(rule).toHaveCount(0, { timeout: 30_000 });
  await other.screenshot({ path: `${SHOTS}/08-revoked-in-security.png` });
  await page.screenshot({ path: `${SHOTS}/09-gone-without-reload.png` });
});
