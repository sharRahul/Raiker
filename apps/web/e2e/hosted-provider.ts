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
import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * The owner every live spec signs in as, unless it is *about* signing in.
 *
 * BUG-229 shared the sign-in *steps*; this is the fixture half of the same
 * problem, and BUG-247 closed it. Every live spec used to declare its own
 * password, so two of them could not be run against one workspace — which is
 * why every FIXED entry's evidence had to be re-seeded from scratch. A password
 * is not evidence about anything a spec asserts, so there is one.
 *
 * The environment override exists so a round can point the whole suite at an
 * instance it did not create; `RAIKER_LIVE_USER` is accepted alongside
 * `RAIKER_LIVE_OWNER` because two specs already used that name.
 *
 * The three specs that are *about* signing in still bring their own, because
 * sharing the fixture there would hide the behaviour they exist to check.
 */
export const OWNER_CREDENTIALS = {
  user: process.env.RAIKER_LIVE_OWNER ?? process.env.RAIKER_LIVE_USER ?? "Rahul",
  password: process.env.RAIKER_LIVE_PASSWORD ?? "Ithink@10",
};

/**
 * Say, before anything else runs, that this spec needs a workspace nothing has
 * touched — and skip with the reason when it does not have one.
 *
 * BUG-250. Once BUG-229, BUG-247 and BUG-248 had peeled away the assumptions
 * that stopped two specs sharing a workspace, a round finally *could* run
 * against one — and the layer underneath was that a handful of specs are about
 * the state a first run leaves. `bug-58-known-limits-live` asserts what two
 * gates do before the owner has touched them, `default-ollama-live` asserts the
 * model a fresh install names, and the three sign-in specs are about creating
 * the account. None of them is wrong; all of them are unrunnable second.
 *
 * **The signal is the account, and it is the honest one.** A workspace with no
 * owner offers "Confirm password" on the sign-in form, because the form is
 * creating an account rather than unlocking one. That is not a proxy for
 * freshness — it *is* freshness, from the product's own surface, read the way an
 * owner would read it. Nothing is inferred from a file, a timestamp, or an
 * environment variable a runner would have to remember to set.
 *
 * A skip rather than a failure, and a skip that says why: a round that runs the
 * whole suite against one instance should be told which specs need their own
 * one, not left to work it out from an assertion about a readiness window.
 */
export async function requireFirstRunWorkspace(
  page: Page,
  base: string,
  reason: string,
): Promise<void> {
  await page.goto(`${base}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  await expect(page.getByLabel("Username")).toBeEnabled({ timeout: 60_000 });
  const fresh = await page
    .getByLabel("Confirm password")
    .isVisible()
    .catch(() => false);
  test.skip(
    !fresh,
    `${reason} This workspace already has an owner account, so it is not a first run. ` +
      "Point RAIKER_LIVE_BASE at a new instance to run it.",
  );
}

/**
 * Turn a capability on the way an owner does, from the Permissions page.
 *
 * Every live spec that needs a gated capability had its own copy of this, and
 * the copies rotted the way BUG-229's sign-ins did. The one that mattered:
 * `page.waitForLoadState("networkidle")` returns before the capability list has
 * rendered, so `page.locator(".cap.card")` found **nothing** and the spec
 * skipped the whole turn-on quietly — leaving the gate closed, the control
 * disabled, and a failure two hundred lines later that read as a product defect.
 * Waiting for the search field, which is part of the list's own shell, is what
 * makes this deterministic.
 *
 * Idempotent: a capability that is already on is left alone rather than being
 * turned off and on again, so a spec can call this against a used workspace.
 */
export async function enableCapability(
  page: Page,
  base: string,
  label: string,
  reason: string,
): Promise<void> {
  await page.goto(`${base}/#/capabilities`);
  await page.getByPlaceholder(/Search capabilities/).waitFor({ timeout: 60_000 });
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible({ timeout: 60_000 });
  await card.locator("button.cap-toggle").click();
  const turnOn = card.getByRole("button", { name: "Turn on", exact: true });
  // Already on: the detail offers "Turn off" instead, and pressing anything here
  // would be a change this helper was not asked to make.
  if (!(await turnOn.isVisible().catch(() => false))) return;
  await turnOn.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await dialog.getByLabel("Reason (required)").fill(reason);
  const token = dialog.getByLabel(/Confirmation token/);
  if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
  const acknowledgement = dialog.getByLabel(/reviewed the threat model/);
  if (await acknowledgement.isVisible().catch(() => false)) await acknowledgement.check();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 60_000 });
}

