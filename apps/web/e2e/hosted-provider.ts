/**
 * The two steps every live spec has to take before it can drive a real turn,
 * in one place.
 *
 * Both used to be inlined in every spec, and both went stale under the product
 * beneath them:
 *
 * * **Where the provider cards are.** Splitting Models into tabs (FIXED-141)
 *   made **Local** the default tab, so `#/models` no longer renders a single
 *   `article.provider-card`. Eighteen live specs still navigated there and
 *   waited for a Connect button that was one tab away, so the whole live
 *   evidence suite failed on its first step.
 * * **The readiness gate.** Since FIXED-133 the composer's **Send** stays
 *   disabled until the *exact* model has a readiness check, so a spec that
 *   connected a provider, pinned a model and typed a prompt sat on a disabled
 *   button until it timed out.
 *
 * Keeping both here means the next change to either surface is one edit rather
 * than eighteen, and a spec that cannot connect fails saying so.
 */
import { expect, type Locator, type Page } from "@playwright/test";

/**
 * Complete the first-run model/privacy/backup wizard if it is up.
 *
 * A brand-new instance opens it over the workbench (FIXED-133), and it is
 * modal: a spec that signs in and goes straight to Models is talking to a page
 * it cannot reach. Skipping is the same choice the sheet offers a person who
 * already knows which provider they are about to connect.
 */
export async function dismissFirstRunModelSetup(page: Page): Promise<boolean> {
  const skip = page.getByRole("button", { name: "Skip for now" });
  if (await skip.isVisible().catch(() => false)) {
    await skip.click();
    await expect(skip).toBeHidden({ timeout: 30_000 });
    return true;
  }

  // FIXED-172 replaced the old one-click sheet with the five-stage setup
  // wizard. Live provider scenarios deliberately defer model selection here,
  // choose the hosted-compatible privacy posture, and defer backup; the model
  // itself is still connected through Models in the next step.
  const decideLater = page.getByRole("button", { name: "Decide later" });
  if (!(await decideLater.isVisible().catch(() => false))) return false;
  await decideLater.click();
  await page.getByRole("button", { name: "Balanced" }).click();
  await page.getByRole("button", { name: "Set up later" }).click();
  await page.getByRole("button", { name: "Open Workbench" }).click();
  await expect(page).toHaveURL(/#\/home$/, { timeout: 30_000 });
  await expect(decideLater).toBeHidden({ timeout: 30_000 });
  return true;
}

/**
 * The Models page, on the tab that actually holds the hosted provider cards.
 *
 * The sheet is re-asserted on every *load*, and skipping it during sign-in does
 * not survive one — so the first real navigation meets it again. Waiting for
 * "either the tab or the sheet" rather than polling for the sheet immediately
 * is what makes this deterministic: the sheet appears only once the bootstrap
 * reads have resolved, which is after `goto` returns.
 */
export async function openHostedProviders(page: Page, base: string): Promise<void> {
  const hosted = page.getByRole("tab", { name: "Hosted" });
  const skip = page.getByRole("button", { name: "Skip for now" });
  const decideLater = page.getByRole("button", { name: "Decide later" });
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await page.goto(`${base}/#/models?tab=hosted`);
    await expect(hosted.or(skip).or(decideLater).first()).toBeVisible({ timeout: 30_000 });
    if (!(await dismissFirstRunModelSetup(page))) break;
  }
  await expect(hosted).toBeVisible({ timeout: 30_000 });
}

/** One hosted provider's card, on the tab it lives on. */
export async function hostedProviderCard(
  page: Page,
  base: string,
  provider: string,
): Promise<Locator> {
  await openHostedProviders(page, base);
  const card = page.locator("article.provider-card").filter({ hasText: provider }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  return card;
}

/**
 * Enter a provider credential through the product's own dialog and confirm the
 * card says it connected.
 */
export async function connectHostedProvider(
  page: Page,
  base: string,
  provider: string,
  keyLabel: string,
  key: string,
): Promise<Locator> {
  const card = await hostedProviderCard(page, base, provider);
  // BUG-208 slice E moved Reconnect into Details — it is credential management,
  // not what the card is for. A provider with no connection still offers Connect
  // on the card, which is the path a fresh workspace takes.
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
  } else {
    await card.getByRole("button", { name: "Details", exact: true }).click();
    await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  }
  await page.getByLabel(keyLabel).fill(key);
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  // The Reconnect path opens **Model details** to reach the control, and saving
  // a credential does not close it — so a spec run against a workspace that
  // already had the provider connected left a modal over the card and every
  // later click hit the overlay instead. Close it here rather than in each
  // caller: the reconnect route is the one an already-configured workspace
  // always takes, so this is the common case, not the edge one.
  const detailsClose = page.getByRole("button", { name: "Close model details" });
  if (await detailsClose.isVisible().catch(() => false)) {
    await detailsClose.click();
    await expect(detailsClose).toBeHidden({ timeout: 30_000 });
  }
  return card;
}

/**
 * Run the readiness check for the model pinned on *card* and wait for it to
 * settle, so the composer will let a turn be sent.
 *
 * The check is the product's own **Test** control — the same one a person
 * clicks — rather than an API call the spec makes behind the page's back.
 */
export async function checkModelReady(page: Page, card: Locator): Promise<void> {
  await card.getByRole("button", { name: "Test", exact: true }).click();
  // The card states the outcome for the *pinned model*: reachable, or the exact
  // reason it is not. "Not checked" is the state before the check answers, so it
  // is deliberately not one of the accepted outcomes.
  await expect(
    card.getByText(/can reach|cannot execute|not reachable|rejected|no credit|no quota/i),
  ).toBeVisible({ timeout: 120_000 });
}

/** Connect a provider, pin an exact model, and leave it ready to answer a turn. */
export async function useHostedModel(
  page: Page,
  base: string,
  options: { provider: string; keyLabel: string; key: string; model: string },
): Promise<Locator> {
  const card = await connectHostedProvider(
    page,
    base,
    options.provider,
    options.keyLabel,
    options.key,
  );
  await card.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = card.getByLabel("Available models");
  await expect(catalogue).toBeVisible({ timeout: 60_000 });
  await catalogue.selectOption(options.model);
  await card.getByRole("button", { name: "Use model" }).click();
  await expect(card.locator("code")).toBeVisible({ timeout: 30_000 });
  // Reload before checking. **Test** probes the model the card was rendered
  // with, and the card the picker just closed still holds the profile as it was
  // before the pin — checking it there proves the provider answers, not that the
  // model the turn will use is ready.
  const pinned = await hostedProviderCard(page, base, options.provider);
  await checkModelReady(page, pinned);
  return pinned;
}

/**
 * Re-run the pinned model's readiness check.
 *
 * A readiness record expires (BUG-83 records the fixed five-minute TTL), and a
 * live spec routinely runs longer than that, so a scenario several minutes into
 * a suite can find **Send** disabled through no fault of its own. Calling this
 * at the top of a scenario that sends a turn keeps the spec measuring what it
 * is about rather than the clock.
 */
export async function refreshHostedReadiness(
  page: Page,
  base: string,
  provider: string,
): Promise<void> {
  const card = await hostedProviderCard(page, base, provider);
  await checkModelReady(page, card);
}
