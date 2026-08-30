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
  //
  // The model stage's own controls arrive with `GET /api/setup`, and the stage
  // now carries a provider row per backend which it populates afterwards. A
  // sampled `isVisible()` therefore returned false on a wizard that was simply
  // still loading, and the caller went on to assert against a screen it had not
  // actually left. The wizard is *waited for* rather than sampled, and a run that
  // was never on it says so by the wait expiring.
  //
  // "Continue" is the same button once a model has been pinned on this screen,
  // which a spec that connects a provider in the wizard will have done.
  const advance = page.getByRole("button", { name: /^(Decide later|Continue)$/ });
  const onWizard = await advance
    .waitFor({ state: "visible", timeout: 20_000 })
    .then(() => true)
    .catch(() => false);
  if (!onWizard) return false;
  await advance.click();
  await page.getByRole("button", { name: "Balanced" }).click();
  await page.getByRole("button", { name: "Set up later" }).click();
  await page.getByRole("button", { name: "Open Workbench" }).click();
  await expect(page).toHaveURL(/#\/home$/, { timeout: 30_000 });
  await expect(advance).toBeHidden({ timeout: 30_000 });
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

/**
 * Set (or clear) the thinking budget for one composer.
 *
 * The effort used to be a `<select>` beside the model chip. It is now a section
 * *inside* the model menu, because the values a provider publishes belong to the
 * model rather than to the composer — and because "Thinking off" and "no effort
 * sent" are the same wire fact, so they are one control instead of two.
 *
 * `level` is one of the values the active model publishes (an effort like
 * `high`, or a mode like `adaptive`); `""` turns thinking off. Returns false
 * when this model publishes no reasoning setting at all, which is a state rather
 * than a failure: the section is then absent rather than empty.
 */
export async function setThinkingEffort(
  composer: Locator,
  page: Page,
  level: string,
): Promise<boolean> {
  const trigger = composer.getByRole("button", { name: /^Model for this turn:/ });
  await trigger.click();
  const effortRow = page.getByRole("button", { name: /^Effort/ });
  if (!(await effortRow.isVisible({ timeout: 5_000 }).catch(() => false))) {
    await page.keyboard.press("Escape");
    return false;
  }
  await effortRow.click();
  const section = page.getByRole("group", { name: "Effort" });
  if (level === "") {
    const thinking = section.getByRole("switch", { name: /Thinking/ });
    if ((await thinking.getAttribute("aria-checked")) === "true") await thinking.click();
  } else {
    await section
      .getByRole("menuitemradio", { name: new RegExp(`^${level}`, "i") })
      .click();
  }
  await page.keyboard.press("Escape");
  return true;
}

/**
 * Turn thinking on at whatever level this model publishes, and say which.
 *
 * Returns the level chosen, or null when the model publishes none — the caller
 * decides whether that is a skip or a failure. Used where a spec needs *some*
 * reasoning rather than a particular amount of it.
 */
export async function pickAnyThinkingLevel(
  composer: Locator,
  page: Page,
): Promise<string | null> {
  const trigger = composer.getByRole("button", { name: /^Model for this turn:/ });
  await trigger.click();
  const effortRow = page.getByRole("button", { name: /^Effort/ });
  if (!(await effortRow.isVisible({ timeout: 5_000 }).catch(() => false))) {
    await page.keyboard.press("Escape");
    return null;
  }
  await effortRow.click();
  const levels = page.getByRole("group", { name: "Effort" }).getByRole("menuitemradio");
  if ((await levels.count()) === 0) {
    await page.keyboard.press("Escape");
    return null;
  }
  const chosen = (await levels.last().textContent())?.trim() ?? null;
  await levels.last().click();
  await page.keyboard.press("Escape");
  return chosen;
}

/**
 * Sign in, on an empty workspace **or** one that already holds work (BUG-229).
 *
 * Every live spec used to inline this, and every one of them asserted the
 * empty-workspace heading — "Welcome to your Work Dashboard". The Workbench
 * says "Welcome back" once anything has run, so a spec re-run against the
 * workspace its own first run created failed on its first step, and the
 * failure looked like a product defect rather than a harness one. Accepting
 * either heading is what makes a round repeatable.
 *
 * It creates the account when there is none and unlocks when there is, so the
 * same call works on a fresh instance and on the fifth run against it.
 */
export async function signInAsOwner(
  page: Page,
  base: string,
  credentials: { user: string; password: string },
): Promise<void> {
  await page.goto(`${base}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const confirm = page.getByLabel("Confirm password");
  await page.getByLabel("Username").fill(credentials.user);
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(credentials.password);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  const workbench = page.getByRole("heading", {
    name: /Welcome (back|to your Work Dashboard)/,
  });
  await expect(
    page.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
  await expect(workbench).toBeVisible({ timeout: 30_000 });
}