/**
 * Complete the first-run setup wizard if it is up, from whichever stage it is on.
 *
 * A brand-new instance opens it over the workbench (FIXED-133), and it is
 * modal: a spec that signs in and goes straight to Models is talking to a page
 * it cannot reach.
 *
 * **It is a five-stage wizard, and only `finish` closes it.** The old helper
 * knew one stage. It clicked "Skip for now" — a control that no longer exists
 * anywhere in the app — and otherwise clicked "Decide later" and then assumed
 * the next three stages in a fixed order. A workspace whose setup was *left*
 * part-way, which is exactly what a previous spec run produces, resumes on the
 * stage it stopped at: `privacy` offers "Local-first"/"Balanced"/"Back" and
 * none of the three names the helper waited for. Every spec run against that
 * workspace then failed at sign-in, which is the property BUG-247 and BUG-248
 * exist to remove.
 *
 * So the wizard is driven by *reading which stage is on screen* and answering
 * that stage, until the wizard is gone. That works from any entry stage, and it
 * finishes setup rather than deferring it — a deferred wizard is the state that
 * traps the next run.
 */
export async function dismissFirstRunModelSetup(page: Page): Promise<boolean> {
  const title = page.locator("#setup-title");
  // Waited for rather than sampled: the wizard mounts only once the bootstrap
  // reads resolve, which is after the navigation that showed this page
  // returned. A run that was never on it says so by the wait expiring.
  const onWizard = await title
    .waitFor({ state: "visible", timeout: 20_000 })
    .then(() => true)
    .catch(() => false);
  if (!onWizard) return false;

  // Five stages, and `Back` on three of them, so a loop that could revisit one
  // is bounded rather than trusted.
  for (let step = 0; step < 8; step += 1) {
    if (!(await title.isVisible().catch(() => false))) return true;
    const heading = ((await title.textContent()) ?? "").trim();
    if (heading.startsWith("Preparing")) {
      await page.waitForTimeout(500);
      continue;
    }
    if (heading.startsWith("Choose where Raiker thinks")) {
      // "Decide later" and "Continue" are the same button; which one it is
      // depends on whether a model was pinned on this screen, and either
      // advances. The model itself is connected through Models afterwards.
      await page.getByRole("button", { name: /^(Decide later|Continue)$/ }).click();
    } else if (heading.startsWith("Choose your privacy boundary")) {
      // Balanced, because a live round connects a hosted provider and
      // local-first would leave it refused for a reason the spec is not about.
      await page.getByRole("button", { name: "Balanced" }).click();
    } else if (heading.startsWith("Create your first backup")) {
      await page.getByRole("button", { name: "Set up later" }).click();
    } else if (heading.startsWith("Your Raiker is ready")) {
      await page.getByRole("button", { name: "Open Workbench" }).click();
      await expect(title).toBeHidden({ timeout: 30_000 });
      return true;
    } else {
      // An unknown stage is a wizard change, not something to guess at.
      throw new Error(`Unrecognised setup stage: ${heading}`);
    }
    await expect(title).not.toHaveText(heading, { timeout: 30_000 });
  }
  throw new Error("The setup wizard did not reach its final stage");
}

