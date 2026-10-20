/**
 * BUG-349, against a running host: the dial-time address guard, as the owner
 * meets it on the Models page.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `python -m raiker.api.serve --workspace <ws> --port 8765 --no-browser`.
 *   2. A hosted-looking test name that this machine's resolver answers with a
 *      private address, and that the host's proxy settings leave direct — for
 *      example `10.0.0.5 models.raiker-live.example` in `/etc/hosts` and the
 *      name appended to `NO_PROXY` for the server process. A proxied name is
 *      resolved by the proxy, so the guard does not see it (the plan's D2).
 *   3. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Model transport
 * guard"): MT-01 … MT-06.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";

import { capture } from "./capture";
import {
  checkModelReady,
  chooseModelForTurn,
  hostedProviderCard,
  keepModelAvailable,
  openProviderDetails,
  pressCardAction,
  signInAsOwner,
} from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE, sendTurn } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const PRIVATE_NAME = process.env.RAIKER_LIVE_PRIVATE_NAME ?? "models.raiker-live.example";
const SHOTS = "../../docs/screenshots/2026-10-20-model-transport-guard";

/** Connect (or reconnect) the OpenAI-compatible card to *endpoint*. */
async function pointCustomEndpoint(
  page: Page,
  endpoint: string,
  linkLocal = false,
  key = "",
): Promise<Locator> {
  const card = await hostedProviderCard(page, BASE, "OpenAI-compatible");
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
  } else {
    await openProviderDetails(page, card);
    await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  }
  const dialog = page.locator(".signin-overlay");
  await dialog.getByPlaceholder("http://127.0.0.1:8000/v1").fill(endpoint);
  if (key) await dialog.getByPlaceholder("(optional)").fill(key);
  const tick = dialog.getByTestId("allow-link-local");
  if ((await tick.isChecked()) !== linkLocal) await tick.setChecked(linkLocal);
  await page.locator(".signin-connect").click();
  await expect(page.locator(".signin-overlay")).toHaveCount(0, { timeout: 60_000 });
  const close = page.getByRole("button", { name: "Close model details" });
  if (await close.isVisible().catch(() => false)) await close.click();
  return hostedProviderCard(page, BASE, "OpenAI-compatible");
}

async function testCard(page: Page, card: Locator): Promise<void> {
  await pressCardAction(page, card, /^Test( connection)?$/);
}

test("MT-01 — a hosted provider is dialled directly and says so", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  await card.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByLabel("Anthropic API key").fill(KEY);
  if (WORKSPACE_ID) {
    await page.getByRole("button", { name: "Advanced" }).click();
    await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE_ID);
  }
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  await keepModelAvailable(page, card, MODEL);
  const pinned = await hostedProviderCard(page, BASE, "Anthropic");
  // A real catalogue and a one-token preflight through the pinned dial.
  await checkModelReady(page, pinned);
  await expect(pinned.getByText(/can reach/i).first()).toBeVisible();
  // The route is stated: this host's NO_PROXY covers api.anthropic.com.
  await expect(pinned.getByText(/Direct connection|Through your proxy/).first()).toBeVisible();
  const posture = page.getByLabel("Off-machine provider posture");
  await expect(posture.getByTestId("proxy-posture")).toHaveText(/^(Yes|No) — /);
  await capture(page, `${SHOTS}/01-anthropic-direct-and-ready.png`, pinned);
  await capture(page, `${SHOTS}/02-posture-through-your-proxy.png`, posture);
  expect(await page.content()).not.toContain(KEY);
});

test("MT-02 — a real turn answers through the pinned connection", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku|claude/i);
  await sendTurn(page, "Reply with exactly the word: pinned");
  await expect(page.locator(".message-bubble-raiker").last()).toContainText(/pinned/i, {
    timeout: 180_000,
  });
  await capture(page, `${SHOTS}/03-turn-answered.png`);
});

