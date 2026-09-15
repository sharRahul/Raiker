/**
 * The two ends of a remembered catalogue, and what a composer says in between.
 *
 * Raiker remembers what a provider last published so a brief outage
 * does not empty every picker. That is right, and it leaves two things to get
 * right at the edges:
 *
 * * **Disconnecting is not an outage.** Removing a credential has to take that
 *   account's models with it, or every picker keeps offering a list Raiker can
 *   no longer reach, drawn exactly like one it can.
 * * **A reachable catalogue is not a chosen model.** With a provider connected
 *   and its whole catalogue selectable, the composer still read *No model is set
 *   up. Open Models to connect a provider* — an instruction to do something the
 *   owner had already done.
 *
 * Needs a real credential; skips with the reason when the round has none.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import {
  connectHostedProvider,
  hostedProviderCard,
  openProviderDetails,
  signInAsOwner,
} from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

const SHOTS = "../../docs/screenshots/2026-09-12-catalogue-lifecycle";

test.describe.configure({ mode: "serial" });

test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");

test("a connected provider's catalogue reaches the composer, unswitched", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);

  const card = await hostedProviderCard(page, BASE, "Anthropic");
  if (!(await card.getByText("Connection saved").isVisible().catch(() => false))) {
    await connectHostedProvider(page, BASE, "Anthropic", "Anthropic API key", KEY);
  }

  // Listing is what writes the catalogue. Nothing below switches a model on.
  const listed = await page.evaluate(async () => {
    const response = await fetch("/api/models/anthropic-hosted/provider-models", {
      credentials: "same-origin",
    });
    return (await response.json()) as { status: string; models: string[] };
  });
  test.skip(
    listed.status !== "available" || listed.models.length === 0,
    `The provider answered "${listed.status}", so there is no catalogue to carry.`,
  );

  const served = await page.evaluate(async () => {
    const response = await fetch("/api/models", { credentials: "same-origin" });
    return (await response.json()) as { catalogues?: Record<string, string[]> };
  });
  expect(served.catalogues?.["anthropic-hosted"] ?? []).toEqual(listed.models);

  // The composer is the surface that has to agree.
  await page.goto(`${BASE}/#/new-chat`);
  await page.getByLabel("Prompt").waitFor({ timeout: 60_000 });

  // With models reachable and none chosen, the composer names the missing
  // choice rather than sending the owner back to connect a provider.
  await expect(page.getByText("No model is chosen.")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Open Models to connect a provider/)).toHaveCount(0);

  await page.getByRole("button", { name: /Model for this turn/ }).click();
  const menu = page.getByRole("menu", { name: "Models" });
  await expect(menu).toBeVisible({ timeout: 30_000 });
  const search = menu.getByLabel(/Search models/);
  await expect(search).toBeVisible({ timeout: 30_000 });
  // Search reaches the whole catalogue, which is what replaced curation.
  await search.fill(listed.models[listed.models.length - 1]);
  await expect(menu.getByRole("menuitemradio").first()).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/composer-search-reaches-catalogue.png`, menu);
});

test("disconnecting a provider takes its models with it", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);

  const before = await page.evaluate(async () => {
    const response = await fetch("/api/models", { credentials: "same-origin" });
    return (await response.json()) as { catalogues?: Record<string, string[]> };
  });
  test.skip(
    (before.catalogues?.["anthropic-hosted"] ?? []).length === 0,
    "No remembered Anthropic catalogue to disconnect.",
  );

  // Through the product's own control, not a direct store write: Details lives
  // in the row's overflow, beside Test connection.
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  await openProviderDetails(page, card);
  // Scoped to the dialog and matched loosely: the control's accessible name
  // carries the provider, and a bare exact match finds nothing.
  const details = page.getByRole("dialog");
  const disconnect = details.getByRole("button", { name: /Disconnect/ }).first();
  await expect(disconnect).toBeVisible({ timeout: 30_000 });
  // Disconnecting asks `window.confirm` first, which Playwright dismisses by
  // default — so without this the click is a no-op and the assertion below
  // reads as the catalogue refusing to clear rather than as a disconnect that
  // never happened.
  page.once("dialog", (dialog) => void dialog.accept());
  await disconnect.click();

  await expect
    .poll(
      async () =>
        (
          await page.evaluate(async () => {
            const response = await fetch("/api/models", { credentials: "same-origin" });
            return (await response.json()) as { catalogues?: Record<string, string[]> };
          })
        ).catalogues?.["anthropic-hosted"]?.length ?? 0,
      { timeout: 30_000 },
    )
    .toBe(0);
});
