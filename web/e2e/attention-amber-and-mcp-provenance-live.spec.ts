/**
 * The owner's 2026-11-08 decisions, against a running host: dark attention is
 * its own amber, apart from the gold primary action, and an MCP server says
 * where it came from (PL-5). No model or key is needed.
 *
 * Prerequisite: a fresh workspace served by
 * `raiker-web --workspace <ws> --port 8765 --no-browser`.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Dark attention amber and
 * MCP provenance"): RT-AMB-01, RT-AMB-02, RT-MCP-PL5-01.
 */
import { expect, test, type Page } from "@playwright/test";

import { settled } from "./destinations";
import { enableCapability, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../output/playwright/2026-11-08-amber-and-mcp-provenance";
const SERVERS = `${BASE}/#/connections?tab=advanced&kind=mcp`;

/** Dark from the system setting, then reloaded: a capture taken mid-transition is not evidence. */
async function dark(page: Page): Promise<void> {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.reload();
  await settled(page);
}

async function token(page: Page, name: string): Promise<string> {
  return page.evaluate((n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim(), name);
}

test("RT-AMB-01 — dark attention is its own amber, and the primary action stays gold", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  await dark(page);
  expect((await token(page, "--warn")).toUpperCase()).toBe("#EE9A4D");
  expect((await token(page, "--action")).toUpperCase()).toBe("#E0B64A");
  // A fresh workspace has no default model: Home says so as an attention notice.
  const notice = page.locator(".notice-warn, .notice.warn, [data-tone='warn']").first();
  if ((await notice.count()) > 0) {
    const colour = await notice.evaluate((element) => getComputedStyle(element).borderColor);
    expect(colour).toContain("238, 154, 77");
  }
  await page.screenshot({ path: `${SHOTS}/01-home-dark.png` });
});

test("RT-AMB-02 — the light theme keeps its blue primary and its own attention colour", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  await page.emulateMedia({ colorScheme: "light" });
  await page.reload();
  await settled(page);
  expect((await token(page, "--warn")).toUpperCase()).toBe("#8A6411");
  expect((await token(page, "--action")).toUpperCase()).not.toBe("#E0B64A");
  await page.screenshot({ path: `${SHOTS}/02-home-light.png` });
});

test("RT-MCP-PL5-01 — an MCP server's row says where it came from", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await enableCapability(page, BASE, "MCP builder", "Generate a sample server for the provenance check");
  await page.goto(SERVERS);
  await settled(page);
  if ((await page.locator(".provenance").count()) === 0) {
    await page.getByText("Developer example — generate a local sample server", { exact: true }).click();
    await page.getByLabel("Server name", { exact: true }).fill("provenance-sample");
    await page.getByRole("button", { name: "Generate example server", exact: true }).click();
  }
  const label = page.locator(".provenance").first();
  await expect(label).toHaveText("Raiker sample", { timeout: 60_000 });
  await expect(label).toHaveAttribute("title", /Shipped with Raiker/);
  await expect(page.locator(".provenance", { hasText: "Experimental" })).toHaveCount(0);
  await label.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${SHOTS}/03-mcp-provenance-light.png` });
  await dark(page);
  await page.locator(".provenance").first().waitFor();
  await page.screenshot({ path: `${SHOTS}/04-mcp-provenance-dark.png` });
});
