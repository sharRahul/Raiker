/**
 * Live evidence for the 2026-09-06 composer and Models redesigns.
 *
 * Not a mocked shell: this drives a running `raiker-web` holding real provider
 * credentials, added through the product's own connect flow rather than seeded
 * into the store, and every screenshot shows the shipped surfaces answering
 * their own endpoints.
 *
 * What it is evidence *for*, in the order the review asks the questions:
 *
 *   MODEL-01  the selection an owner makes survives navigation and reload, and
 *             the page and the composer name the same model because they read
 *             the same contract.
 *   MODEL-02  Design has a model default of its own rather than borrowing
 *             Chat's.
 *   MODEL-03  the page opens on what is running the work, not on a filing
 *             system for the rows.
 *   COMPOSER-02/03/04  two entry points at rest on all three Work modes, with
 *             everything the four permanent controls used to offer inside them.
 *
 * Prerequisites:
 *   1. `python apps/api/main.py --workspace <ws> --port 8765 --no-browser`
 *      with RAIKER_MODEL_EGRESS_ALLOWLIST covering the providers below.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` / `RAIKER_LIVE_OPENAI_KEY` /
 *      `RAIKER_LIVE_OPENROUTER_KEY` in the environment. A provider whose key is
 *      absent is skipped by name rather than silently passed over — a round
 *      that quietly tested one provider and reported three is worse evidence
 *      than one that says which it had.
 */
import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");

/**
 * The model to name when a provider's catalogue cannot be listed.
 *
 * Anthropic's `models` endpoint needs an admin credential, so an ordinary key
 * reaches the picker's manual-entry path. Naming one here is what an owner does
 * in the same situation, and it keeps this round's evidence about a working
 * instance rather than a half-configured one.
 */
const FALLBACK_MODEL: Record<string, string> = {
  anthropic: "claude-sonnet-4-5",
  openai: "gpt-4o-mini",
  openrouter: "openai/gpt-4o-mini",
};

const KEYS = {
  anthropic: process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "",
  openai: process.env.RAIKER_LIVE_OPENAI_KEY ?? "",
  openrouter: process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "",
};

test.describe.configure({ mode: "serial" });

let page: Page;

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, colorScheme: "light" });
  await signInAsOwner(page, BASE);
});

test.afterAll(async () => {
  await page?.close();
});

/**
 * Whether a locator becomes visible within `ms`.
 *
 * `Locator.isVisible()` answers about *this instant* and takes no timeout, so
 * using it as a wait silently reports "not there" for anything that has not
 * rendered yet. That is how the first version of this round pinned no models at
 * all and still passed: every branch below took its early return.
 */
async function appears(locator: import("@playwright/test").Locator, ms = 15_000): Promise<boolean> {
  return locator
    .waitFor({ state: "visible", timeout: ms })
    .then(() => true)
    .catch(() => false);
}

/**
 * Connect one provider the way an owner does: open the card's sign-in, paste
 * the key, save.
 *
 * Deliberately through the interface rather than through the credential store.
 * What this round is evidence about includes whether the connect flow still
 * reaches the store after the Models page was reorganised, and seeding the
 * credential directly would answer a question nobody asked.
 */
