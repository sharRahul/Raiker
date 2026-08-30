/**
 * MEM-14 / FIXED-236 — an unresolved reference is drawn, not dropped.
 *
 * The Knowledge Map used to draw a cited file that no longer exists exactly
 * like one still on disk, so a conversation grounded in something since deleted
 * looked identically grounded in something present. Obsidian keeps its
 * `unresolvedLinks` for the same reason this does: the more useful fact is that
 * the work rested on something that is gone.
 *
 * The citation rows are seeded rather than produced by a model turn, and
 * deliberately: the case needs a file to have been read *and then deleted*,
 * which is a sequence, not a prompt. A live provider turn is covered by
 * `fts5-mem03-bug194-live.spec.ts`. The seeding runs against the real running
 * host through the governed store, after the browser has created the account —
 * the citation rows are owner-scoped and there is no honest way to know that
 * principal in advance.
 */
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { dismissFirstRunModelSetup, OWNER_CREDENTIALS } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";
const PASSWORD = OWNER_CREDENTIALS.password;
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";

test("a cited file that no longer exists is drawn as Missing", async ({ page }) => {
  test.setTimeout(180_000);
  test.skip(!WORKSPACE, "RAIKER_LIVE_WORKSPACE is not set for this run");
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 20_000 });
  await page.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /Sign in|Unlock/ }).click();
  }
  await expect(
    page
      .getByRole("button", { name: "Decide later" })
      .or(page.getByRole("heading", { name: "Welcome to your Work Dashboard" }))
      .first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);

  // Now that the owner exists, plant the pair: one cited file still on disk,
  // one cited file deleted since.
  const seeded = execFileSync(
    "python",
    [fileURLToPath(new URL("./seed_reference_graph.py", import.meta.url)), WORKSPACE],
    { encoding: "utf8" },
  );
  expect(seeded).toContain("seeded");

  await page.goto(`${BASE}/#/brain`);
  await expect(page.getByRole("heading", { name: "Knowledge Map" })).toBeVisible({
    timeout: 30_000,
  });
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(2_500);

  // The map's own search is the surface an owner would use to ask this, and it
  // is the reason `missing` is a status rather than a colour: `status:` is a
  // supported filter, so the state is queryable and not only visible.
  const search = page.getByLabel("Search records");
  await search.fill("status:missing");
  await page.waitForTimeout(1_500);

  // One node matches, and it is the file that is gone.
  const dashed = page.locator("circle.node-circle.unresolved");
  await expect(dashed.first()).toBeVisible({ timeout: 15_000 });
  await expect(dashed).toHaveCount(1);

  // Selected while the filter still holds it alone on the stage: the force
  // layout is live, and a node in a settling simulation never reports stable
  // enough to click. This is a property of the graph view, not of the fix.
  await dashed.first().click();

  // The inspector says it in words. A dashed outline alone would be a hint;
  // "Missing" is the claim, and it names the file rather than a node id.
  const inspector = page.locator(".inspector").first();
  await expect(inspector.getByText("Missing", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    inspector.getByRole("heading", { name: "docs/retired-playbook.md" }),
  ).toBeVisible();

  // Back to the whole map for the photograph: both cited files are drawn, and
  // only one of them is hollow. That contrast is the fix — before it, these two
  // were drawn identically.
  await search.fill("");
  await page.waitForTimeout(2_500);
  await expect(page.locator("circle.node-circle.unresolved")).toHaveCount(1);
  await expect(
    page.locator("circle.node-circle:not(.unresolved)").first(),
  ).toBeVisible();

  await capture(page, `${SHOTS}/r0817-05-knowledge-map-unresolved-reference.png`);
  expect(consoleErrors).toEqual([]);
});
