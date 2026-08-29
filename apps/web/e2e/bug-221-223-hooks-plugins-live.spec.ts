/**
 * The hooks → plugins half of the extensibility gap, against a real instance.
 *
 * Two closures share one surface, so they share one spec:
 *
 * * **BUG-223** — twenty-two lifecycle events were specified and nine were
 *   emitted. Seven more are wired now, and every event the schema accepts has a
 *   call site. The page has to say that: no rule and no catalogue entry may be
 *   marked "Never fires", because none of them are dead any more.
 * * **BUG-221** — installing a plugin recorded it and then provided nothing. A
 *   plugin may now contribute hook rules, which arrive at `plugin` scope, below
 *   every scope the owner controls. The page has to show the rules, credit them
 *   to the plugin that wrote them, and say what the plugin provides.
 *
 * Written as a live spec because the point is what the *runtime* loaded. A
 * mocked run would only prove the template renders a fixture, and the fixture is
 * the thing under test.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { dismissFirstRunModelSetup } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? process.cwd();
const SHOTS = "../../docs/plans/screenshots/working";

const PLUGIN_ID = "acme-guard";
const PLUGIN_RULES = {
  schema_version: "1.0",
  hooks: {
    PreToolUse: [
      {
        matcher: "shell",
        if: "shell(rm -rf *)",
        handlers: [
          { id: "acme-block", type: "builtin", builtin: "block_destructive_shell" },
        ],
      },
    ],
    TaskCreated: [
      {
        matcher: "*",
        handlers: [
          { id: "acme-watch", type: "builtin", builtin: "block_destructive_shell" },
        ],
      },
    ],
  },
};

function writePluginContribution() {
  const dir = join(WORKSPACE, ".raiker", "plugins", PLUGIN_ID);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "hooks.json"), JSON.stringify(PLUGIN_RULES, null, 2), "utf-8");
}

function removePluginContribution() {
  rmSync(join(WORKSPACE, ".raiker", "plugins", PLUGIN_ID), { recursive: true, force: true });
}

async function signIn(page: import("@playwright/test").Page) {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
  await page.getByLabel("Username").fill("Rahul");
  await page.getByLabel("Password", { exact: true }).fill("Ithink@10");
  // Keyed off the confirm *field*, not the create button: the login screen also
  // carries a "Create a User Account" button that only switches mode, so the
  // button is visible on a screen that has no account to create.
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill("Ithink@10");
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker", exact: true }).click();
  }
  const workbench = page.getByRole("heading", { name: "Welcome to your Work Dashboard" });
  await expect(
    page.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
  await expect(workbench).toBeVisible({ timeout: 30_000 });
}

// Serial: every test signs the same owner in against one live instance, and a
// parallel run has them racing to create the account.
test.describe.configure({ mode: "serial" });

test.beforeAll(() => writePluginContribution());
test.afterAll(() => removePluginContribution());

test("no accepted hook event is still marked as never firing (BUG-223)", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  await expect(page.getByRole("heading", { name: "Hooks", exact: true })).toBeVisible();

  const catalogue = page
    .getByRole("heading", { name: "What fires, and what it can change" })
    .locator("xpath=ancestor::section[1]");
  await expect(catalogue).toBeVisible();

  // The seven BUG-223 added, named individually: a count would pass on the
  // wrong seven, and each of these is a call site that can be deleted.
  for (const event of [
    "SessionEnd",
    "Stop",
    "StopFailure",
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
  ]) {
    await expect(catalogue.getByText(event, { exact: true })).toBeVisible();
  }
  // The gap itself is closed: nothing in the catalogue is dead.
  await expect(catalogue.getByText("Never fires")).toHaveCount(0);

  await capture(page, `${SHOTS}/bug-223-hook-event-catalogue.png`);
});

test("a plugin's contributed rules are listed and credited to it (BUG-221)", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto(`${BASE}/#/extensions?tab=hooks`);

  const rules = page
    .getByRole("heading", { name: "Configured rules" })
    .locator("xpath=ancestor::section[1]");
  await expect(rules).toBeVisible();
  // Credited to the plugin, not to the word "plugin": every installed plugin
  // loads at the same scope, so the scope word no longer identifies a file.
  await expect(rules.getByText(PLUGIN_ID).first()).toBeVisible();
  await expect(rules.getByText(`.raiker/plugins/${PLUGIN_ID}/hooks.json`).first()).toBeVisible();
  // And the rule is enforcing, not decorative — a builtin on PreToolUse is the
  // one combination whose decision the runtime honours.
  await expect(rules.getByText("Can deny or ask").first()).toBeVisible();

  await capture(page, `${SHOTS}/bug-221-plugin-contributed-rules.png`);
});

test("the plugins tab says what may be contributed and what may not", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto(`${BASE}/#/extensions?tab=plugins`);

  const kinds = page
    .getByRole("heading", { name: "What a plugin may contribute" })
    .locator("xpath=ancestor::section[1]");
  await expect(kinds).toBeVisible();
  await expect(kinds.getByText("Hooks", { exact: true }).locator("xpath=..")).toContainText(
    "Available",
  );
  await expect(kinds.getByText("Panels", { exact: true }).locator("xpath=..")).toContainText(
    "Not yet",
  );

  await capture(page, `${SHOTS}/bug-221-plugin-contribution-kinds.png`);
});

test("the hooks and plugins tabs hold together at every window size", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  for (const [label, width, height] of [
    ["mobile", 390, 844],
    ["tablet", 834, 1112],
    ["desktop", 1440, 1000],
  ] as const) {
    await page.setViewportSize({ width, height });
    for (const [tab, settled] of [
      ["hooks", "Configured rules"],
      ["plugins", "What a plugin may contribute"],
    ] as const) {
      await page.goto(`${BASE}/#/extensions?tab=${tab}`);
      await expect(page.locator("main#main")).toBeVisible();
      // Waited for by *content*, not by `networkidle`. These routes differ only
      // in the fragment, so `goto` does not navigate and `networkidle` resolves
      // against the previous page — measuring the layout of a tab that has not
      // rendered yet and photographing the drawer mid-transition.
      await expect(page.getByRole("heading", { name: settled })).toBeVisible({
        timeout: 20_000,
      });
      // The strip scrolls sideways below 1024px, and six tabs are wider than a
      // phone. Asserting the *selected* tab is on screen is what catches the
      // state this page was in before: the Plugins panel under a strip scrolled
      // to the start, with the selected tab off the right edge and Hooks looking
      // like the current one.
      const current = page.getByRole("tab", { selected: true });
      await expect(current).toHaveText(tab === "hooks" ? "Hooks" : "Plugins");
      await expect(current).toBeInViewport({ ratio: 0.9 });
      // The page body must never scroll sideways. A rule's matcher, a source
      // path and a contributed-events list are all long strings, and any of
      // them overflowing is the failure this catches.
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${tab} at ${label} scrolls horizontally`).toBeLessThanOrEqual(1);
      // Viewport, not `fullPage`. The navigation is `position: fixed` below
      // 1024px, and a full-page capture composites it as though it were in flow
      // — producing a picture of a half-open drawer that no one ever sees. The
      // viewport shot is what the phone actually shows.
      await page.screenshot({ path: `${SHOTS}/bug-221-223-${tab}-${label}.png` });
    }
  }
});
