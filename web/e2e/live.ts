/**
 * What every live spec needs before its first assertion: where the host is,
 * which provider keys this round was given, and a page already signed in.
 *
 * OPT-16. A hundred and nine specs each declared the host as their own constant
 * — seventy-nine of them hard-coded, so a round could not point the suite at an
 * instance on another port — and sixty-odd read the same three key variables
 * under four different names. One declaration here; a spec imports it.
 *
 * Specs that are *about* a different instance (a first-run workspace on 8766, a
 * release build on 8768) keep their own base, because sharing this one would
 * point them at the wrong host.
 */
import { expect, test as base, type Locator, type Page } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";

/** The live host a round runs against; `RAIKER_LIVE_BASE` overrides it. */
export const LIVE_BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";

/**
 * The hosted-provider keys this round was given. Empty when absent, so a spec
 * can `test.skip(!LIVE_KEYS.openai, "…")` and say why rather than fail.
 */
export const LIVE_KEYS = {
  anthropic: process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "",
  openrouter: process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "",
  openai: process.env.RAIKER_LIVE_OPENAI_KEY ?? "",
} as const;

/**
 * `test` with an `ownerPage`: a page signed in as the suite's owner on
 * `LIVE_BASE`, past the setup wizard. A spec about signing in uses `page`.
 */
export const test = base.extend<{ ownerPage: Page }>({
  ownerPage: async ({ page }, use) => {
    await signInAsOwner(page, LIVE_BASE);
    await use(page);
  },
});

/**
 * Send one message from the open Chat composer and return Raiker's answer.
 *
 * Ten specs each carried this as their own `ask()`. It waits for the turn
 * control to go away — the product's own "this turn is over" — and then for a
 * new answer bubble, so a turn that ends without answering fails here, naming
 * the wait, instead of three assertions later.
 */
export async function runChatTurn(
  page: Page,
  prompt: string,
  { timeout = 240_000 }: { timeout?: number } = {},
): Promise<Locator> {
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  const answers = page.locator(".message-bubble-raiker");
  const before = await answers.count();
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout });
  await expect.poll(async () => answers.count(), { timeout: 60_000 }).toBeGreaterThan(before);
  return answers.last();
}

export { expect };
