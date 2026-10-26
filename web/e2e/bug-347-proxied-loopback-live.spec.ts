/**
 * BUG-347 / BUG-358 — a reverse proxy in front of Raiker, against a running host
 * started with a proxy listener after two-step sign-in was turned on:
 *
 *   raiker-web --workspace <ws> --port 8765 --proxy-port 8766 --no-browser
 *
 * RAIKER_LIVE_PROXY_BASE names the proxy listener (or a reverse proxy in front
 * of it that adds no forwarding header); RAIKER_LIVE_REMOTE_STATE holds the
 * throwaway account's TOTP secret. No model or key is needed.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md): RT-SEC-01 to RT-SEC-03.
 */
import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { OWNER_CREDENTIALS } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { totp } from "./totp";

const PROXY = process.env.RAIKER_LIVE_PROXY_BASE ?? "http://127.0.0.1:8766";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-26-bug-347";
const HTTPS = { "X-Forwarded-Proto": "https" };

function code(): string {
  const state = JSON.parse(readFileSync(process.env.RAIKER_LIVE_REMOTE_STATE ?? "", "utf8")) as { secret: string };
  return totp(state.secret);
}

async function signIn(page: import("@playwright/test").Page, base: string): Promise<void> {
  await page.goto(`${base}/#/workbench`);
  await expect(page.getByLabel("Username")).toBeEnabled({ timeout: 60_000 });
  await page.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
  await page.getByRole("button", { name: /unlock|sign in/i }).click();
  await page.locator("#mfa-code").fill(code());
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.locator("#mfa-code")).toBeHidden({ timeout: 60_000 });
}

test("RT-SEC-01 — a forwarded request on the local listener is refused, and says what to change", async ({ request }) => {
  const refused = await request.get(`${BASE}/api/health`, { headers: { "X-Forwarded-For": "203.0.113.9" } });
  expect(refused.status()).toBe(403);
  const body = await refused.json();
  expect(body.detail.reason_code).toBe("proxied_request_refused");
  expect(body.detail.message).toContain("Remote access");
  const page = await request.get(`${BASE}/`, { headers: { Forwarded: "for=203.0.113.9;proto=https" } });
  expect(page.status()).toBe(403);
  expect(await page.text()).toContain("reverse proxy");
  const direct = await request.get(`${BASE}/api/health`);
  expect(direct.status()).toBe(200);
});

test("RT-SEC-02 — Diagnostics names the refused proxy and where to change it", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, BASE);
  await page.goto(`${BASE}/#/observe?tab=overview`);
  await settled(page);
  const card = page.locator("li.issue").filter({ hasText: "Requests through a reverse proxy are being refused" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card).toContainText("Remote access");
  await capture(page, `${SHOTS}/02-diagnostics-proxy-refused.png`, card);
});

test("RT-SEC-03 — everything on the proxy listener is remote: HTTPS, a code, never local", async ({ browser, request }) => {
  test.setTimeout(240_000);
  // A proxy that adds no forwarding header at all: refused for want of HTTPS.
  const plain = await request.get(`${PROXY}/api/auth/session-state`);
  expect(plain.status()).toBe(403);
  expect((await plain.json()).detail.reason_code).toBe("remote_https_required");
  // With HTTPS at the proxy: still remote, so recovery is refused…
  const stripped = await request.get(`${PROXY}/api/recovery/backups`, { headers: HTTPS });
  expect(stripped.status()).toBe(403);
  expect(await stripped.text()).toContain("recovery_loopback_only");
  // …and a header claiming this computer changes nothing.
  const spoofed = await request.get(`${PROXY}/api/recovery/backups`, { headers: { ...HTTPS, "X-Forwarded-For": "127.0.0.1" } });
  expect(spoofed.status()).toBe(403);
  // The owner signs in through it with the password and a code.
  const context = await browser.newContext({ extraHTTPHeaders: HTTPS, viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await signIn(page, PROXY);
  // Asked from the page, so the browser's own cookie (Secure, HttpOnly) goes with it.
  const who = await page.evaluate(async () => (await (await fetch("/api/auth/session-state")).json()) as { principal_id: string | null });
  expect(who.principal_id).not.toBeNull();
  await page.goto(`${PROXY}/#/observe?tab=overview`);
  await settled(page);
  const card = page.locator("li.issue").filter({ hasText: "Raiker is reachable from other devices" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card).toContainText(new URL(PROXY).port);
  await capture(page, `${SHOTS}/03-diagnostics-proxy-listener.png`, card);
  await context.close();
});
