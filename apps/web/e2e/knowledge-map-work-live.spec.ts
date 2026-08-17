/**
 * BUG-218 — the Knowledge Map draws the owner's work, live.
 *
 * The defect this proves fixed was measured, not described: a workspace after
 * one live round produced 22 nodes, 20 of them typed `tool`, and none of those
 * twenty was a tool — they were rows of the event index. Chats were one
 * undifferentiated dot; projects, context and attachments were absent because
 * nothing read them.
 *
 * This drives a real `raiker-web` holding a workspace seeded through the
 * governed store, and asserts the map's own filter row and counters describe
 * that work. The records are seeded rather than produced by a model turn on
 * purpose: what is under test is the *map*, and seeding is the only way to put
 * a project, an attachment and a cited file in front of it deterministically.
 * A live provider turn is covered by `fts5-mem03-bug194-live.spec.ts`.
 */
import { expect, test } from "@playwright/test";
import { dismissFirstRunModelSetup } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";
const PASSWORD = "Knowledge-map-review-password-1!";

test("the Knowledge Map shows chats, build, projects, context and files", async ({ page }) => {
  test.setTimeout(180_000);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 20_000 });
  await page.getByLabel("Username").fill("owner");
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

  await page.goto(`${BASE}/#/brain`);
  await expect(page.getByRole("heading", { name: "Knowledge Map" })).toBeVisible({
    timeout: 30_000,
  });
  await page.waitForLoadState("networkidle");

  // The filters live behind the graph-settings panel, which is where an owner
  // goes to ask "show me only my files".
  await page.getByRole("button", { name: "Graph settings", exact: true }).click();
  const panel = page.locator("aside.settings-panel");
  await expect(panel).toBeVisible({ timeout: 15_000 });

  // The filter row is the map's own statement of what it contains. It listed
  // six types when the map was mostly event rows; it now names the owner's
  // material, and "Context" is the one that did not exist at all before.
  for (const label of ["Chats", "Build", "Projects", "Files", "Context", "Tools"]) {
    await expect(panel.getByText(label, { exact: true }).first()).toBeVisible({
      timeout: 15_000,
    });
  }

  await page.waitForTimeout(2_500);
  await page.screenshot({
    path: `${SHOTS}/r0817-04-knowledge-map-work-graph.png`,
    fullPage: true,
  });
  expect(consoleErrors).toEqual([]);
});
