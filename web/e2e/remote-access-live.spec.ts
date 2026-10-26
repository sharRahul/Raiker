/**
 * BUG-347 / BUG-358 — remote access, end to end, against a real host.
 *
 * A host is started on a fresh workspace with `raiker-web --port 8765`, and
 * this computer owns a private address (RAIKER_LIVE_PRIVATE_HOST, e.g.
 * 10.77.0.1) with a self-signed certificate for it (RAIKER_LIVE_TLS_CERT,
 * RAIKER_LIVE_TLS_KEY, created for the run and never committed). Another
 * device is a second browser context opening https://<private host>:8443.
 *
 * The run has phases, because applying a remote-access setting restarts the
 * host and this host is not a registered service (so the harness restarts it):
 *
 *   RAIKER_LIVE_REMOTE_PHASE=configure   RT-SEC-04 … RT-SEC-06, then restart the host
 *   RAIKER_LIVE_REMOTE_PHASE=remote      RT-SEC-07 … RT-SEC-11
 *   RAIKER_LIVE_REMOTE_PHASE=failclosed  RT-SEC-12, after the harness removes the
 *                                        certificate and restarts the host
 *
 * The TOTP secret of the throwaway account travels between phases in
 * RAIKER_LIVE_REMOTE_STATE (a scratch file), so each phase can make codes.
 * Live cases: docs/architecture/WEB_APP_LIVE_TEST.md.
 */
import { readFileSync, writeFileSync } from "node:fs";

import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { OWNER_CREDENTIALS, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { secretFrom, totp } from "./totp";

const PHASE = process.env.RAIKER_LIVE_REMOTE_PHASE ?? "";
const HOST = process.env.RAIKER_LIVE_PRIVATE_HOST ?? "10.77.0.1";
const PORT = process.env.RAIKER_LIVE_PRIVATE_PORT ?? "8443";
const CERT = process.env.RAIKER_LIVE_TLS_CERT ?? "";
const KEY = process.env.RAIKER_LIVE_TLS_KEY ?? "";
const STATE = process.env.RAIKER_LIVE_REMOTE_STATE ?? "";
const REMOTE = `https://${HOST}:${PORT}`;
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-26-remote-access";

function secret(): string {
  return (JSON.parse(readFileSync(STATE, "utf8")) as { secret: string }).secret;
}

function remember(value: string): void {
  writeFileSync(STATE, JSON.stringify({ secret: value }));
}

async function security(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/settings?tab=security`);
  await settled(page);
  await expect(page.getByTestId("remote-state")).toBeVisible({ timeout: 30_000 });
  // Every row has the server's answer, not its default, before anything is read or captured.
  await expect(page.getByText("Reading…")).toHaveCount(0, { timeout: 30_000 });
}

/** Sign in at `base`, giving a code when the lock screen asks for one. */
async function signIn(page: Page, base: string, code?: () => string): Promise<void> {
  await page.goto(`${base}/#/workbench`);
  const username = page.getByLabel("Username");
  await expect(username).toBeEnabled({ timeout: 60_000 });
  await username.fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
  await page.getByRole("button", { name: /unlock|sign in/i }).click();
  if (code) {
    const field = page.locator("#mfa-code");
    await expect(field).toBeVisible({ timeout: 30_000 });
    await field.fill(code());
    await page.getByRole("button", { name: "Verify" }).click();
  }
}

async function device(browser: Browser): Promise<BrowserContext> {
  // The self-signed certificate is the run's own; a real device trusts the owner's CA.
  return browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 900 } });
}

async function freshProof(scope: ReturnType<Page["getByRole"]>): Promise<void> {
  await scope.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
  await scope.getByLabel("Authenticator code").fill(totp(secret()));
}

test.describe.configure({ mode: "serial" });