async function connect(provider: string, key: string): Promise<void> {
  await page.goto(`${BASE}/#/models?tab=add`);
  const card = page.locator("article.provider-card", { hasText: new RegExp(provider, "i") }).first();
  await expect(card, `${provider} has no card on Add model`).toBeVisible({ timeout: 15_000 });
  const connect = card.getByRole("button", { name: /^(Connect|Reconnect)$/ });
  if ((await connect.count()) === 0) return; // already connected
  await connect.first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByLabel(/API key/i).fill(key);
  await dialog.getByRole("button", { name: /^(Save|Connect|Sign in)/ }).first().click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

/**
 * Keep one of a connected provider's models, the way an owner does next.
 *
 * A provider connects carrying a `<model>` placeholder, so connecting alone
 * leaves nothing that can answer a turn — which is the state the Overview's
 * "Needs attention" is *supposed* to report. Pinning a model here is what makes
 * the rest of this round evidence about a working instance rather than about a
 * half-configured one.
 */
/**
 * Give a connected provider a concrete model, the way an owner does next.
 *
 * A provider connects carrying a `<model>` placeholder, so connecting alone
 * leaves nothing that can answer a turn — which is the state the Overview's
 * "Needs attention" is *supposed* to report, and this round checks that too.
 *
 * Both of the picker's paths are real and both are exercised here, because
 * which one an owner meets is decided by the provider rather than by them:
 *
 *   * a provider whose catalogue Raiker can read offers switches, one per
 *     model, and keeping one makes it available everywhere;
 *   * a provider whose catalogue is refused offers a name field instead.
 *     Anthropic is that case on an ordinary key — listing models needs an
 *     admin credential, so `provider-models` answers
 *     `provider_workspace_required` and the owner types the model they intend
 *     to use.
 *
 * Returns the model that was pinned, or null when the provider offered neither.
 */
async function pinAModel(provider: string, fallbackModel: string): Promise<string | null> {
  await page.goto(`${BASE}/#/models?tab=add`);
  const card = page.locator("article.provider-card", { hasText: new RegExp(provider, "i") }).first();
  if ((await card.count()) === 0) return null;
  await card.scrollIntoViewIfNeeded();

  // MODEL-15 — one visible action per row, chosen by the row's state, and the
  // rest in an overflow. Which of the two holds the catalogue depends on
  // whether this provider already names a model, so try the visible one and
  // fall back rather than assuming either.
  const direct = card.getByRole("button", { name: /^Select models/ }).first();
  if (await appears(direct)) {
    await direct.click();
  } else {
    const more = card.getByRole("button", { name: /^More actions for / }).first();
    if (!(await appears(more))) return null;
    await more.click();
    const item = page.getByRole("menuitem", { name: /^Select models/ }).first();
    if (!(await appears(item))) return null;
    await item.click();
  }

  const dialog = page.getByRole("dialog");
  if (!(await appears(dialog, 60_000))) return null;

  const custom = dialog.getByLabel("Custom model name");
  if (await appears(custom, 30_000)) {
    await custom.fill(fallbackModel);
    await dialog.getByRole("button", { name: /^Use model/ }).click();
    await expect(dialog).toBeHidden({ timeout: 60_000 });
    return fallbackModel;
  }

  const boxes = dialog.getByRole("checkbox");
  if ((await boxes.count()) === 0) {
    // Nothing to keep, so leave — and leave *closed*. The picker staying up is
    // the failure that found the missing Escape handler this round fixed: it
    // blocked the next provider's card behind an overlay nothing could see.
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden({ timeout: 15_000 });
    return null;
  }

  const wanted = boxes.filter({ has: page.getByText(fallbackModel, { exact: false }) }).first();
  const box = (await wanted.count()) > 0 ? wanted : boxes.first();
  const name = (await box.getAttribute("aria-label")) ?? fallbackModel;
  await box.check();
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden({ timeout: 60_000 });
  return name;
}

test("Models opens on what powers the work, and says so from one contract", async () => {
  await page.goto(`${BASE}/#/models`);

  // MODEL-03 — five tabs named for the questions an owner arrives with.
  const strip = page.getByRole("tablist", { name: "Model settings" });
  await expect(strip.getByRole("tab")).toHaveText([
    "Overview",
    "My models",
    "Add model",
    "Runtime & routing",
    "Usage",
  ]);
  await expect(page.getByRole("heading", { name: "What powers your work" })).toBeVisible();
  // Scoped to the section that answers the question. MODEL-13's "Needs
  // attention" names the same surfaces when one of them cannot run, which is
  // the design working rather than a duplicate to disambiguate around.
  const powers = page.getByLabel("What powers your work");
  for (const surface of ["Chat", "Build", "Design"]) {
    await expect(
      powers.getByText(surface, { exact: true }),
      `${surface} is missing from the Overview`,
    ).toBeVisible();
  }
  await capture(page, join(SHOTS, "live-models-overview.png"));

  // MODEL-11 — Default and Effective are separate columns.
  await page.goto(`${BASE}/#/models?tab=runtime`);
  await expect(page.getByRole("heading", { name: "Work defaults" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Default" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Effective now" })).toBeVisible();
  await capture(page, join(SHOTS, "live-models-work-defaults.png"));
});

test("each provider connects through the product's own flow", async () => {
  // Three real connect flows and three catalogue reads, each reaching a
  // provider over the network. The default budget is for a mocked page.
  test.setTimeout(240_000);
  const missing = Object.entries(KEYS)
    .filter(([, key]) => key === "")
    .map(([name]) => name);
  test.skip(missing.length === Object.keys(KEYS).length, `no provider keys in the environment`);

  for (const [provider, key] of Object.entries(KEYS)) {
    if (key === "") {
      test.info().annotations.push({ type: "skipped provider", description: provider });
      continue;
    }
    await connect(provider, key);
    const pinned = await pinAModel(provider, FALLBACK_MODEL[provider] ?? "");
    test.info().annotations.push({
      type: provider,
      description: pinned === null ? "connected, no model pinned" : `pinned ${pinned}`,
    });
  }

  // MODEL-04 — one inventory, whatever a model's provider is.
  await page.goto(`${BASE}/#/models?tab=models`);
  await expect(page.getByLabel("Filter models")).toBeVisible();
  await capture(page, join(SHOTS, "live-models-inventory.png"));
});

test("a selection survives navigation and reload, and the composer agrees", async () => {
  // MODEL-01's acceptance path, exactly as the review writes it: select, move
  // between surfaces, reload, and find the same model still selected.
  await page.goto(`${BASE}/#/models?tab=models`);
  await expect(page.getByLabel("Filter models")).toBeVisible();

  // Name the row *before* pressing its own Use, and assert about that row
  // afterwards. Reading back "whichever row says Selected" is a different
  // claim — it passes if any row is selected — and it races the list's own
  // refresh, which is how it first failed here for a reason that had nothing to
  // do with persistence.
  const candidate = page.locator(".rows li", { has: page.getByRole("button", { name: "Use" }) }).first();
  test.skip((await candidate.count()) === 0, "every model is already the answer somewhere");
  const chosen = (await candidate.locator(".model").textContent())!.trim();
  await candidate.getByRole("button", { name: "Use" }).click();

  const row = () => page.locator(".rows li", { has: page.getByText(chosen, { exact: true }) }).first();
  await expect(row().getByText("Selected"), `${chosen} did not become selected`).toBeVisible({
    timeout: 30_000,
  });

  // MODEL-01's acceptance path: move between the three Work modes and back,
  // then reload the whole application.
  for (const route of ["new-chat", "build", "design", "models?tab=models"]) {
    await page.goto(`${BASE}/#/${route}`);
    await page.waitForTimeout(400);
  }
  await page.reload();
  await page.goto(`${BASE}/#/models?tab=models`);
  await expect(page.getByLabel("Filter models")).toBeVisible();
  await expect(
    row().getByText("Selected"),
    `${chosen} stopped being selected after a reload`,
  ).toBeVisible({ timeout: 30_000 });
});

test("Design remembers its own model rather than borrowing Chat's", async () => {
  // MODEL-02. The product model is Chat | Build | Design; before this, two of
  // the three had explicit surface state and the third followed the global
  // default, so an owner who put Chat on a small model had their image prompts
  // follow it there.
  await page.goto(`${BASE}/#/design`);
  const picker = page.getByLabel("Image model");
  test.skip((await picker.count()) === 0, "no connected provider declares an image model");

  const options = await picker.locator("option").allTextContents();
  test.skip(options.length < 2, "only one image model is connected, so nothing can drift");

  await picker.selectOption({ index: 1 });
  const chosen = await picker.inputValue();
  await page.goto(`${BASE}/#/new-chat`);
  await page.goto(`${BASE}/#/design`);
  await expect(page.getByLabel("Image model")).toHaveValue(chosen);
  await capture(page, join(SHOTS, "live-design-composer.png"));
});

test("every Work mode composes the same way against a live runtime", async () => {
  for (const [route, label, tools] of [
    ["new-chat", "Prompt", true],
    ["build", "Describe the change", true],
    ["design", "Describe the image", false],
  ] as const) {
    await page.goto(`${BASE}/#/${route}`);
    await expect(page.getByLabel(label, { exact: true })).toBeVisible();
    const composer = page.locator("form.composer:visible");
    await expect(composer.getByRole("button", { name: "Add to this turn" })).toBeVisible();
    await expect(composer.getByRole("button", { name: "Tools" })).toHaveCount(tools ? 1 : 0);
    for (const gone of ["Add attachment", "Dictate"]) {
      await expect(composer.getByRole("button", { name: gone })).toHaveCount(0);
    }
    await capture(page, join(SHOTS, `live-composer-${route}.png`));
  }

  // COMPOSER-04 — the menu is built from the gates this runtime actually
  // reports, so a capability that is off here is listed with its reason.
  await page.goto(`${BASE}/#/build`);
  await page.getByRole("button", { name: "Tools" }).click();
  const tools = page.getByRole("menu", { name: "Tools" });
  await expect(tools.getByRole("menuitem", { name: "Run a command" })).toBeVisible();
  await capture(page, join(SHOTS, "live-composer-tools.png"));
  await page.keyboard.press("Escape");
});

test("a real turn still sends, and the composer says what it will see", async () => {
  test.setTimeout(300_000);
  await page.goto(`${BASE}/#/new-chat`);

  // COMPOSER-05 — choose the model for this turn from the composer's own
  // control, which is the surface this document is about. Whichever model the
  // picker offers is one the readiness gate has judged usable: the picker lists
  // what can be chosen, so picking from it is the owner's path to a turn that
  // can actually run.
  const modelControl = page.getByRole("button", { name: /^Model for this turn/ });
  await expect(modelControl).toBeVisible({ timeout: 60_000 });
  await modelControl.click();
  const menu = page.getByRole("menu", { name: "Models" });
  await expect(menu).toBeVisible();
  const choices = menu.getByRole("menuitemradio");
  // Waited for rather than counted: the models read resolves after the first
  // paint, so an immediate count answers about the frame before the list.
  await expect(choices.first(), "the picker offers nothing to choose").toBeVisible({
    timeout: 60_000,
  });

  // From a connected provider's own group, not simply the first row. The picker
  // lists local runtime slots too, and a slot with nothing served is a model
  // that can be chosen and cannot answer — which is a true thing for the picker
  // to offer and a useless one for this test to pick.
  const hosted = menu.getByRole("group", { name: /OpenAI models/i });
  const pick = (await hosted.count()) > 0 ? hosted.getByRole("menuitemradio").first() : choices.first();
  await pick.click();
  await capture(page, join(SHOTS, "live-composer-model-picker.png"));

  const prompt = page.getByLabel("Prompt", { exact: true });

  // The phrase the model is asked to produce must not appear in the prompt, or
  // the transcript matches the owner's own message and the assertion passes
  // without a model having answered at all. Asking for a word the prompt does
  // not contain is the whole difference between evidence and a tautology.
  await prompt.fill("Reply with one word: the colour of a clear midday sky.");

  const send = page.getByRole("button", { name: "Send" });
  await expect(send).toBeEnabled({ timeout: 120_000 });
  await send.click();

  // The answer, in the assistant's own turn rather than anywhere on the page.
  const answer = page.locator(".message-group-raiker").last();
  await expect(answer).toContainText(/blue/i, { timeout: 180_000 });
  await capture(page, join(SHOTS, "live-chat-turn.png"));

  // COMPOSER-06 — the line appears once there is something true to say, and
  // opens on the token counts the ring used to carry.
  const context = page.getByRole("button", { name: /^Context for this turn/ });
  await expect(context).toBeVisible();
  await context.click();
  const inspector = page.getByRole("dialog", { name: "Context for this turn" });
  await expect(inspector).toBeVisible();
  await expect(inspector.getByText("This turn will see")).toBeVisible();
  await expect(
    inspector.getByLabel("Context window and cost details"),
    "the context meter is not composed into the inspector",
  ).toBeVisible();
  await capture(page, join(SHOTS, "live-composer-context.png"));
});
