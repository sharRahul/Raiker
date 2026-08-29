import { expect, test, type Locator, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";

/**
 * BUG-69's live evidence, runnable with **one** provider key (BUG-84).
 *
 * The spec used to open by requiring both an Anthropic and an OpenRouter key,
 * so the documented way to reproduce this evidence was unrunnable for anyone
 * holding one credential — the common case. It also asserted a specific
 * non-ready outcome for one model, which is a property of the account that ran
 * it rather than of the product.
 *
 * Both are fixed here. Each provider leg is skipped when its key is absent, the
 * run fails only when no provider key is set at all, and every leg asserts the
 * readiness **state machine** — a provider that answers the catalogue either
 * becomes ready and can send, or produces a *classified* non-ready state that
 * disables Send and names its own repair — whichever one the account earns.
 *
 * The local leg is the same shape with a different precondition: a local runtime
 * is a *reachable process*, not a key, so it runs only when
 * `RAIKER_LIVE_OLLAMA_MODEL` names one. Local acquisition and deployment keep
 * their own dedicated specs (`bug-69-local-model-library-live.spec.ts`,
 * `default-ollama-live.spec.ts`); this spec is the readiness gate.
 */

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(
  import.meta.dirname,
  "..",
  "..",
  "..",
  "output",
  "playwright",
);
const PASSWORD = "Bug-69-live-review-password-1!";

interface ProviderLeg {
  provider: string;
  keyLabel: string;
  key: string;
  preferredModel: string;
  marker: string;
}

const LEGS: ProviderLeg[] = [
  {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "",
    preferredModel: "claude-haiku-4-5-20251001",
    marker: "BUG69 ANTHROPIC LIVE",
  },
  {
    provider: "OpenRouter",
    keyLabel: "OpenRouter API key",
    key: process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "",
    preferredModel: "openai/gpt-4o-mini",
    marker: "BUG69 OPENROUTER LIVE",
  },
  {
    provider: "OpenAI",
    keyLabel: "OpenAI API key",
    key: process.env.RAIKER_LIVE_OPENAI_KEY ?? "",
    preferredModel: "gpt-4o-mini",
    marker: "BUG69 OPENAI LIVE",
  },
  {
    provider: "Gemini",
    keyLabel: "Gemini API key",
    key: process.env.RAIKER_LIVE_GEMINI_KEY ?? "",
    preferredModel: "gemini-2.0-flash",
    marker: "BUG69 GEMINI LIVE",
  },
];

// Every non-ready state the gate is allowed to reach. The point of the assertion
// is that the owner is told which one in their own words — a raw reason code
// reaching this copy is the defect BUG-69 was filed for.
const CLASSIFIED_NON_READY =
  /cannot execute|not reachable|rejected|no credit|not available|does not support|blocked/i;

async function connectProvider(page: Page, leg: ProviderLeg): Promise<Locator> {
  const card = page
    .locator("article.provider-card")
    .filter({ hasText: leg.provider });
  await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
  await page.getByLabel(leg.keyLabel).fill(leg.key);
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 30_000 });
  return card;
}

async function chooseModel(card: Locator, preferred?: string) {
  await card.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = card.getByLabel("Available models");
  const custom = card.getByLabel("Custom model name");
  await expect(catalogue.or(custom)).toBeVisible({ timeout: 60_000 });
  if (await catalogue.isVisible()) {
    const values = await catalogue
      .locator("option")
      .evaluateAll((options) =>
        options
          .map((option) => (option as HTMLOptionElement).value)
          .filter(Boolean),
      );
    const choice =
      preferred && values.includes(preferred) ? preferred : values[0];
    expect(choice).toBeTruthy();
    await catalogue.selectOption(choice);
  } else {
    expect(preferred, "provide an exact fallback model id").toBeTruthy();
    await custom.fill(preferred!);
  }
  await card.getByRole("button", { name: "Use model" }).click();
}

/**
 * Drive one provider's readiness to a terminal state and report which one.
 *
 * Returns `"ready"` when the gate admits the turn and the model answers, and
 * `"blocked"` when it refuses with a classified state. Both are correct
 * outcomes; which one an account earns is not the product's property to assert.
 */
