/**
 * BUG-347 — a reverse proxy in front of a loopback-bound Raiker, against a
 * running host started with a proxy listener:
 *
 *   RAIKER_OWNER_TOKEN=… raiker-web --workspace <ws> --port 8765 --proxy-port 8766 --no-browser
 *
 * RAIKER_LIVE_PROXY_BASE names the proxy listener (or a reverse proxy in front
 * of it that adds no forwarding header). No model or key is needed.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md): RT-SEC-01 to RT-SEC-03.
 */
import { expect, test } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const PROXY = process.env.RAIKER_LIVE_PROXY_BASE ?? "http://127.0.0.1:8766";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-26-bug-347";

test("RT-SEC-01 — a forwarded request on the local listener is refused, and says what to change", async ({ request }) => {
  const refused = await request.get(`${BASE}/api/health`, { headers: { "X-Forwarded-For": "203.0.113.9" } });
  expect(refused.status()).toBe(403);
  const body = await refused.json();
  expect(body.detail.reason_code).toBe("proxied_request_refused");
  expect(body.detail.message).toContain("--proxy-port");
  const page = await request.get(`${BASE}/`, { headers: { Forwarded: "for=203.0.113.9;proto=https" } });
  expect(page.status()).toBe(403);
  expect(await page.text()).toContain("reverse proxy");
  const direct = await request.get(`${BASE}/api/health`);
  expect(direct.status()).toBe(200);
});

test("RT-SEC-02 — Diagnostics names the refused proxy and how to run behind one", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/observe?tab=overview`);
  await settled(page);
  const card = page.locator("li.issue").filter({ hasText: "Requests through a reverse proxy are being refused" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card).toContainText("--proxy-port");
  await capture(page, `${SHOTS}/02-diagnostics-proxy-refused.png`, card);
});

test("RT-SEC-03 — everything on the proxy listener is remote, with or without headers", async ({ page, request }) => {
  test.setTimeout(180_000);
  // A proxy that adds no forwarding header at all: still remote.
  const stripped = await request.get(`${PROXY}/api/recovery/backups`);
  expect(stripped.status()).toBe(403);
  expect(await stripped.text()).toContain("recovery_loopback_only");
  // A header that claims this computer changes nothing.
  const spoofed = await request.get(`${PROXY}/api/recovery/backups`, { headers: { "X-Forwarded-For": "127.0.0.1" } });
  expect(spoofed.status()).toBe(403);
  // HTTPS at the proxy brings HSTS.
  const secure = await request.get(`${PROXY}/api/health`, { headers: { "X-Forwarded-Proto": "https" } });
  expect(secure.headers()["strict-transport-security"]).toContain("max-age=");
  // The owner can use Raiker through it, and Diagnostics says it is reachable.
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, PROXY);
  await page.goto(`${PROXY}/#/observe?tab=overview`);
  await settled(page);
  const card = page.locator("li.issue").filter({ hasText: "Raiker is reachable from the internet through a proxy" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card).toContainText(new URL(PROXY).port);
  await capture(page, `${SHOTS}/03-diagnostics-proxy-listener.png`, card);
});
