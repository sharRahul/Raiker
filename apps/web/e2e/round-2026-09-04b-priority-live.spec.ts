/**
 * The second 2026-09-04 round, exercised against a running host.
 *
 * Unit tests prove each mechanism. This proves the *product*: what an owner
 * does, on the surface they do it on, and what the screen says afterwards. Each
 * block is written so it can fail for exactly one reason.
 *
 * Two of the three items below were found by running the product rather than by
 * reading it, which is the whole argument for this file existing:
 *
 * * **BUG-277** was found on the first press of **Test** with the round's
 *   supplied key. Raiker said the provider could not be reached; the provider
 *   had answered in full.
 * * **BUG-278** was found in a page capture: twenty-six connector rows reading
 *   "installed connected enabled usable" under a card saying none of them was.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { enableCapability, hostedProviderCard, signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

// Deliberately not serial. The three blocks share a host but touch different
// surfaces, and a failure in one is not a reason to leave the other two unrun —
// which is exactly what happened on this file's first execution.

test("a collector states the cadence it is delivered on (BUG-276)", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);

  // A delivery leaves the machine, so it answers to `telemetry_export` — a Tier
  // 2 capability with a threat-model acknowledgement and a confirmation token.
  //
  // Turned on unconditionally rather than "only if the page says it is off".
  // Both of this file's first two executions failed on exactly that condition:
  // the section reads its gate in `onMount`, so a check made after
  // `waitForLoadState("networkidle")` can run before the answer arrives, read no
  // blocking notice, and skip the turn-on. `enableCapability` is idempotent, so
  // asking for a state is deterministic where asking about one is not.
  await enableCapability(page, BASE, "Telemetry export", "Live validation of the delivery cadence");

  await page.goto(`${BASE}/#/observe?tab=overview`);
  await page.waitForLoadState("networkidle");

  if ((await page.getByText("Cadence collector", { exact: true }).count()) === 0) {
    await page.getByRole("button", { name: /Add collector/ }).click();
    await page.getByLabel("Name").fill("Cadence collector");
    await page.getByLabel("OTLP endpoint").fill("http://127.0.0.1:4318");
    await page.getByRole("button", { name: /^Add collector$/ }).click();
    await expect(page.getByText("Cadence collector", { exact: true })).toBeVisible({
      timeout: 30_000,
    });
  }

  // The interface outcome BUG-276 names: a destination either states the cadence
  // it is delivered on, or states that it is delivered only on demand. A card
  // that says neither would let an owner believe events are flowing while
  // nothing has run since they last pressed the button.
  const cadence = page.getByLabel(/Delivery cadence for Cadence collector/);
  await expect(cadence).toBeVisible({ timeout: 30_000 });
  await expect(cadence).toHaveValue("off");
  // "On demand only" is a sentence, not a blank — the shipped default says what
  // it is rather than leaving the field empty.
  await expect(cadence.locator("option:checked")).toHaveText("On demand only");
  // Nothing is claimed about a next run while there is no cadence.
  await expect(page.getByText(/^Next /)).toHaveCount(0);

  await cadence.selectOption("hourly");
  // Armed, and the card says when — read back off the server rather than off the
  // select, so a cadence the host will not run cannot be shown as one it will.
  await expect(page.getByText(/^Next /)).toBeVisible({ timeout: 30_000 });
  await capture(page, "../../docs/plans/screenshots/working/bug-276-delivery-cadence.png");

  // And off again clears the claim rather than leaving one in the queue.
  await cadence.selectOption("off");
  await expect(page.getByText(/^Next /)).toHaveCount(0);
});

test("an identity-linked key is answered with the repair, not the network (BUG-277)", async ({
  page,
}) => {
  test.setTimeout(240_000);
  test.skip(
    ANTHROPIC_KEY === "",
    "Set RAIKER_LIVE_ANTHROPIC_KEY to an identity-linked key — the refusal is the point.",
  );
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");

  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
  } else {
    await card.getByRole("button", { name: "Details", exact: true }).click();
    await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  }
  await page.getByLabel(/API key/i).first().fill(ANTHROPIC_KEY);
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });

  await card.getByRole("button", { name: "Test", exact: true }).click();
  const result = card.locator("[data-test-result]");
  await expect(result).toBeVisible({ timeout: 120_000 });

  // What this round found: the provider answered "This API key is not scoped to
  // a workspace…", none of the three literals the classifier matched appeared in
  // it, and the owner was told to check that Anthropic was "running and
  // reachable from this device". The network was fine.
  await expect(result).not.toContainText(/could not be reached/i);
  await expect(result).not.toContainText(/reachable from this device/i);
  await expect(result).toContainText(/identity-linked/i);
  await expect(result).toContainText(/workspace ID/i);
  await capture(page, "../../docs/plans/screenshots/working/bug-277-workspace-repair-live.png");
});

test("a connector row cannot be read as installed when it is not (BUG-278)", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/extensions?tab=connectors`);
  await page.waitForLoadState("networkidle");

  const rows = page.locator(".extension-row");
  await expect(rows.first()).toBeVisible({ timeout: 60_000 });

  // The counters and the rows have to agree. Whichever way this workspace
  // stands, a row's four conditions carry a marker that is not a colour — so a
  // greyscale display, or a colour-blind owner, reads the same thing the
  // counters say.
  const first = rows.first();
  const facts = first.locator(".fact");
  await expect(facts).toHaveCount(4);
  for (let index = 0; index < 4; index += 1) {
    const text = ((await facts.nth(index).textContent()) ?? "").trim();
    // Every pill starts with one of the two markers, so "installed" never
    // appears on screen without something saying whether it is.
    expect(text.startsWith("✓") || text.startsWith("○")).toBe(true);
  }

  // And the screen-reader text says which, in words rather than in a glyph.
  await expect(first.getByText(/^: (yes|no)$/).first()).toHaveCount(1);
  await capture(page, "../../docs/plans/screenshots/working/bug-278-connector-facts.png");
});
