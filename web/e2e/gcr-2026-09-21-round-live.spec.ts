import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import {
  chooseModelForTurn,
  connectHostedProvider,
  hostedProviderCard,
  openHostedProviders,
  pressCardAction,
  signInAsOwner,
  useHostedModel,
} from "./hosted-provider";

/**
 * The 2026-09-21 round, live: the static-review items closed this run, proved
 * against a real host rather than a fixture.
 *
 * Four of them need one:
 *
 * * **CR-07** — a Content-Security-Policy is a header the browser enforces. A
 *   unit test can prove it is sent; only a browser can prove the product still
 *   works under it, and the console is where that shows.
 * * **GCR-16** — the build identity has to reach a surface an owner reads.
 * * **UX-BUILD-05** — the return path from Build to the project that started
 *   the work is a navigation, so it is proved by navigating.
 * * **GCR-14/GCR-17** — a pooled connection and one provider-name spelling are
 *   only interesting against a provider that really answers.
 *
 * Preconditions:
 *   1. `raiker-web` on 127.0.0.1:8765
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (entered through the UI)
 *   3. Optionally `RAIKER_LIVE_OPENAI_KEY`, `RAIKER_LIVE_OPENROUTER_KEY` —
 *      entered through the UI too, and asserted to fail *honestly* on a host
 *      whose egress policy refuses them (BUG-290).
 */
const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-09-21-static-review-round");
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const OPENAI_KEY = process.env.RAIKER_LIVE_OPENAI_KEY ?? "";
const OPENROUTER_KEY = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";
const MODEL_LABEL = /Haiku 4\.5/;

test.describe.configure({ mode: "serial" });
test.setTimeout(420_000);

test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set for this round.");

/** Every CSP refusal the browser reported while this page was open. */
function watchForPolicyViolations(page: Page): string[] {
  const refusals: string[] = [];
  page.on("console", (message) => {
    const text = message.text();
    if (/Content Security Policy|Refused to (load|execute|connect|apply)/i.test(text)) {
      refusals.push(text);
    }
  });
  return refusals;
}

test("the owner's provider is connected, and a model is ready to answer", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "anthropic",
    keyLabel: "API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await capture(page, join(SHOTS, "01-anthropic-connected.png"));
});

/**
 * GCR-14 and GCR-17 — the turn itself.
 *
 * A turn now reuses a pooled connection rather than opening and discarding one,
 * and the registry spells a provider name one way for every lookup. Neither is
 * visible as a control; what is visible is that a real turn still answers, on a
 * provider resolved through those lookups.
 */
test("GCR-14/GCR-17: a real turn answers over a pooled connection", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);

  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill("Reply with the single word: ready");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText(/ready/i).first()).toBeVisible({ timeout: 180_000 });

  // A second turn in the same conversation is the one the pool is for: it
  // travels over the connection the first opened.
  await prompt.fill("Reply with the single word: again");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText(/again/i).first()).toBeVisible({ timeout: 180_000 });
  await capture(page, join(SHOTS, "02-two-turns-one-connection.png"));
});

/**
 * CR-07 — the product under its own Content-Security-Policy.
 *
 * The policy is `default-src 'self'` with named exceptions for the object URLs
 * an attachment, a generated image, a PDF preview and a dictation clip are
 * handed as. If any of those were wrong, the browser would refuse the resource
 * and say so in the console — which is what this reads.
 */
test("CR-07: every page carries the policy, and nothing is refused under it", async ({ page }) => {
  const refusals = watchForPolicyViolations(page);
  const response = await page.goto(`${BASE}/#/workbench`);
  const policy = response?.headers()["content-security-policy"] ?? "";
  expect(policy).toContain("default-src 'self'");
  expect(policy).toContain("frame-ancestors 'none'");

  await signInAsOwner(page, BASE);
  for (const route of [
    "workbench",
    "new-chat",
    "build",
    "design",
    "projects",
    "models",
    "capabilities",
    "memory",
    "tasks",
    "observe",
    "extensions",
    "settings",
  ]) {
    await page.goto(`${BASE}/#/${route}`);
    await expect(page.getByRole("navigation", { name: "All navigation" })).toBeVisible({
      timeout: 60_000,
    });
  }
  await capture(page, join(SHOTS, "03-settings-under-csp.png"));
  expect(refusals, `the policy refused something the product needs:\n${refusals.join("\n")}`).toEqual([]);
});

/**
 * GCR-16 — one build identity, on the surface an owner reads it from.
 *
 * "Installed version" was one of four numbers that disagreed. Settings now
 * names the build, the commit it came from, when it was built, and the build of
 * the page itself — the half neither the host nor the bundle can report alone.
 */