test.describe("configure", () => {
  test.skip(PHASE !== "configure", "phase");

  test("RT-SEC-04 — remote access is off, and cannot be set up before two-step sign-in", async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAsOwner(page, BASE);
    await security(page);
    await expect(page.getByTestId("remote-state")).toHaveText("Off — this device only");
    await expect(page.getByTestId("host-access").or(page.getByTestId("remote-connection"))).toBeTruthy();
    await page.getByTestId("remote-access").getByRole("button", { name: "Set up" }).click();
    const dialog = page.getByRole("dialog", { name: "Remote access" });
    await dialog.getByRole("radio", { name: /Private network/ }).check();
    await expect(dialog.getByText("Two-step sign-in must be on for every account.")).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Continue" })).toBeDisabled();
    await capture(page, `${SHOTS}/04-needs-two-step.png`, dialog);
    await dialog.getByRole("button", { name: "Close" }).click();
  });

  test("RT-SEC-05 — two-step sign-in is turned on in Settings", async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAsOwner(page, BASE);
    await security(page);
    await page.locator(".setting-row").filter({ hasText: "Two-step sign-in" }).first().getByRole("button", { name: "Turn on" }).click();
    const dialog = page.getByRole("dialog", { name: "Two-step sign-in" });
    await dialog.getByRole("button", { name: "Enroll in MFA" }).click();
    const uri = (await dialog.locator("code.uri").textContent()) ?? "";
    remember(secretFrom(uri));
    await dialog.getByLabel("Verification code").fill(totp(secret()));
    await dialog.getByRole("button", { name: "Activate" }).click();
    await expect(dialog.getByText("MFA is now active.")).toBeVisible({ timeout: 30_000 });
  });

  test("RT-SEC-06 — a private-network setting is checked, reviewed and saved with fresh MFA", async ({ page }) => {
    test.setTimeout(240_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, BASE, () => totp(secret()));
    await security(page);
    await page.getByTestId("remote-access").getByRole("button", { name: "Set up" }).click();
    let dialog = page.getByRole("dialog", { name: "Remote access" });
    await dialog.getByRole("radio", { name: /Private network/ }).check();
    await expect(dialog.getByText("Two-step sign-in is on.")).toBeVisible();
    await dialog.getByRole("button", { name: "Continue" }).click();
    await dialog.getByLabel("This computer's private address").fill(HOST);
    await dialog.getByLabel("Certificate file (PEM)").fill(CERT);
    await dialog.getByLabel("Private key file (PEM)").fill(KEY);
    // First the local listener's own port, which the check refuses by name.
    await dialog.getByText("Advanced").click();
    await dialog.getByLabel("Port").fill("8765");
    await dialog.getByRole("button", { name: "Check and continue" }).click();
    await expect(dialog.getByText(/Port 8765 is Raiker's own listener for this computer/)).toBeVisible({ timeout: 30_000 });
    await capture(page, `${SHOTS}/06-check-refuses-local-port.png`, dialog);
    await dialog.getByLabel("Port").fill(PORT);
    await dialog.getByRole("button", { name: "Check and continue" }).click();
    dialog = page.getByRole("dialog", { name: "Remote access" });
    await expect(dialog.getByText(`https://${HOST}:${PORT}`)).toBeVisible({ timeout: 30_000 });
    await freshProof(dialog);
    const turnOn = dialog.getByRole("button", { name: "Turn on remote access" });
    await expect(turnOn).toBeDisabled();
    await dialog.getByRole("checkbox").check();
    await capture(page, `${SHOTS}/06-review.png`, dialog);
    await turnOn.click();
    await expect(dialog.getByText("Saved. Raiker opens it when it restarts.")).toBeVisible({ timeout: 30_000 });
    await expect(dialog.getByText(/Quit Raiker and open it again/)).toBeVisible();
    await dialog.getByRole("button", { name: "Close" }).click();
    // Not shown as on before the host opens it.
    await expect(page.getByTestId("remote-state")).toHaveText("Waiting for a restart");
    await expect(page.getByTestId("remote-connection")).toHaveText("This device only");
    await capture(page, `${SHOTS}/06-waiting-for-restart.png`, page.getByTestId("remote-access"));
  });
});

