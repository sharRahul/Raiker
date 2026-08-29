/**
 * The rest of the extensibility gap, against a real instance.
 *
 * Three closures share one surface, so they share one spec:
 *
 * * **BUG-221 step 2** — a plugin may contribute skills. They must arrive
 *   *switched off*, be credited to the plugin on the row, and not offer the two
 *   controls the next reconcile would undo.
 * * **BUG-221 step 3** — a plugin may *offer* an MCP server. The tab has to make
 *   "offered" and "added" different things on screen, because that difference is
 *   the whole safety property.
 * * **BUG-225 step 1** — what a channel message is in a turn is decided. The tab
 *   has to say so without reading as a shipped feature.
 *
 * Live rather than mocked for the same reason as the hooks spec: the point is
 * what the *runtime* loaded off disk, and a fixture would only prove the
 * template renders.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { dismissFirstRunModelSetup } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? process.cwd();
const SHOTS = "../../docs/plans/screenshots/working";

const PLUGIN_ID = "acme-toolkit";
const SKILL_NAME = "acme-review";
const SERVER_NAME = "acme-docs";

const SKILL_DOC = [
  "---",
  `name: ${SKILL_NAME}`,
  "description: Review a change against Acme's internal checklist.",
  "---",
  "",
  "Check the changelog, then the tests, then the migration.",
  "",
].join("\n");

const MCP_OFFER = {
  servers: [
    {
      name: SERVER_NAME,
      transport: "http",
      endpoint_url: "https://mcp.acme.example/v1",
      auth_ref: "ACME_MCP_TOKEN",
      description: "Acme's internal documentation index.",
    },
  ],
};

function writeContributions() {
  const dir = join(WORKSPACE, ".raiker", "plugins", PLUGIN_ID);
  const skill = join(dir, "skills", SKILL_NAME);
  mkdirSync(skill, { recursive: true });
  writeFileSync(join(skill, "SKILL.md"), SKILL_DOC, "utf-8");
  writeFileSync(join(dir, "mcp-servers.json"), JSON.stringify(MCP_OFFER, null, 2), "utf-8");
}

function removeContributions() {
  rmSync(join(WORKSPACE, ".raiker", "plugins", PLUGIN_ID), { recursive: true, force: true });
}

async function signIn(page: import("@playwright/test").Page) {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
  await page.getByLabel("Username").fill("Rahul");
  await page.getByLabel("Password", { exact: true }).fill("Ithink@10");
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill("Ithink@10");
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker", exact: true }).click();
  }
  // The Workbench greets a fresh instance and a returning owner differently
  // ("Welcome to your Work Dashboard" vs "Welcome back"), and a workspace turns
  // from the first into the second the moment it holds any work. Keying sign-in
  // to one of them makes a spec pass or fail on how much history the instance
  // happens to have, which is not what any of these tests are about.
  const workbench = page.getByRole("heading", { name: /Welcome (to your Work Dashboard|back)/ });
  await expect(
    page.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
  await expect(workbench.first()).toBeVisible({ timeout: 30_000 });
}

test.describe.configure({ mode: "serial" });

test.afterAll(() => removeContributions());

test("a plugin's skill arrives switched off and credited to it (BUG-221)", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);

  // Start from *absent*, proved rather than assumed. Visiting Skills with the
  // plugin directory gone runs the reconcile, which deletes any row a previous
  // run left behind — including one the owner had switched on, since the file
  // that authorised it is no longer there. Only then does the contribution
  // arriving mean what the test says it means.
  removeContributions();
  await page.goto(`${BASE}/#/extensions?tab=skills`);
  await expect(page.getByRole("heading", { name: "Skills" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(SKILL_NAME, { exact: true })).toHaveCount(0);
  // Let that reconcile *finish* before writing the files. Without this the write
  // races the in-flight request, and the test measures the interleaving rather
  // than the behaviour. (The reconcile keeps anything either of two overlapping
  // passes saw, so the race no longer loses a row — but a test that depends on
  // which request won is still a test about the wrong thing.)
  await page.waitForLoadState("networkidle");

  writeContributions();
  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  await page.goto(`${BASE}/#/extensions?tab=skills`);

  const row = page.getByText(SKILL_NAME, { exact: true }).locator("xpath=ancestor::li[1]");
  await expect(row).toBeVisible({ timeout: 30_000 });
  // Credited to the plugin by id — "a plugin" would not answer "which one".
  await expect(row.getByText("from plugin")).toBeVisible();
  await expect(row.getByText(`Provided by plugin ${PLUGIN_ID}`)).toBeVisible();
  // Offered, not running: installing was consent to offer, not to run with it.
  await expect(row.getByText("inactive", { exact: true })).toBeVisible();
  await expect(row.getByRole("button", { name: "Activate" })).toBeVisible();
  // The two controls the next reconcile would undo are not offered at all.
  await expect(row.getByRole("button", { name: "Rename" })).toHaveCount(0);
  await expect(row.getByRole("button", { name: "Delete" })).toHaveCount(0);
  // Reading exactly what it says stays possible.
  await expect(row.getByRole("button", { name: "Download" })).toBeVisible();

  await capture(page, `${SHOTS}/bug-221-plugin-skill-inactive.png`);
});

test("the owner can switch a contributed skill on, and it stays theirs", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto(`${BASE}/#/extensions?tab=skills`);

  const row = page.getByText(SKILL_NAME, { exact: true }).locator("xpath=ancestor::li[1]");
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByRole("button", { name: "Activate" }).click();
  await expect(row.getByText("active", { exact: true })).toBeVisible({ timeout: 15_000 });

  // Leaving and coming back re-runs the reconcile against the files on disk. The
  // owner's choice has to survive it — that is the property the store keeps and
  // the disk does not. Navigated inside the SPA rather than reloaded: the bearer
  // token is held in memory by design, so a hard reload is a sign-out, not a
  // refresh.
  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  await expect(page.getByRole("heading", { name: "Hooks", exact: true })).toBeVisible();
  await page.goto(`${BASE}/#/extensions?tab=skills`);
  const again = page.getByText(SKILL_NAME, { exact: true }).locator("xpath=ancestor::li[1]");
  await expect(again.getByText("active", { exact: true })).toBeVisible({ timeout: 30_000 });

  await again.getByRole("button", { name: "Deactivate" }).click();
  await expect(again.getByText("inactive", { exact: true })).toBeVisible({ timeout: 15_000 });
});

test("an offered MCP server is offered, not connected (BUG-221)", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto(`${BASE}/#/extensions?tab=mcp`);

  const offers = page
    .getByRole("heading", { name: "Offered by your plugins" })
    .locator("xpath=ancestor::section[1]");
  await expect(offers).toBeVisible({ timeout: 30_000 });
  await expect(offers.getByText(SERVER_NAME, { exact: true })).toBeVisible();
  await expect(offers.getByText(PLUGIN_ID)).toBeVisible();
  await expect(offers.getByText(/Nothing here is connected or reachable/i)).toBeVisible();
  // The token's *variable name*, never a token.
  await expect(offers.getByText("ACME_MCP_TOKEN")).toBeVisible();
  await expect(offers.getByRole("button", { name: "Add server" })).toBeVisible();

  await capture(page, `${SHOTS}/bug-221-plugin-mcp-offer.png`);
});

// The channel *contract* is asserted here because this spec is where BUG-225's
// step 1 was closed. Everything the surface does with it — pairing, enabling,
// the governed test delivery, the five conditions — belongs to the channel
// surface and is covered by `bug-225-channels-live.spec.ts`; duplicating it here
// would mean two places to update and two chances to update only one.
test("the channels tab states the contract (BUG-225 step 1)", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto(`${BASE}/#/extensions?tab=channels`);

  await expect(page.getByRole("heading", { name: "What a channel message is" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByText(/untrusted content with a named sender who is not you/i),
  ).toBeVisible();
  // An accepted spec and a shipped feature must still not read the same, so the
  // list of what is *not* built stays on the page beside what is.
  await expect(page.getByRole("heading", { name: "What is still not built" })).toBeVisible();

  await capture(page, `${SHOTS}/bug-225-channel-contract.png`);
});

test("the Plugins tab names all four kinds with three now available", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto(`${BASE}/#/extensions?tab=plugins`);

  const kinds = page
    .getByRole("heading", { name: "What a plugin may contribute" })
    .locator("xpath=ancestor::section[1]");
  await expect(kinds).toBeVisible({ timeout: 30_000 });
  for (const kind of ["Hooks", "Skills", "MCP servers"]) {
    await expect(kinds.getByText(kind, { exact: true }).locator("xpath=ancestor::li[1]")).toContainText(
      "Available",
    );
  }
  // Panels is the one kind left, and it still says so rather than being hidden.
  await expect(
    kinds.getByText("Panels", { exact: true }).locator("xpath=ancestor::li[1]"),
  ).toContainText("Not yet");

  await capture(page, `${SHOTS}/bug-221-contribution-kinds-three.png`);
});

test("revoking the plugin withdraws both the skill and the offer (BUG-221)", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);

  // Present first, so the disappearance below is a change rather than a state.
  await page.goto(`${BASE}/#/extensions?tab=skills`);
  await expect(page.getByText(SKILL_NAME, { exact: true })).toBeVisible({ timeout: 30_000 });

  // Revocation deletes the plugin's directory. Nothing annotates a record and
  // hopes the runtime agrees: the files are what both surfaces read.
  removeContributions();

  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  await page.goto(`${BASE}/#/extensions?tab=skills`);
  await expect(page.getByRole("heading", { name: "Skills" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(SKILL_NAME, { exact: true })).toHaveCount(0);

  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  await expect(page.getByRole("heading", { name: "MCP Servers" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Offered by your plugins" })).toHaveCount(0);

  // Put it back for the viewport captures that follow.
  writeContributions();
});

// Every viewport the app claims to support, on the two tabs this round changed.
for (const [label, viewport] of [
  ["mobile", { width: 390, height: 844 }],
  ["tablet", { width: 834, height: 1112 }],
  ["desktop", { width: 1440, height: 1000 }],
] as const) {
  test(`skills and MCP offers stay usable at ${label}`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.setViewportSize(viewport);
    await signIn(page);

    for (const tab of ["skills", "mcp"]) {
      await page.goto(`${BASE}/#/extensions?tab=${tab}`);
      await page.waitForTimeout(600);
      // Nothing may push the page sideways at any supported width.
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${tab} overflows horizontally at ${label}`).toBeLessThanOrEqual(1);
      // The selected tab has to be the one on screen (FIXED-257).
      const selected = page.locator('[role="tab"][aria-selected="true"]');
      await expect(selected).toBeInViewport();
    }

    await page.goto(`${BASE}/#/extensions?tab=skills`);
    await page.waitForTimeout(600);
    await capture(page, `${SHOTS}/bug-221-plugin-skill-${label}.png`);
  });
}
