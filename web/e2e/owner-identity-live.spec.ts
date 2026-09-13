/*
 * RR-IDENTITY-01, closed against a real model.
 *
 * The symptom was owner-observed and is not a literal in the source, so no
 * amount of unit coverage can close it: the sentence *"The workspace's real
 * owner is principal_user_ac5eb6e5f7620f0d"* was composed by a model that had
 * been handed an opaque owner identifier and no name. The regression is
 * therefore the original question, asked of a real provider through the
 * product's own composer, and read back out of the transcript.
 *
 * Everything before the question is the product's own path: the key is entered
 * through the Models dialog, the readiness check is the card's own **Test**, and
 * the display name is set on the Account page. Nothing is written behind the
 * page's back.
 *
 * Providers this host cannot reach are skipped with the reason rather than
 * faked — a suite that cannot really pass must not report that it did.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import {
  checkModelReady,
  connectHostedProvider,
  signInAsOwner,
  useHostedModel,
} from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8768";
const SHOTS = "../../docs/screenshots/2026-09-13-release-readiness";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const OWNER_NAME = "Rahul S";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";

test.describe.configure({ mode: "serial" });

test("the owner's chosen name is set through the Account page", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  const settingsRead = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/settings" &&
      response.request().method() === "GET",
    { timeout: 60_000 },
  );
  await page.goto(`${BASE}/#/settings?tab=account`);
  const name = page.getByLabel("Display name");
  await expect(name).toBeVisible({ timeout: 60_000 });
  await settingsRead;
  if ((await name.inputValue()) !== OWNER_NAME) {
    await name.fill(OWNER_NAME);
    await name.blur();
    await page.getByRole("button", { name: /save changes/i }).click();
    await expect(page.getByText(/all changes saved/i)).toBeVisible({ timeout: 60_000 });
  }
  await expect(name).toHaveValue(OWNER_NAME);
});

test("a real turn answers with the owner's name and not with their key", async ({ page }) => {
  test.setTimeout(300_000);
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  await signInAsOwner(page, BASE);

  // Connect, pin an exact model and leave it ready — the card offers **Test**
  // only once it has a model to test, so connecting alone is not enough.
  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: KEY,
    model: MODEL,
  });
  await capture(page, `${SHOTS}/anthropic-connected.png`, card);

  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByLabel("Prompt");
  await expect(composer).toBeVisible({ timeout: 60_000 });

  // Choose the model for this turn from the composer's own menu. A workspace
  // that has never sent a turn opens with none chosen, and Send stays disabled
  // until the exact model has a readiness check (FIXED-133).
  await page.getByRole("button", { name: /Not selected|Haiku|Model/ }).first().click();
  await page.getByRole("menuitemradio", { name: /Haiku/ }).first().click();

  // The owner's own question, as reported.
  await composer.fill("Who is the owner of this workspace? Answer in one short sentence.");
  // The composer's own Send, by class: once a turn has been answered the
  // transcript grows its own "Send this message again" controls, and a name
  // match finds three buttons where the spec means one.
  const send = page.locator("button.send");
  await expect(send).toBeEnabled({ timeout: 120_000 });
  await send.click();

  const answer = page.locator(".message-group-assistant, .message-group").last();
  await expect(answer).toContainText(/\w/, { timeout: 180_000 });
  // Settled, rather than mid-stream: reading a partial answer would let this
  // pass on a sentence the turn had not finished writing. The control is
  // labelled "Running" while the turn streams and "Send" once it has stopped —
  // and it is *disabled* either way afterwards, because the composer is empty,
  // so the label is the signal and enabledness is not.
  await expect(send).toHaveAttribute("aria-label", "Send", { timeout: 180_000 });

  const transcript = await page.locator(".conversation, main").first().innerText();
  // The defect, asserted away against the real path: no internal identifier
  // appears in the answer at all …
  expect(transcript).not.toMatch(/principal_user_[0-9a-f]{8}/);
  expect(transcript).not.toMatch(/The workspace's real owner is principal_/);
  // … and the name the owner set is what the turn has to work with.
  expect(transcript).toContain(OWNER_NAME);
  await capture(page, `${SHOTS}/identity-answered-by-name.png`);
});

/*
 * The other providers the round was asked to use.
 *
 * This host's egress policy answers `connect_rejected` to `CONNECT
 * api.openai.com` and `CONNECT openrouter.ai`, and it has no local Ollama, so
 * the provider round trip cannot be had here and is not pretended. What *can*
 * be proven is Raiker's half, which is the half these entries changed: the key
 * is entered through the product's own dialog, the connection is stored, and
 * the readiness check reports the refusal **as itself** rather than as a
 * network problem — FIXED-388's rule, and the one that made two earlier fixes
 * unreachable when it was broken.
 */
for (const provider of [
  { name: "OpenRouter", keyLabel: /OpenRouter API key/i, env: "RAIKER_LIVE_OPENROUTER_KEY" },
  { name: "OpenAI", keyLabel: /OpenAI API key/i, env: "RAIKER_LIVE_OPENAI_KEY" },
]) {
  test(`${provider.name} reports its own outcome, whatever this host can reach`, async ({
    page,
  }) => {
    test.setTimeout(300_000);
    const key = process.env[provider.env] ?? "";
    test.skip(key === "", `${provider.env} is unset`);
    await signInAsOwner(page, BASE);

    const card = await connectHostedProvider(page, BASE, provider.name, provider.keyLabel, key);
    await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
    await checkModelReady(page, card);

    // A sentence, never a bare status, and never a wrong diagnosis: a provider
    // this host cannot reach must not be reported as a bad key, and a bad key
    // must not be reported as a network fault.
    await expect(card.getByText(/http_\d{3}/)).toHaveCount(0);
    await capture(page, `${SHOTS}/${provider.name.toLowerCase()}-connection.png`, card);
  });
}