/**
 * The Models page, on the tab that actually holds the hosted provider cards.
 *
 * The wizard is re-asserted on every *load* until setup is finished, so the
 * first real navigation meets it again. Waiting for "either the tab or the
 * wizard" rather than polling for the wizard immediately is what makes this
 * deterministic: the wizard mounts only once the bootstrap reads have resolved,
 * which is after `goto` returns. It is identified by its own heading rather
 * than by a control on one of its stages, because a workspace resumed part-way
 * shows a stage that has neither of the buttons this used to wait for.
 */
export async function openHostedProviders(page: Page, base: string): Promise<void> {
  const hosted = page.getByRole("tab", { name: "Hosted" });
  const wizard = page.locator("#setup-title");
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await page.goto(`${base}/#/models?tab=hosted`);
    await expect(hosted.or(wizard).first()).toBeVisible({ timeout: 30_000 });
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
    card.getByText(
      // BUG-272 — `needs a workspace` joined this list the day the answer
      // existed. The set is closed on purpose: an outcome missing from it does
      // not fail the check, it hangs for two minutes and then blames the spec
      // that was using the key rather than the key.
      /can reach|cannot execute|not reachable|rejected|no credit|no quota|needs a workspace|identity-linked/i,
    ),
  ).toBeVisible({ timeout: 120_000 });
}

/**
 * Open a provider's model dialog and hand back the dialog itself.
 *
 * The dialog is mounted at the page root rather than inside the card, so a
 * spec that scoped its query to the card found nothing once the inline picker
 * became a dialog.
 */
export async function openModelDialog(page: Page, card: Locator): Promise<Locator> {
  await card
    .getByRole("button", { name: /Select models|Choose model|Change model/ })
    .click();
  const dialog = page.getByRole("dialog", { name: /models/i });
  await expect(dialog).toBeVisible({ timeout: 60_000 });
  return dialog;
}

/** Every model id this provider published, in the order it published them. */
export async function offeredModelIds(dialog: Locator): Promise<string[]> {
  return dialog
    .locator('input[type="checkbox"]')
    .evaluateAll((boxes) =>
      boxes.map((box) => (box as HTMLInputElement).value).filter(Boolean),
    );
}

/** Turn one model's switch on, if it is not already on, and close the dialog. */
export async function keepOffered(dialog: Locator, model: string): Promise<void> {
  const box = dialog.locator(`input[type="checkbox"][value="${model}"]`);
  await expect(box).toBeAttached({ timeout: 30_000 });
  if (!(await box.isChecked())) await box.click();
  await expect(box).toBeChecked({ timeout: 30_000 });
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

/**
 * Keep one exact model offered by this provider.
 *
 * Choosing models is a dialog of switches rather than a select-and-confirm
 * inside the card: each switch is the whole decision, and the switch carries
 * the model id so a spec never has to know how a display name is derived.
 */
export async function keepModelAvailable(
  page: Page,
  card: Locator,
  model: string,
): Promise<void> {
  await keepOffered(await openModelDialog(page, card), model);
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
  await keepModelAvailable(page, card, options.model);
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
  credentials: { user: string; password: string } = OWNER_CREDENTIALS,
): Promise<void> {
  await page.goto(`${base}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const confirm = page.getByLabel("Confirm password");
  // The field mounts disabled while the bootstrap reads resolve. Waited for
  // rather than filled optimistically: on a server that has only just started,
  // the first attempt lands before the form is usable.
  const username = page.getByLabel("Username");
  await expect(username).toBeEnabled({ timeout: 60_000 });
  await username.fill(credentials.user);
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
  // The wizard is identified by its own heading rather than by a button on one
  // of its five stages: a workspace that left setup part-way resumes on the
  // stage it stopped at, and "Decide later" lives on only one of them.
  await expect(
    page.locator("#setup-title").or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
  // Signed in, rather than *on the workbench*. A workspace with a saved startup
  // route lands somewhere else entirely, and waiting for a greeting there is
  // BUG-229 behaving exactly as recorded. The navigation rail is the thing that
  // means "there is a session here", which is what every caller actually needs.
  await expect(
    page.getByRole("navigation", { name: "All navigation" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
}
