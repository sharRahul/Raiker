/** QUI-G06: real host with injected 503 responses; no release install is attempted. */
import { expect, test } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { capture, captureElement } from "./capture";
const failed = { status: 503, contentType: "application/json", body: '{"detail":{"reason_code":"injected_failure"}}' };
const shots = "../../output/playwright/2026-11-06-settings-recovery";
test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signInAsOwner(page, BASE);
});
test("RT-SETTINGS-RECOVERY-01: update read can recover without endless loading", async ({ page }) => {
  await page.route("**/api/host/update", route => route.fulfill(failed));
  await page.goto(`${BASE}/#/settings?tab=updates`);
  await expect(page.getByRole("status").filter({ hasText: "Update status could not be read" })).toContainText("HTTP 503");
  await expect(page.getByText("Loading update status…", { exact: true })).toHaveCount(0);
  await capture(page, `${shots}/01-update-read.png`);
  await page.unroute("**/api/host/update");
  await page.getByRole("button", { name: "Retry update status" }).click();
  await expect(page.getByText("Installed build", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry update status" })).toHaveCount(0);
});
test("RT-SETTINGS-RECOVERY-02: update check states uncertainty", async ({ page }) => {
  await page.route("**/api/host/update/check", route => route.fulfill(failed));
  await page.goto(`${BASE}/#/settings?tab=updates`);
  await page.getByRole("button", { name: "Check for updates", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "The update check did not finish" })).toContainText("Whether a newer release is available is unknown");
  await capture(page, `${shots}/02-update-check.png`);
});
test("RT-SETTINGS-RECOVERY-03: profiles read explains affected boundary", async ({ page }) => {
  await page.route("**/api/execution-profiles", route => route.fulfill(failed));
  await page.goto(`${BASE}/#/settings?tab=execution-profiles`);
  await expect(page.getByText(/The saved boundaries are unconfirmed/)).toBeVisible();
  await capture(page, `${shots}/03-profiles-read.png`);
});
test("RT-SETTINGS-RECOVERY-04: execution status never claims readiness on failure", async ({ page }) => {
  await page.route("**/api/runtime-mode", route => route.fulfill(failed));
  await page.goto(`${BASE}/#/settings?tab=advanced`);
  await page.evaluate(() => { document.documentElement.dataset.theme = "dark"; });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByText(/Whether the agent accepts new work is unconfirmed/)).toBeVisible();
  await capture(page, `${shots}/04-execution-status-dark.png`);
});

test("RT-SETTINGS-RECOVERY-05: supplied provider credentials are entered through the UI", async ({ page }) => {
  test.setTimeout(240_000);
  const { connectHostedProvider } = await import("./hosted-provider");
  const providers = [
    ["Anthropic", "Anthropic API key", process.env.RAIKER_LIVE_ANTHROPIC_KEY],
    ["OpenRouter", "OpenRouter API key", process.env.RAIKER_LIVE_OPENROUTER_KEY],
    ["OpenAI", "OpenAI API key", process.env.RAIKER_LIVE_OPENAI_KEY],
  ];
  test.skip(providers.some(([, , key]) => !key), "Requires all three owner-supplied provider keys in environment variables.");
  for (const [provider, label, key] of providers) {
    const card = await connectHostedProvider(page, BASE, provider!, label!, key!);
    await captureElement(card, `${shots}/05-${provider!.toLowerCase()}-connection.png`);
  }

});


test("RT-SETTINGS-RECOVERY-06: saved provider connections remain readable", async ({ page }) => {
  test.setTimeout(120_000);
  const { hostedProviderCard } = await import("./hosted-provider");
  for (const provider of ["Anthropic", "OpenRouter", "OpenAI"]) {
    const card = await hostedProviderCard(page, BASE, provider);
    await expect(card).toBeVisible();
    await expect(card.getByRole("button", { name: "Connect", exact: true })).toHaveCount(0);
    await captureElement(card, `${shots}/06-${provider.toLowerCase()}-saved.png`);
  }
});
