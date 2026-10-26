/**
 * Storage upgrade, against a running host: SQLCipher 4.19.0, FTS5 required, and
 * no `off` mode for SQLCipher memory security (owner's decisions, 2026-10-26).
 *
 * Prerequisites: a fresh workspace served by
 * `RAIKER_SQLCIPHER_MEMORY_SECURITY=off raiker-web --workspace <ws> --port 8765 --no-browser`.
 * The stale `off` is deliberate: RT-STORE-03 proves it is read as *auto*.
 * No model or key is needed.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Storage upgrade"):
 * RT-STORE-01 … RT-STORE-03.
 */
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-26-storage-upgrade";

async function health(page: Page): Promise<Record<string, unknown>> {
  const response = await page.request.get(`${BASE}/api/health`);
  expect(response.ok()).toBe(true);
  return (await response.json()) as Record<string, unknown>;
}

test("RT-STORE-01 — the host runs SQLCipher 4.19.0 and searches with FTS5", async ({ page }) => {
  const body = await health(page);
  expect(body.store).toBe("ok");
  expect(String(body.sqlcipher_version)).toMatch(/^4\.19\./);
  expect(body.text_search_engine).toBe("fts5");
  expect(body.text_search_ranking).toBe("bm25_relevance");
  expect(body.text_search_reason).toBe("");
});

test("RT-STORE-02 — Settings names the SQLCipher version and never says memory locking was disabled", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=security`);
  await settled(page);
  const row = page.getByTestId("storage-posture");
  await expect(row).toContainText("On", { timeout: 30_000 });
  await row.getByRole("button", { name: "Details" }).click();
  const dialog = page.getByRole("dialog", { name: "Encryption" });
  await expect(dialog).toContainText("Encrypted");
  await expect(dialog).toContainText(/Locked in memory|Degraded on this host/);
  await expect(dialog).not.toContainText("Disabled by user");
  await expect(dialog).toContainText(/SQLCipher 4\.19\./);
  await capture(page, `${SHOTS}/02-encryption-details.png`, dialog);
});

test("RT-STORE-03 — a stale RAIKER_SQLCIPHER_MEMORY_SECURITY=off is read as auto", async ({ page }) => {
  const body = await health(page);
  expect(body.memory_security_mode).toBe("auto");
  expect(String(body.memory_security_reason)).not.toBe("requested_off");
  expect(String(body.memory_security_reason)).toMatch(/^auto_probe_/);
});
