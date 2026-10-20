/**
 * ADR-0004, against a real provider: a saved connection is the whole of the
 * setup, revocation still wins, and disconnecting takes the provider away.
 *
 * Prerequisites:
 *   1. `python -m raiker.api.serve --workspace <fresh ws> --port 8765 --no-browser`
 *      with **no** model egress variable needed — set
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST` to an unrelated host to prove it is ignored.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in the environment of this run only.
 *      The key is typed into the product's own dialog; no key is written here.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Model connection
 * authorization"): LC-01 … LC-05.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";

import { capture } from "./capture";
import {
  checkModelReady,
  chooseModelForTurn,
  hostedProviderCard,
  keepModelAvailable,
  openHostedProviders,
  openProviderDetails,
  signInAsOwner,
} from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE, sendTurn } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = "../../docs/screenshots/2026-10-20-model-connection-anthropic";

test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");

async function setHostedModels(page: Page, on: boolean, reason: string): Promise<void> {
  await page.goto(`${BASE}/#/capabilities`);
  await page.getByLabel("Search capabilities", { exact: true }).waitFor({ timeout: 60_000 });
  await page.getByLabel("Search capabilities", { exact: true }).fill("Hosted models");
  const card = page.locator(".cap.card").filter({ hasText: "Hosted models" }).first();
  await expect(card).toBeVisible({ timeout: 60_000 });
  const toggle = card.locator("button.cap-toggle");
  if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();
  const action = card.getByRole("button", { name: on ? "Turn on" : "Turn off", exact: true });
  if (!(await action.isVisible().catch(() => false))) return;
  await action.click();
  const dialog = page.getByRole("dialog");
  if (await dialog.isVisible({ timeout: 5_000 }).catch(() => false)) {
    const reasonField = dialog.getByLabel("Reason (required)");
    if (await reasonField.isVisible().catch(() => false)) await reasonField.fill(reason);
    const token = dialog.getByLabel(/Confirmation token/);
    if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
    const ack = dialog.getByLabel(/reviewed the threat model/);
    if (await ack.isVisible().catch(() => false)) await ack.check();
    await dialog.getByRole("button", { name: /Confirm change|Turn off|Turn on/ }).last().click();
    await expect(dialog).toBeHidden({ timeout: 60_000 });
  }
}

async function anthropicCard(page: Page): Promise<Locator> {
  return hostedProviderCard(page, BASE, "Anthropic");
}

test("LC-01 — connecting Anthropic in the UI is the whole setup", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  const card = await anthropicCard(page);
  await card.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByLabel("Anthropic API key").fill(KEY);
  if (WORKSPACE_ID) {
    await page.getByRole("button", { name: "Advanced" }).click();
    await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE_ID);
  }
  await capture(page, `${SHOTS}/01-connect-anthropic.png`, page.getByRole("dialog"));
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  await keepModelAvailable(page, card, MODEL);
  const pinned = await anthropicCard(page);
  await checkModelReady(page, pinned);
  await expect(pinned.getByText(/can reach/i).first()).toBeVisible();
  await capture(page, `${SHOTS}/02-anthropic-ready-without-allowlist.png`, pinned);
  // The key never comes back to the page in any read.
  expect(await page.content()).not.toContain(KEY);
});

test("LC-02 — a real turn answers through the saved connection", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku|claude/i);
  await sendTurn(page, "Reply with exactly the word: connected");
  // The answer, not the prompt that contains the same word.
  await expect(page.locator(".message-bubble-raiker").last()).toContainText(/connected/i, {
    timeout: 180_000,
  });
  await capture(page, `${SHOTS}/03-turn-answered.png`);
});

test("LC-03 — turning Hosted models off refuses the saved connection", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  // Before revoking: Permissions says the gate is on, and why.
  await page.goto(`${BASE}/#/capabilities`);
  await page.getByLabel("Search capabilities", { exact: true }).fill("Hosted models");
  const row = page.locator(".cap.card").filter({ hasText: "Hosted models" }).first();
  await row.locator("button.cap-toggle").click();
  await expect(row.getByText(/on because you connected a provider/i)).toBeVisible({ timeout: 30_000 });
  await expect(row.getByText("On by connection")).toBeVisible();
  await expect(row.getByRole("button", { name: "Turn off", exact: true })).toBeVisible();
  await capture(page, `${SHOTS}/04a-permissions-on-by-connection.png`, row);
  await setHostedModels(page, false, "LC-03 revocation check");
  await expect(
    page.locator(".cap.card").filter({ hasText: "Hosted models" }).first().getByText(/cannot use this/),
  ).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/04-hosted-models-off.png`);
  await openHostedProviders(page, BASE);
  const posture = page.getByLabel("Off-machine provider posture");
  await expect(posture.getByText(/^Off$/).first()).toBeVisible({ timeout: 30_000 });
  const card = await anthropicCard(page);
  await checkModelReady(page, card).catch(() => undefined);
  // A policy refusal, told apart from a connection failure.
  await expect(card.getByText(/Policy blocked|blocked by the current model policy/).first()).toBeVisible({
    timeout: 60_000,
  });
  await capture(page, `${SHOTS}/05-revoked-card.png`, card);
  await setHostedModels(page, true, "LC-03 restore");
});

test("LC-04 — disconnecting takes the provider away", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  const card = await anthropicCard(page);
  await openProviderDetails(page, card);
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: /^Disconnect/ }).first().click();
  const after = await anthropicCard(page);
  await expect(after.getByText("Not connected")).toBeVisible({ timeout: 60_000 });
  await expect(
    page.getByLabel("Off-machine provider posture").getByText("Connected off-machine providers"),
  ).toBeVisible();
  await capture(page, `${SHOTS}/06-disconnected.png`, after);
});
