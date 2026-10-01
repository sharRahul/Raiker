/**
 * OPT-16 — what every live spec used to declare for itself.
 *
 * A hundred and ten specs wrote out the host's address, seventy-nine of them
 * with no way to point it anywhere else; fifty-eight read the Anthropic key from
 * the environment under one of two names; forty-one spelled out the same pinned
 * model; and thirty-eight repeated the same five-line connect-and-pin call. Each
 * copy was right when it was written. What a copy cannot do is change once.
 *
 * These are the product-level steps and the round's fixtures, not DOM details:
 * where the host is, which key and model the round was given, connecting that
 * provider the way an owner does, and sending one turn. The steps themselves
 * stay in `hosted-provider.ts`, which already owns how the Models page works.
 *
 * A spec that is *about* a different host — a first-run instance, a second
 * port, a release build — keeps its own address, because that difference is
 * what it tests.
 */
import { expect, type Locator, type Page } from "@playwright/test";

import { useHostedModel } from "./hosted-provider";

/** The running `raiker-web` a live round drives. */
export const LIVE_BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";

/** The Anthropic key the round was given. Read here, never written into a spec. */
export const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";

/** The model a round pins unless it says otherwise. */
export const ANTHROPIC_MODEL =
  process.env.RAIKER_LIVE_ANTHROPIC_MODEL ??
  process.env.RAIKER_LIVE_MODEL ??
  "claude-haiku-4-5-20251001";

/**
 * Connect Anthropic through Models, pin `model`, and leave it ready to answer.
 *
 * Fails first, and by name, when the round has no key: a spec that typed an
 * empty key into the dialog would fail three steps later on a readiness check,
 * reading as a provider that refused rather than a round that was not given one.
 */
export async function useAnthropic(
  page: Page,
  base: string = LIVE_BASE,
  model: string = ANTHROPIC_MODEL,
): Promise<Locator> {
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  return useHostedModel(page, base, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model,
  });
}

/**
 * Type one message into a composer and send it.
 *
 * Returns once the send has been accepted — the composer's **Send** has been
 * pressed — not once the answer has arrived; what "answered" means differs per
 * spec, so each waits for its own evidence.
 */
export async function sendTurn(
  page: Page,
  text: string,
  composerLabel = "Message composer",
): Promise<Locator> {
  const composer = page.getByRole("group", { name: composerLabel });
  await composer.getByRole("textbox").first().fill(text);
  await composer.getByRole("button", { name: /^Send/ }).click();
  return composer;
}
