/**
 * `InstructionsLoaded` and `PostToolBatch` against a real model turn (FIXED-305).
 *
 * `tests/test_hooks_surface.py` derives the dispatched set from the source, so a
 * missing call site fails there. `tests/test_hooks_lifecycle.py` drives each new
 * call site through the object that owns it, so a guard behind a condition that
 * is never true fails there. Neither proves the events are reached on the path a
 * person actually takes — a real prompt, a real provider, a real tool call — and
 * that is the failure the whole hooks surface exists to make visible.
 *
 * Both events are observation-only, so a turn that fired them looks identical on
 * screen to one that did not. The evidence is therefore the durable record:
 * `hook_matched` and `hook_executed` on the Hooks tab's own activity list, for a
 * turn this spec sent.
 *
 * `Notification` is proved in `tests/test_hooks_lifecycle.py` rather than here.
 * It fires from the notification path rather than from a turn, and reaching it
 * live would mean parking a real approval only to abandon it — a worse test of
 * the same call site.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { dismissFirstRunModelSetup, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? process.cwd();
const PASSWORD = "Lifecycle-hooks-305-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

/**
 * A rule on each of the two turn-scoped events FIXED-305 added.
 *
 * Written before the first turn and safe to write while the host is running:
 * `AgentGateway` is constructed per request, so the registry is re-read every
 * turn. `block_destructive_shell` is the observer — it returns `no_decision` for
 * every tool that is not `shell`, so it executes without changing anything,
 * which is exactly what an observation-only event should be able to show.
 */
function writeLifecycleHooks() {
  const dir = join(WORKSPACE, "config");
  mkdirSync(dir, { recursive: true });
  const rule = [
    {
      matcher: "*",
      handlers: [
        { id: "lifecycle-watch", type: "builtin", builtin: "block_destructive_shell" },
      ],
    },
  ];
  writeFileSync(
    join(dir, "hooks.json"),
    JSON.stringify(
      {
        schema_version: "1.0",
        hooks: { InstructionsLoaded: rule, PostToolBatch: rule },
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
  const workbench = target.getByRole("heading", { name: /Welcome to your Work Dashboard/ });
  await expect(
    target.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(target);
  await expect(workbench).toBeVisible({ timeout: 30_000 });
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  writeLifecycleHooks();
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

test("the three new events are offered, and each says it only observes", async () => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  const catalogue = page
    .getByRole("heading", { name: "What fires, and what it can change" })
    .locator("xpath=ancestor::section[1]");
  await expect(catalogue).toBeVisible({ timeout: 30_000 });

  for (const event of ["Notification", "PostToolBatch", "InstructionsLoaded"]) {
    const row = catalogue.getByRole("listitem").filter({ hasText: event }).first();
    await expect(row).toBeVisible();
    // Each fires after the thing it describes has already happened, so none of
    // them may read as a decider. A page that showed "Decides" here would be
    // telling the owner a guard exists that the runtime does not honour.
    await expect(row).toContainText("Observes");
    await expect(row).not.toContainText("Never fires");
  }
  // The whole catalogue: every event this build's schema accepts is emitted.
  await expect(catalogue.getByText("Never fires")).toHaveCount(0);

  // `fullPage` does not reach past the shell's own scroll container, so the
  // section under test is brought into view before the capture. A screenshot
  // that does not contain the thing it is named for is not evidence.
  await catalogue.scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(SHOTS, "fixed-305-lifecycle-event-catalogue.png") });
});

test("both rules load and are reported as live before any turn runs", async () => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  const rules = page
    .getByRole("heading", { name: "Configured rules" })
    .locator("xpath=ancestor::section[1]");
  await expect(rules).toBeVisible({ timeout: 30_000 });

  const loaded = rules.getByRole("listitem").filter({ hasText: "InstructionsLoaded" }).first();
  await expect(loaded).toContainText("Observes only");
  const batch = rules.getByRole("listitem").filter({ hasText: "PostToolBatch" }).first();
  await expect(batch).toContainText("Observes only");
  await expect(rules.getByText("never fires")).toHaveCount(0);
});

test("a real tool-using turn fires both, and the audit log is the proof", async () => {
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
  // A tool call is what makes this turn different from BUG-223's: without one
  // there is no batch, and `PostToolBatch` correctly fires nothing.
  await composer.fill(
    "Use your tools to list the files in the current directory, then tell me how many there are.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });

  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  const activity = page
    .getByRole("heading", { name: "Recent hook activity" })
    .locator("xpath=ancestor::section[1]");
  await expect(activity).toBeVisible({ timeout: 30_000 });
  // Named rather than counted: an activity list holding only `InstructionsLoaded`
  // would satisfy a bare "something matched" and would mean the batch event
  // never fired.
  await expect(activity.getByText("InstructionsLoaded").first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(activity.getByText("PostToolBatch").first()).toBeVisible({ timeout: 30_000 });
  await expect(activity.getByText("matched").first()).toBeVisible({ timeout: 30_000 });
  await expect(activity.getByText("executed").first()).toBeVisible({ timeout: 30_000 });

  await activity.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: join(SHOTS, "fixed-305-lifecycle-hooks-fired-on-a-real-turn.png"),
  });
});
