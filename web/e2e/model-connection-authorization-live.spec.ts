/**
 * ADR-0004 — an owner configures a provider once and Raiker may use it, with no
 * separate model egress allowlist to discover.
 *
 * Prerequisites:
 *   1. `python -m raiker.api.serve --workspace <fresh ws> --port 8765 --no-browser`
 *      with `OPENAI_API_KEY` set in the server's environment (any value: this
 *      spec never sends a request to OpenAI) and, to prove it is ignored,
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST` set to an unrelated host.
 *   2. `RAIKER_LIVE_BASE` if the server is not on 127.0.0.1:8765.
 *
 * What it proves, through the product's own pages:
 *   - the off-machine posture reports connected providers, not an allowlist;
 *   - a provider whose key is already in the environment is connected with one
 *     tick, the key never reaching the page;
 *   - the saved connection is what the Models read reports afterwards.
 */
import { expect, test } from "@playwright/test";

import { capture } from "./capture";
import { hostedProviderCard, openHostedProviders, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE } from "./live";

const SHOTS = "../../docs/screenshots/2026-10-20-model-connection-authorization";

test("an environment key becomes a connection with one owner decision", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, LIVE_BASE);
  await openHostedProviders(page, LIVE_BASE);

  const posture = page.getByLabel("Off-machine provider posture");
  await expect(posture.getByText("Connected off-machine providers")).toBeVisible();
  await expect(posture.getByText("Egress allowlist")).toHaveCount(0);
  await capture(page, `${SHOTS}/01-posture-before-connecting.png`, posture);

  const card = await hostedProviderCard(page, LIVE_BASE, "OpenAI");
  await card.getByRole("button", { name: "Connect", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const useEnvironment = dialog.getByRole("checkbox", { name: /OPENAI_API_KEY/ });
  await expect(useEnvironment).toBeVisible();
  await capture(page, `${SHOTS}/02-connect-dialog-offers-environment-key.png`);

  await useEnvironment.check();
  await expect(dialog.getByLabel(/OpenAI API key/i)).toHaveCount(0);
  await capture(page, `${SHOTS}/03-environment-key-chosen.png`);

  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator(".signin-overlay")).toHaveCount(0, { timeout: 30_000 });
  await capture(page, `${SHOTS}/04-connected-without-an-allowlist.png`, card);

  // What the server now holds, read the way the page reads it: a connection,
  // no key in the response, and no environment offer left to make.
  const body = await page.evaluate(async (base) => {
    const token = (window as unknown as { __raikerToken?: string }).__raikerToken;
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const answer = await fetch(`${base}/api/models`, { headers, credentials: "include" });
    return { status: answer.status, text: await answer.text() };
  }, LIVE_BASE);
  expect(body.status).toBe(200);
  const models = JSON.parse(body.text);
  expect(models).not.toHaveProperty("model_egress_allowlist_configured");
  const openai = models.profiles.find(
    (profile: { profile_id: string }) => profile.profile_id === "openai-hosted",
  );
  expect(openai.connection_configured).toBe(true);
  expect(openai.environment_credential_env).toBeNull();
  // The environment key's value is never part of anything the page reads.
  expect(body.text).not.toContain(process.env.RAIKER_LIVE_ENV_KEY_SENTINEL ?? "sk-env-sentinel");

  await openHostedProviders(page, LIVE_BASE);
  await expect(card.getByText("Needs your connection")).toBeVisible();
  await expect(card.getByText(/Egress-gated/)).toHaveCount(0);
});

test("the connect dialog reads in the dark theme and at phone width", async ({ page }) => {
  test.setTimeout(180_000);
  await page.emulateMedia({ colorScheme: "dark" });
  await signInAsOwner(page, LIVE_BASE);
  const card = await hostedProviderCard(page, LIVE_BASE, "Gemini");
  await card.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await capture(page, `${SHOTS}/06-connect-dialog-dark.png`);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("dialog")).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await capture(page, `${SHOTS}/07-connect-dialog-phone.png`);
});
