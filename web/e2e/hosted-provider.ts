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
  // By label rather than by placeholder: the placeholder has said "Search
  // permissions, actions or groups…" since the page's own vocabulary changed,
  // so this waited sixty seconds for a string the product no longer prints and
  // then walked on with the list unrendered. The label is the stable half.
  await page.getByLabel("Search capabilities").waitFor({ timeout: 60_000 });
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
 * **FIRST-02 … FIRST-09 rewrote which stages exist**, and every heading below
 * moved with them: `Account` and `Backup` are no longer stages, a `Welcome`
 * screen opens the flow, the privacy question is about where content travels,
 * and the last screen finishes into work rather than into "Open Workbench". The
 * retired headings are still answered, because an instance created before that
 * change can have one of them stored and resuming it must not throw.
 *
 * **Only the final stage closes it.** The old helper
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
    if (heading.startsWith("Meet Raiker")) {
      await page.getByRole("button", { name: "Continue" }).click();
    } else if (
      heading.startsWith("Choose how Raiker should think") ||
      // Retired heading, still answered: an instance created before FIRST-04.
      heading.startsWith("Choose where Raiker thinks")
    ) {
      // "Decide later" and "Continue" are the same button; which one it is
      // depends on whether a model was pinned on this screen, and either
      // advances. The model itself is connected through Models afterwards.
      await page.getByRole("button", { name: /^(Decide later|Continue)$/ }).click();
    } else if (heading.startsWith("Where may Raiker send model requests")) {
      // The connected-providers answer, because a live round connects a hosted
      // provider and "Local only" would leave it refused for a reason the spec
      // is not about.
      await page.getByRole("button", { name: /Local, and the providers I connect/ }).click();
    } else if (heading.startsWith("Choose your privacy boundary")) {
      // Balanced, because a live round connects a hosted provider and
      // local-first would leave it refused for a reason the spec is not about.
      await page.getByRole("button", { name: "Balanced" }).click();
    } else if (heading.startsWith("Create your first backup")) {
      await page.getByRole("button", { name: "Set up later" }).click();
    } else if (heading.startsWith("Your Raiker is ready") || heading.startsWith("Setup saved")) {
      // REM-LAUNCH-01 — the last stage now says which of the two it is: a run
      // that deferred the model reads "Setup saved" and names what is missing.
      // Both are the final stage and both finish the same way.
      await page.getByRole("button", { name: "Start using Raiker" }).click();
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
 * first real navigation meets it again. Waiting for "either the destination or
 * the wizard" rather than polling for the wizard immediately is what makes this
 * deterministic: the wizard mounts only once the bootstrap reads have resolved,
 * which is after `goto` returns. It is identified by its own heading rather
 * than by a control on one of its stages, because a workspace resumed part-way
 * shows a stage that has neither of the buttons this used to wait for.
 *
 * **Found live on 2026-09-07, and it had taken every live spec down with it.**
 * The Models rebuild folded Local and Hosted into one **Add model** tab, and
 * `?tab=hosted` became an alias that lands on the *inventory* — a page with no
 * provider cards on it at all. This helper still waited for a `Hosted` tab, so
 * eighteen specs timed out before their first assertion, and the failure looked
 * like a broken product rather than a stale harness. It waits for the section
 * heading now: `Your hosted providers` is what the redesign actually renders,
 * and unlike a tab name it is the thing the cards are under.
 */
export async function openHostedProviders(page: Page, base: string): Promise<void> {
  const hosted = page.getByRole("heading", { name: "Your hosted providers" });
  const wizard = page.locator("#setup-title");
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await page.goto(`${base}/#/models?tab=add`);
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
 * Open one provider's **Details**, wherever the row happens to keep it.
 *
 * A connected card offers one primary action and one overflow, so
 * Details is a menu item; an unconnected card has historically carried it
 * directly. Both are tried, in that order, so a spec never has to know which
 * shape of row it is looking at.
 */
export async function openProviderDetails(page: Page, card: Locator): Promise<void> {
  await pressCardAction(page, card, /^Details$/);
  await expect(page.getByRole("button", { name: "Close model details" })).toBeVisible({
    timeout: 30_000,
  });
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
  //
  // **Found live on 2026-09-12.** Details then moved into the overflow: a
  // repeated row gets one primary action and one overflow, so a *connected*
  // card offers `Select models…` and a `More actions` menu, and nothing named
  // Details is on the card at all. This branch waited five minutes for a button
  // that had become a menu item, and the failure read as a provider that could
  // not be reconnected rather than as a helper looking in the wrong place.
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
  } else {
    await openProviderDetails(page, card);
    await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  }
  await page.getByLabel(keyLabel).fill(key);
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  // The Reconnect path opens **Model details** to reach the control, and saving
  // a credential used to leave that modal sitting over the card it had just
  // changed. `saveConnection` closes both the sign-in dialog and Details itself
  // now, so this is a *guard*, not the fix: wait for the sign-in overlay to go,
  // then close Details only if the product has not already.
  //
  // Waiting for the overlay first is the whole point. Found 2026-09-05 running
  // this helper against a workspace that already held the connection: the
  // Details close button is behind the sign-in overlay while it is still
  // mounted, so an unconditional click resolved the button, waited for it to be
  // "stable", and then spent the spec's whole timeout being told the overlay
  // intercepts pointer events — reported as a slow click on a button nobody
  // needed to press.
  await expect(page.locator(".signin-overlay")).toHaveCount(0, { timeout: 60_000 });
  const detailsClose = page.getByRole("button", { name: "Close model details" });
  if (await detailsClose.isVisible().catch(() => false)) {
    await detailsClose.click();
    await expect(detailsClose).toBeHidden({ timeout: 30_000 });
  }
  return card;
}

/**
 * Press one of a provider card's actions, wherever the card keeps it.
 *
 * **Found live on 2026-09-13.** A repeated row gained one primary action
 * and one overflow, and the row has gone on tightening since: a connected card
 * now offers `Select` and a `More actions` menu holding **Select models…**,
 * **Test connection** and **Details**. Every helper below looked for a button
 * *on the card* and, not finding one, waited out the spec's whole timeout — so
 * a UI that had merely moved a control read as a provider that could not be
 * tested. Same shape as BUG-229 and BUG-241: the drift is in the harness, and
 * the fix belongs in the one place that knows where a control lives.
 *
 * The card is tried first, so a shape that still puts the action in the open
 * keeps working, and the menu name is matched loosely because "Test" and "Test
 * connection" are the same control under two labels.
 */
export async function pressCardAction(page: Page, card: Locator, name: RegExp): Promise<void> {
  const direct = card.getByRole("button", { name }).first();
  if (await direct.isVisible().catch(() => false)) {
    await direct.click();
    return;
  }
  await card.getByRole("button", { name: /More actions/ }).click();
  await page.getByRole("menuitem", { name }).first().click();
}

/**
 * Run the readiness check for the model pinned on *card* and wait for it to
 * settle, so the composer will let a turn be sent.
 *
 * The check is the product's own **Test** control — the same one a person
 * clicks — rather than an API call the spec makes behind the page's back.
 */
export async function checkModelReady(page: Page, card: Locator): Promise<void> {
  await pressCardAction(page, card, /^Test( connection)?$/);
  // The card states the outcome for the *pinned model*: reachable, or the exact
  // reason it is not. "Not checked" is the state before the check answers, so it
  // is deliberately not one of the accepted outcomes.
  await expect(
    card.getByText(
      // BUG-272 — `needs a workspace` joined this list the day the answer
      // existed. The set is closed on purpose: an outcome missing from it does
      // not fail the check, it hangs for two minutes and then blames the spec
      // that was using the key rather than the key.
      //
      // `could not be reached` joined it on 2026-09-13, running the round
      // against a host whose egress policy refuses `CONNECT openrouter.ai`.
      // That is the product's honest last-resort sentence for a genuinely
      // unclassified failure, and the helper was hanging on it — reporting a
      // provider this host cannot reach as a spec that had gone wrong.
      /can reach|could not be reached|cannot execute|not reachable|rejected|no credit|no quota|needs a workspace|identity-linked/i,
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
  await pressCardAction(page, card, /Select models|Choose model|Change model/);
  const dialog = page.getByRole("dialog", { name: /models/i });
  await expect(dialog).toBeVisible({ timeout: 60_000 });
  // BUG-295 — visible is not the same as answered.
  //
  // The dialog mounts immediately and asks the provider for its catalogue
  // afterwards, so for the first second or two it holds nothing but "Loading
  // models from X…". Every helper below read its checkboxes the instant it
  // appeared, saw an empty fieldset, and handed back an empty list — and the
  // spec that had asked for `offered[0]` then went looking for
  // `input[value="undefined"]`, waited its full timeout for an element that
  // could never exist, and failed two hundred lines later as though the product
  // had lost a model.
  //
  // Waiting on the loading note to go is the honest wait: it is the one thing
  // on this dialog that means "the answer has not arrived yet", and when it
  // clears the dialog is showing whatever it really has — a catalogue, a
  // refusal, or the custom-name fallback.
  await expect(dialog.getByText(/^Loading models from/i)).toBeHidden({
    timeout: 120_000,
  });
  return dialog;
}

/**
 * Every model id this provider published, in the order it published them.
 *
 * BUG-295 — fails saying so when the provider published none, rather than
 * returning `[]` for a caller to trip over. A helper that cannot find what it
 * is waiting for has to be the thing that fails: the whole failure mode this
 * closes is a silent empty answer being blamed on the assertion that used it.
 */
export async function offeredModelIds(dialog: Locator): Promise<string[]> {
  const ids = await dialog
    .locator('input[type="checkbox"]')
    .evaluateAll((boxes) =>
      boxes.map((box) => (box as HTMLInputElement).value).filter(Boolean),
    );
  if (ids.length === 0) {
    const note = (await dialog.locator(".picker-note").first().textContent()) ?? "";
    throw new Error(
      "offeredModelIds: this provider's model dialog published no models. " +
        `The dialog says: ${note.trim() || "(no note)"}`,
    );
  }
  return ids;
}

/** Turn one model's switch on, if it is not already on, and close the dialog. */
export async function keepOffered(dialog: Locator, model: string): Promise<void> {
  // BUG-295 — the second half of the same failure. `offered[0]` on an empty
  // list is `undefined`, and a selector built from it is a valid selector for
  // nothing, so this waited its timeout and reported a missing element instead
  // of a missing model id.
  if (typeof model !== "string" || model.trim() === "") {
    throw new Error(
      `keepOffered: asked to keep ${JSON.stringify(model)}, which is not a ` +
        "model id. The caller's list of offered models was probably empty.",
    );
  }
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
  // of its stages: a workspace that left setup part-way resumes on the
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

/**
 * Choose the model this turn will use, from the composer's own picker.
 *
 * BUG-292 — pinning a model on a provider card and choosing it for a turn are
 * two different decisions, by design. The first makes a model *available*; the
 * second makes it the one that answers. A workspace where no global model has
 * ever been chosen leaves Send disabled and says so — *"No model is chosen.
 * Choose one from the model menu beside Send."* — which is the composer being
 * right, and several live specs were waiting out their timeout on that disabled
 * button and reporting it as a product failure.
 *
 * Here rather than inline in each spec for the reason FIXED-503 gives: the
 * harness keeps encoding where a control used to be, and one copy is one edit
 * the next time the picker changes.
 */
export async function chooseModelForTurn(
  page: Page,
  model: RegExp,
  composerLabel = "Message composer",
): Promise<void> {
  // Chat, Build and Design label their composer "Message composer"; Tasks
  // labels its own "Plan work", because what it composes is a plan rather than
  // a message. Same control, same decision, one helper — a second copy here is
  // exactly the drift FIXED-503 describes.
  const composer = page.getByRole("group", { name: composerLabel });
  await composer.getByRole("button", { name: /^Model for this turn:/ }).click();
  const menu = page.getByRole("menu", { name: "Models" });
  await expect(menu).toBeVisible({ timeout: 30_000 });
  // A radio, not a plain item: the menu is a single choice among the models the
  // owner's providers published, and it says so in its roles.
  await menu.getByRole("menuitemradio", { name: model }).first().click();
  // The trigger reading anything but "Not selected" is the product's own
  // confirmation that the choice landed. Asserting it here is what stops a
  // silently-missed click becoming a disabled Send three lines later.
  await expect(
    composer.getByRole("button", { name: /^Model for this turn: (?!Not selected)/ }),
  ).toBeVisible({ timeout: 30_000 });
}
