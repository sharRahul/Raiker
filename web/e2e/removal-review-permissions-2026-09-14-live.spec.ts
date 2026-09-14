/**
 * The 2026-09-14 Permissions overhaul and the §18.3 rows that closed with it,
 * against a running host.
 *
 * The Permissions page is the one an owner decides from, so its evidence is
 * live rather than fixtured: a page that reads the gate table correctly under a
 * stub and incorrectly against the runtime has proved nothing about the product.
 *
 * Covered here:
 *
 * * **The overhaul.** One page title, one posture summary that is also the one
 *   status filter, the actionable sections above the registry, and the read-only
 *   authority table below all of them rather than above the controls it
 *   summarises (REM-PERM-01).
 * * **REM-PERM-03** — a row states availability and behaviour without being
 *   opened, and the explanation lives in the row's own detail.
 * * **REM-LAUNCH-01** — first run says what it did rather than that the
 *   instance is ready, when the model was deferred. (Asserted on a first-run
 *   workspace by `first-launch-live.spec.ts`; this file asserts the sign-in
 *   path still completes setup either way.)
 * * **REM-MCP-01/02** — the sample server is a developer example below the
 *   list, described by its scope rather than called safe.
 * * **REM-SET-PRIVACY** — Privacy is an inventory of what is kept and what can
 *   leave, reading availability in the Permissions vocabulary.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = "../../docs/screenshots/2026-09-14-permissions-overhaul";

test("Permissions leads with posture and actions, and keeps the table as evidence", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/capabilities`);

  const registry = page.getByRole("region", { name: "All permissions" });
  await expect(registry).toBeVisible({ timeout: 60_000 });

  // One page title. This view carried a second `<h1>` reading "Permissions"
  // directly under the one in the top bar — the only view in the product that
  // did, and the first thing that made the page look unfinished.
  await expect(page.getByRole("heading", { level: 1, name: "Permissions" })).toHaveCount(1);

  // One posture summary, and the counts under it are the page's one status
  // filter rather than four page-width tiles plus a select further down.
  const posture = page.getByRole("region", { name: "Permission posture" });
  await expect(posture).toBeVisible();
  await expect(posture.getByText(/permissions are available to Raiker on this account/)).toBeVisible();
  const status = page.getByRole("group", { name: "Filter permissions by status" });
  await expect(status.getByRole("button", { name: /All/ })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Permission status" })).toHaveCount(0);
  await capture(page, `${SHOTS}/permissions-overhauled.png`);

  // REM-PERM-01 — the read-only authority table is evidence, and reads after
  // the controls it summarises rather than above them.
  const authority = page.locator("details.authority-disclosure");
  await expect(authority).toBeVisible();
  const registryBox = await registry.boundingBox();
  const authorityBox = await authority.boundingBox();
  expect(authorityBox!.y).toBeGreaterThan(registryBox!.y);
  await authority.getByText("How your permissions apply").click();
  await expect(page.getByRole("heading", { name: /Owner sets the boundary/ })).toBeVisible();
  await capture(page, `${SHOTS}/permissions-authority-below.png`, authority);

  // REM-PERM-03 — the row answers both questions closed, and explains itself
  // open, in one shape rather than four stacked paragraphs.
  const shell = registry.locator(".cap.card").filter({ hasText: "Shell commands" }).first();
  await expect(shell.locator(".cap-summary")).toHaveText(/^(On|Off) · (Ask me|Allow|Automatic|Never)$/);
  await shell.locator("button.cap-toggle").click();
  await expect(shell.getByText("Can Raiker use this?")).toBeVisible();
  await expect(shell.getByText("When Raiker wants to use it")).toBeVisible();
  await expect(shell.getByText(/Raiker (may|cannot) use this on this account/)).toBeVisible();
  await capture(page, `${SHOTS}/permissions-row-detail.png`, shell);

  // Git is one group, not three. A branch, a commit, a push and the account the
  // push authenticates to were filed under Workspace, Network and Connectors.
  const git = registry.locator(".cap-list").filter({ hasText: "GIT" }).first();
  for (const label of ["Git writes", "Git push", "GitHub connector"]) {
    await expect(git.getByText(label, { exact: true })).toBeVisible();
  }
  await capture(page, `${SHOTS}/permissions-git-grouped.png`, git);

  // And nothing is left in the fallback bucket, whose name means "nobody filed
  // this": both execution destinations have a real home.
  await expect(registry.getByText("OTHER TOOLS")).toHaveCount(0);

  // GEP-04's second answer: the gates this page does not decide are read-only
  // reference, with no mode control and no selection box.
  const reference = page.locator("details.not-decided");
  await expect(reference).toBeVisible();
  await reference.getByText("Not decided here").click();
  await expect(reference.getByText("Container execution", { exact: true })).toBeVisible();
  await expect(reference.getByText("Processes", { exact: true })).toBeVisible();
  await expect(reference.getByRole("group", { name: /when Raiker wants to use/i })).toHaveCount(0);
  await expect(reference.getByRole("checkbox")).toHaveCount(0);
  // Every one of them names what really governs it, or why nothing runs.
  await expect(reference.getByText(/Governed elsewhere/).first()).toBeVisible();
  await expect(reference.getByText(/No route yet/).first()).toBeVisible();
  await capture(page, `${SHOTS}/permissions-not-decided-here.png`, reference);

  // The filter chips really filter, and the count line follows them.
  await status.getByRole("button", { name: /Available/ }).click();
  await expect(registry.getByText(/^Showing \d+ of \d+ permissions$/)).toBeVisible();

  // And the phone width keeps the whole page reachable without a sideways
  // scroll, which is where fifty-one rows of four buttons would show it first.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(registry).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
  await capture(page, `${SHOTS}/permissions-overhauled-390.png`);

  expect(consoleErrors).toEqual([]);
});

test("the MCP sample is a developer example described by its scope (REM-MCP-01/02)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  // The tab mounts inside the Extensions hub, whose own heading names it.
  await expect(page.locator("details.example")).toBeVisible({ timeout: 60_000 });

  // It no longer leads the page: the name field and template picker are inside
  // a closed disclosure below the list.
  await expect(page.getByLabel("Server name")).toBeHidden();
  const example = page.locator("details.example");
  await example.getByText("Developer example").click();

  // REM-MCP-02 — the reviewed scope, not the word "safe".
  await expect(page.getByText(/opens no socket, writes no file and runs no shell/)).toBeVisible();
  await expect(page.getByText(/safe starter/i)).toHaveCount(0);
  await expect(page.getByLabel("Server name")).toBeVisible();
  await capture(page, `${SHOTS}/mcp-developer-example.png`, example);
});

test("Privacy is an inventory of what is kept and what can leave (REM-SET-PRIVACY)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=privacy`);

  const kept = page.getByRole("region", { name: "Kept on this machine" });
  await expect(kept).toBeVisible({ timeout: 60_000 });
  await expect(kept.getByRole("link", { name: "Memory" })).toHaveAttribute("href", "#/memory");
  await expect(kept.getByText(/not from a backup already written/)).toBeVisible();

  const outbound = page.getByRole("region", { name: "What can leave this machine" });
  await expect(outbound).toBeVisible();
  // Availability is read from the same gate list Permissions reads, in the same
  // words — so the two pages cannot disagree about whether something can leave.
  await expect(
    outbound.getByText(/^(On|Off) · (Ask me|Allow|Automatic|Never)$/).first(),
  ).toBeVisible({ timeout: 30_000 });
  await expect(outbound.getByText(/as much of the conversation as the turn needs/)).toBeVisible();
  await capture(page, `${SHOTS}/privacy-inventory.png`);
});
