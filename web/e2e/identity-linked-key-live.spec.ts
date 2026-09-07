/**
 * BUG-274 — an identity-linked key acts inside one workspace, and Raiker can
 * now name it.
 *
 * [FIXED-370](../../../docs/plans/FIXED_ITEMS.md) classified the refusal and
 * left the owner a dead end: *"use a standard API key from the provider's
 * console"*, which is no repair at all for an owner who has only this key. The
 * remediation now names a field the product has, and the field is where the
 * remediation says it is.
 *
 * This runs against a real provider answer. `RAIKER_LIVE_ANTHROPIC_KEY` must be
 * an **identity-linked** key — the whole point is the refusal — and the spec
 * skips itself when the variable is unset, so it neither fails CI nor claims a
 * scenario it did not run.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { hostedProviderCard, signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

test.skip(KEY === "", "Set RAIKER_LIVE_ANTHROPIC_KEY to an identity-linked key.");

test("an identity-linked key is answered with the field that fixes it", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");

  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
  } else {
    await card.getByRole("button", { name: "Details", exact: true }).click();
    await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  }

  // The field is behind Advanced, because most keys need nothing there.
  await expect(page.getByLabel(/Workspace ID/i)).toBeHidden();
  await page.getByLabel(/API key/i).first().fill(KEY);
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });

  // Saving contacts nothing — it stores a credential. The provider is asked by
  // the readiness check, which is where the refusal actually arrives and where
  // the owner is standing when they meet it.
  await card.getByRole("button", { name: "Test", exact: true }).click();
  const result = card.locator("[data-test-result]");
  await expect(result).toBeVisible({ timeout: 120_000 });

  // The answer is a repair, not a status code and not a different key to go and
  // find. "Update the key" would be wrong: the key is fine.
  await expect(result).toContainText(/identity-linked/i);
  await expect(result).toContainText(/workspace ID/i);
  await expect(result).not.toContainText(/standard .*API key/i);
  await capture(page, "../../docs/plans/screenshots/working/bug-274-workspace-answer-live.png", result);

  // And the remediation names a field the owner can reach from where they read
  // it, opened on the section that holds it.
  await result.getByRole("button", { name: "Add workspace ID" }).click();
  await expect(page.getByLabel(/Workspace ID/i)).toBeVisible();
  await capture(page, "../../docs/plans/screenshots/working/bug-274-workspace-field-live.png");

  // A value that could never be an HTTP header is refused before it is stored.
  await page.getByLabel(/Workspace ID/i).fill("wrkspc_1\nx-admin: yes");
  await page.locator(".signin-connect").click();
  await expect(page.locator(".signin-guidance, .error")).toBeVisible({ timeout: 30_000 });
});
