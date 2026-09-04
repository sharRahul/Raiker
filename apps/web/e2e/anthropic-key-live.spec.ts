/**
 * Connecting the round's supplied Anthropic key, through the UI, and reading
 * what Raiker says about it.
 *
 * The key supplied for this round is **identity-linked**: it authenticates only
 * with the id of the workspace it acts inside. FIXED-370 stopped that being
 * reported as a bare HTTP status; FIXED-372 gave the connection a Workspace ID
 * field so the owner has somewhere to put the answer. What neither can supply is
 * the id itself, which only the key's owner has — and the key cannot be asked
 * for it: `/v1/organizations/*` answers a key of this kind with 403.
 *
 * So this spec proves the half that is Raiker's: the refusal is classified, it
 * is stated in words the owner can act on, and the field that would fix it is on
 * the screen. It is deliberately not a provider turn — that is BUG-273, and it
 * stays open until a key that authenticates is supplied.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { hostedProviderCard, signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");

test("an identity-linked key is refused in words, beside the field that fixes it", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);

  const card = await hostedProviderCard(page, BASE, "Anthropic");
  // Idempotent: a workspace that already holds this key from an earlier run
  // shows no Connect button, and re-entering it would prove nothing new.
  const connect = card.getByRole("button", { name: /^(Connect|Reconnect)$/ });
  if (await connect.count()) {
    await connect.first().click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    await page.locator(".signin-connect").click();
    // Storing a key is not using one: the connection saves without a round
    // trip, which is right — a provider that is briefly unreachable should not
    // cost the owner their credential. The refusal arrives at the first call.
    await expect(page.getByRole("dialog", { name: "Connect to Anthropic" })).toBeHidden({
      timeout: 30_000,
    });
  }
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 30_000 });

  // Listing this provider's models is that first call.
  await card.getByRole("button", { name: /Select models|Choose model|Change model/ }).click();

  // Whatever comes back, it is stated in words. A bare status is the defect
  // FIXED-370 closed, "go and get another key" is the dead end FIXED-372
  // closed, and "Provider unreachable" — about a provider that answered in
  // full — is the one this round found in the picker. So the answer names the
  // workspace id, which is the thing the owner can actually act on.
  const dialog = page.getByRole("dialog", { name: /models/i });
  await expect(dialog).toBeVisible({ timeout: 60_000 });
  await expect(dialog.getByText(/identity-linked/i)).toBeVisible({ timeout: 90_000 });
  await expect(dialog.getByText(/Provider unreachable/i)).toHaveCount(0);

  await capture(page, "../../docs/plans/screenshots/working/anthropic-identity-linked-key.png");
});
