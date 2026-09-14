/**
 * Connecting the round's supplied Anthropic key, through the UI, and reading
 * what Raiker says about it.
 *
 * **BUG-291 — this spec used to assert a refusal.** The key supplied for the
 * 2026-09-05 round was *identity-linked*: it authenticated only with the id of
 * the workspace it acts inside, and the spec asserted that the model dialog said
 * so. That was a true and useful thing to check, and it was checking it in the
 * wrong place — it encoded a property of one *credential* as though it were a
 * property of the *product*. The next round's key authenticated normally,
 * `/v1/models` answered 200 with eleven models, and the spec spent ninety
 * seconds waiting for a refusal that was not coming.
 *
 * Raiker's half — that an identity-linked refusal is classified and stated in
 * words beside the field that fixes it — is asserted against a stubbed provider
 * response in `ModelsView.test.ts`, where it can be produced on demand.
 *
 * What is left here is what only a live key can prove: the key goes in through
 * the UI, the connection saves, and the provider publishes a catalogue Raiker
 * can offer. It passes against a working key. Against an identity-linked one it
 * **says which it is looking at** and stops, rather than failing as though the
 * product were broken — the credential is the limit, and that is BUG-273.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import {
  hostedProviderCard,
  openModelDialog,
  signInAsOwner,
} from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");

test("a supplied Anthropic key connects through the UI and publishes its catalogue", async ({ page }) => {
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
    // cost the owner their credential. The answer arrives at the first call.
    await expect(page.getByRole("dialog", { name: "Connect to Anthropic" })).toBeHidden({
      timeout: 30_000,
    });
  }
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 30_000 });

  // Listing this provider's models is that first call. `openModelDialog` waits
  // for the catalogue request to finish rather than for the dialog to mount
  // (BUG-295), so what is on screen below is the provider's real answer.
  const dialog = await openModelDialog(page, card);

  // Whatever the answer is, it is stated in words. A bare status is the defect
  // FIXED-370 closed, "go and get another key" is the dead end FIXED-372
  // closed, and "Provider unreachable" — about a provider that answered in
  // full — is the one the 2026-09-05 round found in the picker.
  await expect(dialog.getByText(/Provider unreachable/i)).toHaveCount(0);

  const identityLinked = await dialog
    .getByText(/identity-linked/i)
    .isVisible()
    .catch(() => false);
  await capture(page, "../../docs/plans/screenshots/working/anthropic-key-catalogue.png");

  if (identityLinked) {
    // Named, not swallowed. This is the credential's limit rather than the
    // product's, the refusal is classified and carries the field that fixes it,
    // and a provider turn needs a key that authenticates — BUG-273.
    test.skip(
      true,
      "This Anthropic key is identity-linked: it authenticates only with the id " +
        "of the workspace it acts inside. Raiker classified the refusal and " +
        "offered the Workspace ID field; a catalogue needs a key that " +
        "authenticates on its own.",
    );
    return;
  }

  // A working key. The catalogue is the thing only a live round can show.
  await expect(dialog.locator('input[type="checkbox"]').first()).toBeAttached({
    timeout: 60_000,
  });
});
