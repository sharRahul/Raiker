/**
 * `Stop` and `StopFailure` against a real model turn (BUG-223).
 *
 * The unit tests prove the branch picks the right event for a given status, and
 * the surface test proves the call site exists. Neither proves the call site is
 * *reached* on the path a person actually takes — a helper that is correct and
 * never called is the exact failure the whole BUG-223 surface exists to make
 * visible, so one event is driven end to end through a hosted provider, a real
 * prompt, and the durable event log.
 *
 * The evidence is the audit log, not the page: `Stop` is observation-only, so a
 * turn that fired it looks identical to one that did not. What must exist
 * afterwards is `hook_matched` and `hook_executed` for the turn's own session.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { dismissFirstRunModelSetup, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? process.cwd();
const PASSWORD = "Turn-end-hooks-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

/**
 * A `Stop` rule, written before the first turn.
 *
 * Safe to write while the host is running: `AgentGateway` is constructed per
 * request, so the registry is re-read every turn. That is also what makes this a
 * real test of the loading path rather than of a fixture.
 */
function writeStopHook() {
  const dir = join(WORKSPACE, "config");
  mkdirSync(dir, { recursive: true });
  writeFileSync(
    join(dir, "hooks.json"),
    JSON.stringify(
      {
        schema_version: "1.0",
        hooks: {
          Stop: [
            {
              matcher: "*",
              handlers: [
                { id: "turn-end-watch", type: "builtin", builtin: "block_destructive_shell" },
              ],
            },
          ],
        },
      },
      null,
      2,
    ),
    "utf-8",
  );
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
  // The first-run setup wizard is modal on a brand-new instance, so a spec that
  // signs in and navigates straight to Extensions is talking to a page it cannot
  // reach. Waited for rather than sampled: the sheet mounts once the bootstrap
  // reads resolve, which is after account creation returns.
  const workbench = target.getByRole("heading", { name: /Welcome to your Work Dashboard/ });
  await expect(
    target.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(target);
  await expect(workbench).toBeVisible({ timeout: 30_000 });
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  writeStopHook();
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  await signIn(page);
});

test.afterAll(async () => {
  await context?.close();
  rmSync(join(WORKSPACE, "config", "hooks.json"), { force: true });
});

test("the Stop rule is loaded and reported as live before any turn runs", async () => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  const rules = page
    .getByRole("heading", { name: "Configured rules" })
    .locator("xpath=ancestor::section[1]");
  await expect(rules).toBeVisible({ timeout: 30_000 });

  const rule = rules.getByRole("listitem").filter({ hasText: "Stop" }).first();
  await expect(rule).toContainText("A turn finished and produced an answer.");
  // Observation only: a turn that already ended cannot be refused, and the page
  // says so rather than letting the rule look enforcing.
  await expect(rule).toContainText("Observes only");
  await expect(rules.getByText("never fires")).toHaveCount(0);
});

test("a real turn fires Stop, and the audit log is the proof", async () => {
  test.setTimeout(300_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");

  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });

  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill("Reply with exactly the word: acknowledged.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });

  await expect(page.getByText(/acknowledged/i).first()).toBeVisible({ timeout: 30_000 });

  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  const activity = page
    .getByRole("heading", { name: "Recent hook activity" })
    .locator("xpath=ancestor::section[1]");
  await expect(activity).toBeVisible({ timeout: 30_000 });
  await expect(activity.getByText("matched").first()).toBeVisible({ timeout: 30_000 });
  await expect(activity.getByText("executed").first()).toBeVisible({ timeout: 30_000 });

  await capture(page, join(SHOTS, "bug-223-stop-fired-on-a-real-turn.png"));
});