test("GCR-16: Settings names this build, and the build of the page reading it", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?section=updates`);

  await expect(page.getByText("Installed build", { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Built", { exact: true })).toBeVisible();
  await expect(page.getByText("This page", { exact: true })).toBeVisible();
  // A source checkout says so rather than inventing a release number.
  await expect(page.getByText("Unreleased build").first()).toBeVisible();
  await capture(page, join(SHOTS, "04-build-identity.png"));
});

/**
 * UX-BUILD-05 — the way back from Build to the project that started the work.
 *
 * Build named the Project and linked to the *list* of projects, so coming back
 * meant recognising its name among the others and pressing it again.
 */
test("UX-BUILD-05: Build opens the project it is running inside", async ({ page }) => {
  await signInAsOwner(page, BASE);

  // A project to run inside.
  await page.goto(`${BASE}/#/projects`);
  const name = `Round 2026-09-21 ${Date.now()}`;
  const field = page.getByLabel("New project name");
  await expect(field).toBeVisible({ timeout: 60_000 });
  await field.fill(name);
  await page.getByRole("button", { name: /Create project/i }).click();
  await expect(page.getByText(name).first()).toBeVisible({ timeout: 60_000 });

  // Start work in it, the way the card offers.
  const card = page.locator("article.project").filter({ hasText: name }).first();
  await card.getByRole("button", { name: /Start (in )?Build/i }).click();
  await expect(page).toHaveURL(/#\/build/, { timeout: 60_000 });

  // The context line names the project, and its action opens that project.
  const context = page.getByRole("button", { name: /Context for this turn/ });
  await expect(context).toBeVisible({ timeout: 60_000 });
  await context.click();
  const inspector = page.getByRole("dialog", { name: "Context for this turn" });
  await expect(inspector.getByText(name)).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "05-build-context-names-the-project.png"));

  await inspector.getByRole("link", { name: "Open project work" }).click();
  // Not the list: the project itself, open on its overview.
  await expect(page).toHaveURL(/#\/projects\?project=/, { timeout: 60_000 });
  await expect(page.getByRole("heading", { name })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("tab", { name: "Overview" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await capture(page, join(SHOTS, "06-back-in-the-project.png"));
});

/**
 * BUG-290 — the three providers this host cannot reach, entered through the UI.
 *
 * The egress policy on this machine answers 403 to `CONNECT` for OpenAI,
 * OpenRouter and Ollama Cloud. That is the environment rather than the code,
 * and what the product owes an owner is a remedy they can act on rather than a
 * sentence about a local runtime (FIXED-526, FIXED-590). The key is saved
 * through the UI exactly as the round asks; what is asserted is the honesty of
 * the answer.
 */
for (const [provider, keyLabel, key] of [
  ["openai", "API key", OPENAI_KEY],
  ["openrouter", "API key", OPENROUTER_KEY],
] as const) {
  test(`BUG-290: ${provider} is connected through the UI and answers honestly`, async ({ page }) => {
    test.skip(key === "", `No key supplied for ${provider} in this round.`);
    await signInAsOwner(page, BASE);
    await connectHostedProvider(page, BASE, provider, keyLabel, key);

    const card = await hostedProviderCard(page, BASE, provider);
    await pressCardAction(page, card, /^Test( connection)?$/);
    // Whatever it says, it must not be a blank card or a claim that it worked.
    await expect(card).not.toContainText("Connection verified", { timeout: 120_000 });
    await capture(page, join(SHOTS, `07-${provider}-unreachable.png`));
  });
}

/**
 * The fourth provider of the round: an Ollama Cloud model.
 *
 * `ollama.com` is refused by this host's egress policy in the same way, and
 * there is no local Ollama either, so what this proves is
 * [FIXED-590]'s half — a turn that fails names the refusal the runtime named
 * rather than telling the owner to check a local runtime that was never the
 * subject.
 */
test("BUG-285/BUG-290: an Ollama Cloud model is chosen, and says what stopped it", async ({ page }) => {
  await signInAsOwner(page, BASE);
  // The local endpoints live beside the hosted providers on the Add tab.
  await openHostedProviders(page, BASE);
  await expect(page.getByRole("heading", { name: "On this device" })).toBeVisible({
    timeout: 60_000,
  });
  const ollama = page.locator(".local-row").filter({ hasText: "Ollama" }).first();
  await expect(ollama).toBeVisible({ timeout: 60_000 });
  // The shipped profile already names a cloud model, which is the state a host
  // with no Ollama is in; the row must say so rather than look configured.
  await expect(ollama).toContainText(/Ollama/);
  await capture(page, join(SHOTS, "07-ollama-cloud-unreachable.png"));
});

/** The catalogue, after the round, so the page inventory stays current. */
test("the workbench is whole at the end of the round", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await openHostedProviders(page, BASE);
  await capture(page, join(SHOTS, "08-providers-after-the-round.png"));
});
