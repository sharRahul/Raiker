/**
 * BUG-239 — Permissions says what an untouched switch actually means.
 *
 * FIXED-279 made the enforcing paths and the model's context bundle read one
 * table for "what does an empty gate table mean". It left the surface an owner
 * decides from reading its own: on a fresh account the page said **Off** about
 * `web_fetch` while `WebAccessService` would have fetched.
 *
 * Live rather than fixtured, because the whole claim is that the page and the
 * runtime now answer from the same read — which a fixture would assume rather
 * than test.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { openPermission, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = "../../docs/plans/screenshots/working";

test("an untouched gate says which of the three things it means", async ({ page }) => {
  test.setTimeout(180_000);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await signInAsOwner(page, BASE);

  // 2026-11-15 — Permissions is a category rail and a list-detail view
  // (QUI-L06); the card is the detail pane `openPermission` returns.
  const webFetch = await openPermission(page, BASE, "Web fetch");

  // It no longer claims Off about a capability the runtime would run, and it
  // says why rather than leaving it to be discovered from behaviour.
  await expect(webFetch.getByText(/On by default/).first()).toBeVisible();
  await expect(webFetch.getByText(/an empty table on a new install is not a refusal/i)).toBeVisible();
  // The only action it really has is the one it offers (FIXED-288).
  await expect(webFetch.getByRole("button", { name: "Turn off", exact: true })).toBeVisible();
  await expect(webFetch.getByRole("button", { name: "Turn on", exact: true })).toHaveCount(0);
  await capture(page, `${SHOTS}/bug-239-unset-gate-honesty.png`, webFetch);

  // A capability whose empty table really does mean off is untouched by this.
  const shell = await openPermission(page, BASE, "Shell commands");
  await expect(shell.getByText(/On by default/)).toHaveCount(0);
  await expect(shell.getByRole("button", { name: "Turn on", exact: true })).toBeVisible();

  expect(consoleErrors).toEqual([]);
});