test.describe("remote", () => {
  test.skip(PHASE !== "remote", "phase");

  test("RT-SEC-07 — after the restart Settings, the Host menu and Diagnostics report the open listener", async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, BASE, () => totp(secret()));
    await security(page);
    await expect(page.getByTestId("remote-state")).toHaveText("On");
    await expect(page.getByTestId("remote-connection")).toHaveText(`Private network · https://${HOST}:${PORT}`);
    await expect(page.getByTestId("remote-access").getByText("Verified")).toBeVisible();
    await capture(page, `${SHOTS}/07-settings-on.png`, page.getByTestId("remote-access"));
    await page.getByRole("button", { name: /host/i }).first().click();
    await expect(page.getByTestId("host-access")).toContainText("other devices through your private network");
    await page.keyboard.press("Escape");
    await page.goto(`${BASE}/#/observe?tab=overview`);
    await settled(page);
    await expect(page.locator("li.issue").filter({ hasText: "Raiker is reachable from other devices" })).toBeVisible({ timeout: 30_000 });
  });

  test("RT-SEC-08 — another device needs the password and a code, over HTTPS only", async ({ browser, request }) => {
    test.setTimeout(240_000);
    const context = await device(browser);
    const page = await context.newPage();
    // A password alone opens nothing: the lock screen asks for a code.
    await page.goto(`${REMOTE}/#/workbench`);
    await page.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
    await page.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
    const field = page.locator("#mfa-code");
    await expect(field).toBeVisible({ timeout: 30_000 });
    await field.fill("000000");
    await page.getByRole("button", { name: "Verify" }).click();
    await expect(page.getByRole("alert")).toBeVisible({ timeout: 30_000 });
    await capture(page, `${SHOTS}/08-wrong-code.png`);
    // The same ticket takes the right code.
    await field.fill(totp(secret()));
    await page.getByRole("button", { name: "Verify" }).click();
    await expect(page.locator("#mfa-code")).toBeHidden({ timeout: 60_000 });
    await settled(page);
    await capture(page, `${SHOTS}/08-signed-in-remotely.png`);
    // This computer's operations refuse it, whatever it is signed in as.
    const recovery = await page.request.get(`${REMOTE}/api/recovery/backups`);
    expect(recovery.status()).toBe(403);
    const restart = await page.request.post(`${REMOTE}/api/host/restart`, { data: { confirm: true } });
    expect(restart.status()).toBe(403);
    // Plain HTTP is not answered on the remote listener at all.
    await expect(request.get(`http://${HOST}:${PORT}/api/health`, { timeout: 5_000 })).rejects.toThrow();
    await context.close();
  });

  test("RT-SEC-09 — Signed-in devices shows the remote session, and signing it out ends it there", async ({ page, browser }) => {
    test.setTimeout(240_000);
    const context = await device(browser);
    const remote = await context.newPage();
    await signIn(remote, REMOTE, () => totp(secret()));
    await expect(remote.getByLabel("Username")).toBeHidden({ timeout: 60_000 });
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, BASE, () => totp(secret()));
    await security(page);
    await page.locator(".setting-row").filter({ hasText: "Signed-in devices" }).getByRole("button", { name: "Manage" }).click();
    const dialog = page.getByRole("dialog", { name: "Signed-in devices" });
    const row = dialog.getByTestId("device-session").filter({ hasText: "Another device" }).first();
    await expect(row).toContainText("Signed in with a code");
    await capture(page, `${SHOTS}/09-signed-in-devices.png`, dialog);
    await row.getByRole("button", { name: "Sign out" }).click();
    await remote.reload();
    await expect(remote.getByLabel("Username")).toBeVisible({ timeout: 60_000 });
    await context.close();
  });

  test("RT-SEC-10 — turning two-step sign-in off suspends remote access at once", async ({ page, browser }) => {
    test.setTimeout(300_000);
    const context = await device(browser);
    const remote = await context.newPage();
    await signIn(remote, REMOTE, () => totp(secret()));
    await expect(remote.getByLabel("Username")).toBeHidden({ timeout: 60_000 });
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, BASE, () => totp(secret()));
    await security(page);
    await page.locator(".setting-row").filter({ hasText: "Two-step sign-in" }).first().getByRole("button", { name: "Manage" }).click();
    const mfa = page.getByRole("dialog", { name: "Two-step sign-in" });
    await mfa.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
    await mfa.getByLabel("Authenticator or recovery code").fill(totp(secret()));
    await mfa.getByRole("button", { name: "Turn off" }).click();
    await page.getByRole("dialog", { name: "Turn off two-step sign-in?" }).getByRole("button", { name: "Turn off" }).click();
    await expect(mfa.getByText(/remote access is suspended/)).toBeVisible({ timeout: 30_000 });
    await mfa.getByRole("button", { name: "Close" }).click();
    await security(page);
    await expect(page.getByTestId("remote-state")).toHaveText("Suspended");
    await capture(page, `${SHOTS}/10-suspended.png`, page.getByTestId("remote-access"));
    // The other device is signed out, and signing in again says why it cannot.
    await remote.reload();
    await remote.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
    await remote.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
    await remote.getByRole("button", { name: /unlock|sign in/i }).click();
    await expect(remote.getByRole("alert")).toContainText("Remote access is suspended", { timeout: 30_000 });
    await capture(remote, `${SHOTS}/10-remote-suspended.png`);
    await page.goto(`${BASE}/#/observe?tab=overview`);
    await settled(page);
    await expect(page.locator("li.issue").filter({ hasText: "Remote access is suspended" })).toBeVisible({ timeout: 30_000 });
    await capture(page, `${SHOTS}/10-diagnostics-suspended.png`, page.locator("li.issue").filter({ hasText: "Remote access is suspended" }));
    // Turning it on again lifts the suspension without a restart.
    await security(page);
    await page.locator(".setting-row").filter({ hasText: "Two-step sign-in" }).first().getByRole("button", { name: "Turn on" }).click();
    const again = page.getByRole("dialog", { name: "Two-step sign-in" });
    await again.getByRole("button", { name: "Enroll in MFA" }).click();
    remember(secretFrom((await again.locator("code.uri").textContent()) ?? ""));
    await again.getByLabel("Verification code").fill(totp(secret()));
    await again.getByRole("button", { name: "Activate" }).click();
    await expect(again.getByText("MFA is now active.")).toBeVisible({ timeout: 30_000 });
    await signIn(remote, REMOTE, () => totp(secret()));
    await expect(remote.getByLabel("Username")).toBeHidden({ timeout: 60_000 });
    await context.close();
  });

  test("RT-SEC-11 — another device turns remote access off, at once", async ({ page, browser }) => {
    test.setTimeout(240_000);
    const context = await device(browser);
    const remote = await context.newPage();
    await signIn(remote, REMOTE, () => totp(secret()));
    await expect(remote.getByLabel("Username")).toBeHidden({ timeout: 60_000 });
    await remote.goto(`${REMOTE}/#/settings?tab=security`);
    await settled(remote);
    const section = remote.getByTestId("remote-access");
    await expect(section.getByText(/changed on the computer Raiker runs on/)).toBeVisible({ timeout: 30_000 });
    await expect(section.getByRole("button", { name: "Change" })).toHaveCount(0);
    await section.getByRole("button", { name: "Turn off" }).click();
    await remote.getByRole("dialog", { name: "Turn off remote access?" }).getByRole("button", { name: "Turn off" }).click();
    await expect(section.getByText(/Other devices are refused now/)).toBeVisible({ timeout: 30_000 });
    const after = await remote.request.get(`${REMOTE}/api/health`);
    expect(after.status()).toBe(403);
    expect((await after.json()).detail.reason_code).toBe("remote_access_disabled");
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, BASE, () => totp(secret()));
    await security(page);
    await expect(page.getByTestId("remote-state")).toHaveText("Off — this device only");
    await capture(page, `${SHOTS}/11-turned-off.png`, page.getByTestId("remote-access"));
    await context.close();
  });
});