test("MT-03 — a hosted name that resolves to a private address is refused by name", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  // A hosted endpoint needs a key; this one is a sentinel that must never be
  // sent anywhere, and the guard is what makes sure of it.
  const card = await pointCustomEndpoint(page, `https://${PRIVATE_NAME}/v1`, false, "sk-live-sentinel");
  await testCard(page, card);
  await expect(
    card.getByText(/resolved to a private, loopback or link-local address/i).first(),
  ).toBeVisible({ timeout: 60_000 });
  // A policy answer with its own reason: not "enable its gate", not "unreachable".
  await expect(card.getByText(/enable its gate/i)).toHaveCount(0);
  await expect(card.getByText(/could not be reached/i)).toHaveCount(0);
  await capture(page, `${SHOTS}/04-hosted-name-private-address-refused.png`, card);
});

test("MT-04 — a link-local endpoint needs the owner's tick", async ({ page }) => {
  // Nothing routes to 169.254.10.10 here, so the opted-in dial waits out the
  // profile's own connect timeout (120 s) before the card can say so.
  test.setTimeout(480_000);
  await signInAsOwner(page, BASE);
  let card = await pointCustomEndpoint(page, "http://169.254.10.10:8000/v1");
  await testCard(page, card);
  await expect(card.getByText(/link-local address/i).first()).toBeVisible({ timeout: 60_000 });
  await capture(page, `${SHOTS}/05-link-local-refused.png`, card);
  // With the opt-in, the same address is dialled: what comes back is about the
  // server (nothing listens there), not a policy refusal.
  card = await pointCustomEndpoint(page, "http://169.254.10.10:8000/v1", true);
  await testCard(page, card);
  await expect(card.getByText(/Raiker refused to connect/i)).toHaveCount(0, { timeout: 60_000 });
  await expect(
    card.getByText(/could not be reached|not reachable|did not answer|not running|could not reach/i).first(),
  ).toBeVisible({ timeout: 200_000 });
  await capture(page, `${SHOTS}/06-link-local-opted-in-dialled.png`, card);
});

test("MT-05 — a cloud metadata address is never a model destination", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "OpenAI-compatible");
  await openProviderDetails(page, card);
  await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  const dialog = page.locator(".signin-overlay");
  await dialog.getByPlaceholder("http://127.0.0.1:8000/v1").fill("http://169.254.169.254/v1");
  // Even with the link-local opt-in ticked: there is no setting for this.
  await dialog.getByTestId("allow-link-local").setChecked(true);
  await page.locator(".signin-connect").click();
  // Refused when it is saved, before anything is dialled — in the dialog,
  // where the owner can still see what they typed.
  const refusal = dialog.getByRole("alert");
  await expect(refusal.getByText(/cloud metadata service/i)).toBeVisible({ timeout: 60_000 });
  await expect(refusal.getByText("model_dial_refused:metadata_address")).toBeVisible();
  await capture(page, `${SHOTS}/07-metadata-refused.png`, dialog.getByRole("dialog"));
  await dialog.getByRole("button", { name: "Cancel" }).click();
});

test("MT-06 — the opt-in in the dialog, dark theme at 390 px", async ({ browser }) => {
  test.setTimeout(240_000);
  const context = await browser.newContext({ viewport: { width: 390, height: 900 }, colorScheme: "dark" });
  const page = await context.newPage();
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "OpenAI-compatible");
  await openProviderDetails(page, card);
  await page.getByRole("button", { name: "Reconnect", exact: true }).click();
  const tick = page.getByTestId("allow-link-local");
  // Prefilled from the saved connection, so re-saving keeps the owner's choice.
  await expect(tick).toBeChecked();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await capture(page, `${SHOTS}/08-dialog-link-local-dark-390.png`);
  await page.getByRole("button", { name: "Cancel" }).click();
  // Leave the workspace as it was: the custom endpoint disconnected. Details is
  // still open behind the dialog that was cancelled, and Disconnect is in it.
  await expect(page.locator(".signin-overlay")).toHaveCount(0, { timeout: 30_000 });
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: /^Disconnect/ }).first().click();
  await expect((await hostedProviderCard(page, BASE, "OpenAI-compatible")).getByText("Not connected")).toBeVisible({
    timeout: 60_000,
  });
  await context.close();
});
