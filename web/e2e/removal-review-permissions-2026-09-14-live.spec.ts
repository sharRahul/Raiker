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
import { LIVE_BASE as BASE } from "./live";

const SHOTS = "../../output/playwright/2026-09-14-permissions-overhaul";

// QUI-L06 (2026-10-21) replaced the stacked registry with a category rail, a
// list per category and one detail pane. The assertions below are the same
// REM-PERM rules on that layout: closed rows still state availability and
// behaviour, Git is still one group, the reference gates still decide nothing.
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
  const rail = page.getByRole("navigation", { name: "Permission categories" });
  await expect(rail).toBeVisible({ timeout: 60_000 });

  // One page title, in the top bar only.
  await expect(page.getByRole("heading", { level: 1, name: "Permissions" })).toHaveCount(1);

  // One posture sentence, and the rail's counts are the page's one filter.
  const main = page.getByRole("main");
  await expect(main.getByText(/^\d+ of \d+ permissions are available to Raiker on this account/)).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Permission status" })).toHaveCount(0);
  await expect(rail.getByRole("button", { name: /^Files \d+$/ })).toBeVisible();
  await capture(page, `${SHOTS}/permissions-overhauled.png`);

  // REM-PERM-03 — a closed row answers both questions; its detail explains
  // itself in one shape.
  await rail.getByRole("button", { name: /^Advanced/ }).click();
  const shellRow = page.getByRole("option", { name: /^Shell commands / }).first();
  await expect(shellRow).toHaveAccessibleName(/^Shell commands (On|Off) · (Ask me|Allow|Automatic|Never)$/);
  await shellRow.click();
  const shell = page.getByRole("article", { name: "Shell commands" });
  await expect(shell.getByRole("heading", { name: "Can Raiker use this?" })).toBeVisible();
  await expect(shell.getByRole("heading", { name: "When Raiker wants to use it" })).toBeVisible();
  await expect(shell.getByText(/Raiker (may|cannot) use this on this account/)).toBeVisible();
  await capture(page, `${SHOTS}/permissions-row-detail.png`, shell);

  // REM-PERM-01 — the read-only authority table is evidence, below the list
  // of controls it summarises.
  const list = page.getByRole("listbox", { name: "Advanced permissions" });
  const authority = page.getByText("How your permissions apply", { exact: true });
  const listBox = await list.boundingBox();
  const authorityBox = await authority.boundingBox();
  expect(authorityBox!.y).toBeGreaterThan(listBox!.y);
  await authority.click();
  await expect(page.getByRole("heading", { name: /Owner sets the boundary/ })).toBeVisible();

  // GEP-04 — the gates this page does not decide are read-only reference, with
  // no mode control and no selection box.
  const reference = page.locator("details.not-decided");
  await reference.locator("summary").click();
  await expect(reference.getByRole("group", { name: /when Raiker wants to use/i })).toHaveCount(0);
  await expect(reference.getByRole("checkbox")).toHaveCount(0);
  await expect(reference.getByText(/Governed elsewhere|No route yet/).first()).toBeVisible();
  await capture(page, `${SHOTS}/permissions-not-decided-here.png`, reference);

  // Git is one group, not three: a branch, a commit, a push and the account the
  // push authenticates to sit together under Git and GitHub (RU-06).
  await rail.getByRole("button", { name: /^Git and GitHub/ }).click();
  const files = page.getByRole("listbox", { name: "Git and GitHub permissions" });
  for (const label of ["Git writes", "Git push", "GitHub connector"]) {
    await expect(files.getByRole("option", { name: new RegExp(`^${label} `) })).toBeVisible();
  }
  await capture(page, `${SHOTS}/permissions-git-grouped.png`, files);
  // And nothing is left in a fallback bucket whose name means "nobody filed this".
  await expect(rail.getByRole("button", { name: /^Other tools/ })).toHaveCount(0);

  // Search filters the list.
  await page.getByRole("searchbox", { name: "Search permissions" }).fill("Git push");
  await expect(files.getByRole("option")).toHaveCount(1);

  // A phone width keeps the page reachable without a sideways scroll.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(rail).toBeVisible();
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
  // The backup caveat sits in the *Forgetting and backups* disclosure (QUI-L03).
  await kept.getByText("Forgetting and backups", { exact: true }).click();
  await expect(kept.getByText(/not from a backup already written/)).toBeVisible();

  const outbound = page.getByRole("region", { name: "What leaves this computer" });
  await expect(outbound).toBeVisible();
  // Availability is read from the same gate list Permissions reads, in the same
  // words — so the two pages cannot disagree about whether something can leave.
  await expect(
    outbound.getByText(/^(On|Off) · (Ask me|Allow|Automatic|Never)$/).first(),
  ).toBeVisible({ timeout: 30_000 });
  await expect(outbound.getByText(/as much of the conversation as the turn needs/).first()).toBeVisible();
  await capture(page, `${SHOTS}/privacy-inventory.png`);
});
