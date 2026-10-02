/**
 * The 2026-10-02 round: every ordinary route described and called through the
 * generated client (OPT-01/OPT-02 Stage B), and what describing them found.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, with
 * Anthropic connected through Models from `RAIKER_LIVE_ANTHROPIC_KEY` — the key
 * typed into the Connect dialog, never written here. The last test turns on MFA,
 * so it runs last: an account with MFA asks for a code at every unlock.
 */
import { createHmac } from "node:crypto";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { DESTINATIONS, settled } from "./destinations";
import {
  OWNER_CREDENTIALS,
  chooseModelForTurn,
  enableCapability,
  refreshHostedReadiness,
  signInAsOwner,
} from "./hosted-provider";
import { LIVE_BASE, sendTurn, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-02-contract-round");
const HAIKU = /Haiku 4\.5/i;

test.describe.configure({ mode: "serial" });

/** The current RFC 6238 code for a base32 secret — what an authenticator app shows. */
function totp(secret: string, at = Date.now()): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const char of secret.replace(/=+$/, "").toUpperCase()) {
    bits += alphabet.indexOf(char).toString(2).padStart(5, "0");
  }
  const key = Buffer.from(bits.match(/.{8}/g)!.map((byte) => parseInt(byte, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 30_000)));
  const digest = createHmac("sha1", key).update(counter).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const value = (digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return value.toString().padStart(6, "0");
}

function watchFailures(page: Page): { failures: string[]; consoleErrors: string[] } {
  const failures: string[] = [];
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 400) {
      failures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  return { failures, consoleErrors };
}

/** Hosts this container cannot reach; their refusals are the network's, not Raiker's. */
const UNREACHABLE = /huggingface|openrouter|ollama|503/i;

test("Anthropic connects through Models, and a real Chat turn answers", async ({ page }) => {
  test.setTimeout(300_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await useAnthropic(page, BASE);
  await capture(page, join(SHOTS, "01-anthropic-connected.png"));

  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, HAIKU);
  const answers = page.locator(".message-bubble-raiker");
  const before = await answers.count();
  await sendTurn(page, "In one sentence: what is a governed agent?");
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
  await expect.poll(async () => answers.count(), { timeout: 60_000 }).toBeGreaterThan(before);
  await expect(answers.last()).not.toBeEmpty();
  await capture(page, join(SHOTS, "02-chat-answer.png"));
  expect(seen.failures.filter((line) => !UNREACHABLE.test(line))).toEqual([]);
});

test("Models says Design can research but not draw, and offers the fix", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/models`);
  await settled(page);
  // Chat's choice is Chat's; Design follows the global model, so choose one.
  const global = page.getByRole("combobox", { name: "Global model" });
  const haiku = (await global.locator("option").allTextContents()).find((label) => HAIKU.test(label));
  expect(haiku, "Haiku is offered as the global model").toBeTruthy();
  await global.selectOption({ label: haiku! });
  // A selection change invalidates the profile's readiness by rule, so check
  // the model again, as the overview's Fix asks.
  await refreshHostedReadiness(page, BASE, "Anthropic");
  await page.goto(`${BASE}/#/models`);
  await settled(page);
  await expect(page.getByText("Research only")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: "Connect an image provider" })).toBeVisible();
  await capture(page, join(SHOTS, "03-models-design-research-only.png"));
});