async function driveReadiness(
  page: Page,
  leg: ProviderLeg,
): Promise<"ready" | "blocked"> {
  await page.goto(`${BASE}/#/new-chat`);
  const modelButton = page.getByRole("button", {
    name: /Model for this turn:/,
  });
  await modelButton.click();
  const providerGroup = page
    .locator(".model-provider-group")
    .filter({ hasText: leg.provider });
  await expect(providerGroup).toBeVisible();
  await expect(modelButton.locator("img")).toHaveAttribute(
    "src",
    new RegExp(`/provider-logos/${leg.provider.toLowerCase()}`),
  );
  await modelButton.click();
  const prompt = page.getByPlaceholder("How can I help you today?");
  await prompt.fill(`Reply with exactly: ${leg.marker}`);
  const send = page.getByRole("button", { name: "Send", exact: true });

  if (await send.isDisabled()) {
    await modelButton.click();
    const selectedModel = (await modelButton.textContent())?.trim() ?? "";
    const setup = providerGroup
      .locator(".setup-choice")
      .filter({ hasText: selectedModel })
      .getByRole("button", { name: new RegExp(`^Set up ${leg.provider} for`) });
    await expect(setup).toBeVisible();
    await setup.click();
    const dialog = page.getByRole("dialog", { name: /model/i });
    await dialog.getByRole("button", { name: "Check again" }).click();
    await expect(dialog.getByText("Check complete")).toBeVisible({
      timeout: 90_000,
    });
    const blocked = await dialog.getByText(CLASSIFIED_NON_READY).isVisible();
    await dialog.getByRole("button", { name: "Close" }).click();
    if (blocked) {
      // The state machine's other half: a classified refusal keeps Send
      // disabled and the owner's draft intact.
      await expect(send).toBeDisabled();
      await expect(prompt).toHaveValue(`Reply with exactly: ${leg.marker}`);
      return "blocked";
    }
  }

  await expect(send).toBeEnabled({ timeout: 30_000 });
  await send.click();
  await expect(page.locator(".message-group-raiker").last()).toContainText(
    new RegExp(`${leg.marker}|Approval required for local action`),
    { timeout: 240_000 },
  );
  return "ready";
}

test("BUG-69 first-run gate and readiness state machine, per available provider", async ({
  page,
}) => {
  test.setTimeout(900_000);
  const available = LEGS.filter((leg) => leg.key !== "");
  expect(
    available.length,
    "set at least one of RAIKER_LIVE_ANTHROPIC_KEY, RAIKER_LIVE_OPENROUTER_KEY, " +
      "RAIKER_LIVE_OPENAI_KEY or RAIKER_LIVE_GEMINI_KEY",
  ).toBeGreaterThan(0);
  for (const leg of LEGS) {
    if (leg.key === "") {
      test.info().annotations.push({
        type: "skipped-leg",
        description: `${leg.provider}: no key set, leg skipped`,
      });
    }
  }

  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({
    timeout: 30_000,
  });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirmPassword = page.getByLabel("Confirm password");
  if (await confirmPassword.isVisible()) {
    await confirmPassword.fill(PASSWORD);
    await page
      .getByRole("button", { name: "Create a User Account", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Choose how to run models" }),
    ).toBeVisible();
    await capture(page, join(SHOTS, "bug69-first-run-model-setup-live.png"));
    await page.getByRole("button", { name: "Skip for now" }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker" }).click();
  }

  // The gate holds before any provider is reachable, whichever keys this run has.
  // It is asserted in Chat rather than on the Workbench: the Workbench no longer
  // has a composer to gate — it is the board over the work that is already
  // running — so the readiness gate lives where a prompt is actually written.
  await page.goto(`${BASE}/#/new-chat`);
  await page.getByLabel("Prompt", { exact: true }).fill("Draft a short project brief");
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Set up model" })).toBeVisible();
  await capture(page, join(SHOTS, "bug69-composer-readiness-gate-live.png"));

  await page.goto(`${BASE}/#/models?tab=hosted`);
  await expect(page.getByRole("tab", { name: "Local" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Hugging Face" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Activity" })).toBeVisible();
  for (const leg of available) {
    await connectProvider(page, leg);
  }
  await capture(page, join(SHOTS, "bug69-provider-setup-live.png"));

  const outcomes: Record<string, string> = {};

  // The local leg: a reachable runtime rather than a credential.
  const localModel = process.env.RAIKER_LIVE_OLLAMA_MODEL ?? "";
  if (localModel === "") {
    test.info().annotations.push({
      type: "skipped-leg",
      description: "Ollama: set RAIKER_LIVE_OLLAMA_MODEL to run the local leg",
    });
  } else {
    await page.goto(`${BASE}/#/models?tab=local`);
    await chooseModel(
      page.locator(".local-row").filter({ hasText: "Ollama" }),
      localModel,
    );
    outcomes.Ollama = await driveReadiness(page, {
      provider: "Ollama",
      keyLabel: "",
      key: "local",
      preferredModel: localModel,
      marker: "BUG69 OLLAMA LIVE",
    });
    await capture(page, join(SHOTS, `bug69-ollama-${outcomes.Ollama}-live.png`));
  }
  for (const leg of available) {
    await page.goto(`${BASE}/#/models?tab=hosted`);
    await chooseModel(
      page.locator("article.provider-card").filter({ hasText: leg.provider }),
      leg.preferredModel,
    );
    outcomes[leg.provider] = await driveReadiness(page, leg);
    await capture(page, join(
        SHOTS,
        `bug69-${leg.provider.toLowerCase()}-${outcomes[leg.provider]}-live.png`,
      ));
  }

  // Every leg that ran reached one of the two terminal states — never a raw
  // reason code and never an indefinite "checking".
  for (const outcome of Object.values(outcomes)) {
    expect(["ready", "blocked"]).toContain(outcome);
  }
  test.info().annotations.push({
    type: "readiness-outcomes",
    description: JSON.stringify(outcomes),
  });

  expect(consoleErrors).toEqual([]);
});
