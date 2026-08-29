/**
 * `Stop` fires the same way whichever provider answered (BUG-223).
 *
 * `bug-223-turn-end-hooks-live.spec.ts` proves the event reaches the durable
 * record on one hosted provider. This one asks the question that matters for a
 * product whose whole premise is that the owner chooses the backend: is the
 * lifecycle event a property of the *runtime*, or did it get wired somewhere a
 * particular provider adapter happens to pass through?
 *
 * `_finalize_turn` is common to every provider, so the expected answer is yes —
 * and an expected answer is exactly the kind that goes untested until it is
 * wrong. Each provider is connected through the product's own dialog, a real
 * turn is sent, and the `hook_executed` count is required to rise by at least
 * one for that turn.
 *
 * A provider whose key is not supplied is **skipped by name**, not silently
 * passed: a green run that tested one provider must not look like a green run
 * that tested four.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { dismissFirstRunModelSetup, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? process.cwd();
const PASSWORD = "Turn-end-providers-1!";

const PROVIDERS = [
  {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "",
    model: "claude-haiku-4-5-20251001",
  },
  {
    provider: "OpenAI",
    keyLabel: "OpenAI API key",
    key: process.env.RAIKER_LIVE_OPENAI_KEY ?? "",
    model: process.env.RAIKER_LIVE_OPENAI_MODEL ?? "gpt-4o-mini",
  },
  {
    provider: "OpenRouter",
    keyLabel: "OpenRouter API key",
    key: process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "",
    model: process.env.RAIKER_LIVE_OPENROUTER_MODEL ?? "openai/gpt-4o-mini",
  },
] as const;

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

function writeStopHook() {
  const dir = join(WORKSPACE, "config");
  mkdirSync(dir, { recursive: true });
  writeFileSync(
    join(dir, "hooks.json"),
    JSON.stringify({
      schema_version: "1.0",
      hooks: {
        Stop: [
          {
            matcher: "*",
            handlers: [
              { id: "turn-end-watch", type: "builtin", builtin: "block_destructive_shell" },
            ],
          },
        ],
      },
    }),
    "utf-8",
  );
}

async function signIn(target: Page) {
  await target.goto(`${BASE}/#/workbench`);
  await expect(target.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const confirm = target.getByLabel("Confirm password");
  await target.getByLabel("Username").fill("owner");
  await target.getByLabel("Password", { exact: true }).fill(PASSWORD);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await target.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await target.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  const workbench = target.getByRole("heading", { name: /Welcome to your Work Dashboard/ });
  await expect(
    target.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(target);
  await expect(workbench).toBeVisible({ timeout: 30_000 });
}

/**
 * How many hook executions the Hooks tab is showing right now.
 *
 * Read through the page rather than by calling `/api/hooks` directly: the bearer
 * token is deliberately never persisted, so a `fetch` from `page.evaluate` is
 * unauthenticated and returns nothing — which reads as "zero executions" and
 * would have made this assertion fail for a reason that has nothing to do with
 * hooks. Counting what the owner can actually see is also the stronger claim.
 */
async function hookExecutions(): Promise<number> {
  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  const activity = page
    .getByRole("heading", { name: "Recent hook activity" })
    .locator("xpath=ancestor::section[1]");
  await expect(activity).toBeVisible({ timeout: 30_000 });
  return await activity.getByText("executed", { exact: true }).count();
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  writeStopHook();
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  await signIn(page);
});

test.afterAll(async () => {
  await context?.close();
  rmSync(join(WORKSPACE, "config", "hooks.json"), { force: true });
});

/**
 * The same claim for a **local** provider, taken through the Local tab.
 *
 * A hosted provider and a local one reach `_finalize_turn` by different
 * adapters, and "local" is the case Raiker exists for — a lifecycle event that
 * only fired when a hosted API answered would be the wrong half working.
 *
 * Skipped by name when no Ollama daemon is reachable, for the same reason the
 * hosted entries are: a run that tested nothing must not read like one that
 * tested everything.
 */
test("Stop fires on a turn answered by a local Ollama model", async () => {
  test.setTimeout(420_000);
  const model = process.env.RAIKER_LIVE_OLLAMA_MODEL ?? "";
  test.skip(model === "", "no RAIKER_LIVE_OLLAMA_MODEL supplied — skipped by name");

  await page.goto(`${BASE}/#/models?tab=local`);
  // By its heading, not by `hasText`. Several rows mention Ollama in their help
  // text, and the first `hasText` match was a different provider's row whose
  // Select button this test then waited seven minutes for.
  const row = page
    .locator(".local-row")
    .filter({ has: page.getByRole("heading", { name: "Ollama", exact: true }) })
    .first();
  await expect(row).toBeVisible({ timeout: 30_000 });

  // A row that is already the serving provider has no Select button — that is
  // what "selected" means here — so selecting is conditional rather than assumed.
  const select = row.getByRole("button", { name: "Select", exact: true });
  if (await select.isVisible().catch(() => false)) await select.click();

  await row.getByRole("button", { name: /Choose model…|Change model…/ }).click();
  // The catalogue is what the daemon actually published. Falling back to the
  // free-text field would let this pass against a model Ollama does not have.
  const catalogue = row.getByLabel("Available models");
  await expect(catalogue).toBeVisible({ timeout: 60_000 });
  await catalogue.selectOption(model);
  await row.getByRole("button", { name: "Use model" }).click();
  await expect(row.locator("code")).toBeVisible({ timeout: 60_000 });

  await page.goto(`${BASE}/#/models?tab=local`);
  const pinned = page
    .locator(".local-row")
    .filter({ has: page.getByRole("heading", { name: "Ollama", exact: true }) })
    .first();
  await pinned.getByRole("button", { name: "Test", exact: true }).click();
  await expect(
    pinned.getByText(/can reach|cannot execute|not reachable|rejected|no credit|no quota/i),
  ).toBeVisible({ timeout: 180_000 });

  const before = await hookExecutions();

  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill("Reply with exactly the word: acknowledged.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 360_000 });

  expect(await hookExecutions()).toBeGreaterThan(before);

  await capture(page, join(SHOTS, "bug-223-stop-ollama.png"));
});

for (const entry of PROVIDERS) {
  test(`Stop fires on a turn answered by ${entry.provider}`, async () => {
    test.setTimeout(360_000);
    test.skip(
      entry.key === "",
      `no key supplied for ${entry.provider} — skipped by name rather than passing quietly`,
    );

    await useHostedModel(page, BASE, {
      provider: entry.provider,
      keyLabel: entry.keyLabel,
      key: entry.key,
      model: entry.model,
    });

    const before = await hookExecutions();

    await page.goto(`${BASE}/#/new-chat`);
    const composer = page.getByPlaceholder("How can I help you today?");
    await expect(composer).toBeVisible({ timeout: 30_000 });
    await composer.fill("Reply with exactly the word: acknowledged.");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });

    // The count, not merely "some activity exists": an earlier provider's turn
    // already left `hook_executed` rows, so presence would pass without this
    // provider having fired anything.
    expect(await hookExecutions()).toBeGreaterThan(before);

    await capture(page, join(SHOTS, `bug-223-stop-${entry.provider.toLowerCase()}.png`));
  });
}