test.describe("failclosed", () => {
  test.skip(PHASE !== "failclosed", "phase");

  test("RT-SEC-12 — a setting that cannot start leaves the host closed, says why, and rolls back", async ({ page, request }) => {
    test.setTimeout(240_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, BASE, () => totp(secret()));
    await security(page);
    await expect(page.getByTestId("remote-state")).toHaveText("Not working");
    await expect(page.getByTestId("remote-problem").first()).toContainText("Remote access did not start");
    await expect(page.getByTestId("remote-connection")).toHaveText("This device only");
    await capture(page, `${SHOTS}/12-start-failed.png`, page.getByTestId("remote-access"));
    await expect(request.get(`https://${HOST}:${PORT}/api/health`, { timeout: 5_000, ignoreHTTPSErrors: true })).rejects.toThrow();
    await page.goto(`${BASE}/#/observe?tab=overview`);
    await settled(page);
    await expect(page.locator("li.issue").filter({ hasText: "Remote access did not start" })).toBeVisible({ timeout: 30_000 });
    await security(page);
    await page.getByTestId("remote-access").getByRole("button", { name: "Details" }).click();
    const details = page.getByRole("dialog", { name: "Connection details" });
    await details.getByText(/Go back to the previous setting/).click();
    await freshProof(details);
    await details.getByRole("button", { name: "Go back" }).click();
    await expect(details.getByText("The previous setting is back.")).toBeVisible({ timeout: 30_000 });
    await capture(page, `${SHOTS}/12-rolled-back.png`, details);
  });
});
