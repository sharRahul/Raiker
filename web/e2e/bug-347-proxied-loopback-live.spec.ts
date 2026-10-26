/**
 * BUG-347 — a reverse proxy in front of a loopback-bound Raiker, against a
 * running host (`raiker-web --workspace <ws> --port 8765 --no-browser`, with no
 * RAIKER_TRUSTED_PROXY). No model or key is needed.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md): RT-SEC-01, RT-SEC-02.
 * The trusted-proxy half needs a host started with RAIKER_TRUSTED_PROXY and
 * RAIKER_OWNER_TOKEN; it is checked by hand and by `test_proxied_loopback.py`.
 */
import { expect, test } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-26-bug-347";

test("RT-SEC-01 — a request a proxy forwarded to the loopback host is refused, and says what to change", async ({ request }) => {
  const refused = await request.get(`${BASE}/api/health`, { headers: { "X-Forwarded-For": "203.0.113.9" } });
  expect(refused.status()).toBe(403);
  const body = await refused.json();
  expect(body.detail.reason_code).toBe("proxied_request_refused");
  expect(body.detail.message).toContain("RAIKER_TRUSTED_PROXY");
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
  await expect(card).toContainText("RAIKER_TRUSTED_PROXY");
  await capture(page, `${SHOTS}/02-diagnostics-proxy-refused.png`, card);
});
