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
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";
const CREDENTIALS = { user: "owner", password: "Survey-password-1!" };

test("an untouched gate says which of the three things it means", async ({ page }) => {
  test.setTimeout(180_000);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await signInAsOwner(page, BASE, CREDENTIALS);
  await page.goto(`${BASE}/#/capabilities`);

  const webFetch = page.locator(".cap.card", { hasText: "Web fetch" }).first();
  await expect(webFetch).toBeVisible({ timeout: 30_000 });

  // The row, before anything is opened: it no longer claims Off about a
  // capability the runtime would run.
  await expect(webFetch.getByText("On by default")).toBeVisible();
  await expect(webFetch.getByText("Off", { exact: true })).toHaveCount(0);

  // And the card says why, rather than leaving it to be discovered from
  // behaviour.
  await webFetch.getByRole("button", { name: /Web fetch/ }).click();
  await expect(page.getByText(/an empty table on a new install is not a refusal/i))
    .toBeVisible();
  // And the only action it really has is the one it offers. Turning a running
  // capability "on" is the FIXED-288 contradiction the other way round.
  await expect(webFetch.getByRole("button", { name: "Turn off" })).toBeVisible();
  await expect(webFetch.getByRole("button", { name: "Turn on" })).toHaveCount(0);
  await capture(page, `${SHOTS}/bug-239-unset-gate-honesty.png`, webFetch);

  // A capability whose empty table really does mean off is untouched by this.
  const shell = page.locator(".cap.card", { hasText: "Shell commands" }).first();
  await expect(shell.getByText("Off", { exact: true })).toBeVisible();
  await expect(shell.getByText("On by default")).toHaveCount(0);

  expect(consoleErrors).toEqual([]);
});