test("Design's Research reaches the turn and answers", async ({ page }) => {
  test.setTimeout(300_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await enableCapability(page, BASE, "Web fetch", "Live round: Design research");
  await page.goto(`${BASE}/#/design`);
  const composer = page.getByRole("group", { name: "Image composer" });
  await expect(composer).toBeVisible({ timeout: 60_000 });
  await composer.getByRole("textbox").first().fill("a timber footbridge over a narrow river");
  await page.getByRole("button", { name: "Tools" }).first().click();
  await page.getByRole("menu", { name: "Tools" }).getByRole("menuitem", { name: "Search the web" }).click();

  const research = page.getByTestId("design-research");
  await expect(research).toBeVisible({ timeout: 30_000 });
  await expect(research.getByText("Reading sources…")).toBeHidden({ timeout: 240_000 });
  await expect(research.getByRole("alert")).toHaveCount(0);
  await expect(research.locator(".research-body")).not.toBeEmpty();
  await capture(page, join(SHOTS, "04-design-research-answers.png"));
  // The defect was a 422 from POST /api/prompts before the turn began.
  expect(seen.failures.filter((line) => line.includes("/api/prompts"))).toEqual([]);
});

test("every destination reads through the generated client", async ({ page }) => {
  test.setTimeout(420_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  for (const destination of DESTINATIONS) {
    await page.goto(`${BASE}/#/${destination.route}`);
    await expect(page.locator("main#main")).toBeVisible();
    await settled(page);
  }
  // Pages whose answers changed shape in this run: grants, telemetry and
  // security health became projections, the update panel's answer a union, and
  // the execution environments a declared view.
  for (const [route, file] of [
    ["settings?tab=security", "05-settings-security.png"],
    ["settings?tab=updates", "06-settings-updates.png"],
    ["settings?tab=runtime", "07-settings-runtime.png"],
    ["observability", "08-observability.png"],
    ["extensions", "09-extensions.png"],
  ] as const) {
    await page.goto(`${BASE}/#/${route}`);
    await settled(page);
    await capture(page, join(SHOTS, file));
  }
  expect(seen.failures.filter((line) => !UNREACHABLE.test(line))).toEqual([]);
  expect(seen.consoleErrors.filter((line) => !UNREACHABLE.test(line))).toEqual([]);
});

test("MFA shows its recovery codes once, and one recovers the password from the lock screen", async ({
  browser,
}) => {
  test.setTimeout(240_000);
  const context = await browser.newContext();
  const page = await context.newPage();
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=security`);
  await page.getByRole("button", { name: "Enroll in MFA" }).click();
  const codes = page.getByRole("list", { name: "Recovery codes" });
  await expect(codes).toBeVisible({ timeout: 30_000 });
  // The codes and the secret are this throwaway workspace's, but a capture
  // that is committed shows where they are, not what they are.
  // Through the CSSOM: the host's `style-src 'self'` refuses an injected sheet.
  await page.locator(".backup-codes code, code.uri").evaluateAll((nodes) => {
    for (const node of nodes) (node as HTMLElement).style.filter = "blur(5px)";
  });
  await capture(page, join(SHOTS, "10-mfa-recovery-codes.png"));
  const backup = (await codes.locator("code").allTextContents()).map((code) => code.trim());
  expect(backup.length).toBeGreaterThan(1);
  const uri = (await page.locator("code.uri").textContent()) ?? "";
  const secret = new URL(uri).searchParams.get("secret") ?? "";
  expect(secret).not.toBe("");
  await page.getByLabel("Verification code").fill(totp(secret));
  await page.getByRole("button", { name: "Activate" }).click();
  await expect(page.getByText("MFA is now active.")).toBeVisible({ timeout: 30_000 });
  await context.close();

  // A fresh browser: the lock screen, as an owner who has forgotten the password.
  const locked = await browser.newContext();
  const lock = await locked.newPage();
  const temporary = `${OWNER_CREDENTIALS.password}-recovered`;
  async function recover(code: string, to: string): Promise<void> {
    // A reload, because the lock screen keeps its recovery step across a
    // same-address navigation.
    await lock.goto(`${BASE}/#/workbench`);
    await lock.reload();
    await expect(lock.getByLabel("Username")).toBeEnabled({ timeout: 60_000 });
    await lock.getByRole("button", { name: "Forgot password?" }).click();
    await lock.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
    await lock.getByRole("button", { name: "Begin recovery" }).click();
    await lock.getByLabel("Recovery verification code").fill(code);
    await lock.getByLabel("New password").fill(to);
    await lock.getByRole("button", { name: "Reset password" }).click();
  }

  await recover(backup[0], temporary);
  await expect(lock.getByText("Your password was changed. Unlock with the new one.")).toBeVisible({
    timeout: 30_000,
  });
  await capture(lock, join(SHOTS, "11-recovered-by-backup-code.png"));

  // A recovery code works once.
  await recover(backup[0], OWNER_CREDENTIALS.password);
  await expect(lock.getByText("Password recovery failed.")).toBeVisible({ timeout: 30_000 });

  // The next one puts the round's password back, and the account unlocks with
  // it and the authenticator's code.
  await recover(backup[1], OWNER_CREDENTIALS.password);
  await expect(lock.getByText("Your password was changed. Unlock with the new one.")).toBeVisible({
    timeout: 30_000,
  });
  await lock.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
  await lock.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
  await lock.getByRole("button", { name: /unlock|sign in/i }).click();
  await lock.getByLabel("Authentication code").fill(totp(secret));
  await lock.getByRole("button", { name: "Verify" }).click();
  await expect(lock.getByRole("navigation", { name: "All navigation" })).toBeVisible({ timeout: 60_000 });
  await locked.close();
});
