/** VD-1: real managed engines through the product UI on a disposable packaged host. */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

test("VD-1 packaged Voice installs, speaks, hears and removes its verified engines", async ({ page }) => {
  test.skip(process.env.RAIKER_LIVE_MANAGED_VOICE !== "1", "Requires a packaged Kokoro host and explicit real downloads");
  test.setTimeout(900_000);
  page.setDefaultTimeout(30_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=voice`);
  await page.getByRole("radio", { name: /^Lite/ }).check();
  await page.getByRole("combobox", { name: "Run on", exact: true }).selectOption("cpu");
  await page.getByLabel("English only (faster and more accurate for English)").check();
  await page.getByRole("combobox", { name: "Speech recognition", exact: true }).selectOption("whisper-base.en-q5_1");
  await capture(page, "../../output/playwright/windows-managed-voice/01-selected.png");
  await page.getByRole("button", { name: "Install", exact: true }).click();
  const outcome = page.getByRole("status").filter({ hasText: /Installed and verified\.|Install failed:/ }).last();
  await expect(outcome).toBeVisible({ timeout: 600_000 });
  await expect(outcome).toContainText("Installed and verified.");
  const response = page.waitForResponse(r => new URL(r.url()).pathname === "/api/voice/test" && r.request().method() === "POST");
  await page.getByRole("button", { name: "Test", exact: true }).click();
  const result = await (await response).json();
  expect(result.spoke).toBe(true);
  expect(result.heard).toBe(true);
  expect(result.word_error_rate).toBeLessThanOrEqual(0.2);
  await expect(page.getByTestId("voice-test-result")).toContainText("Spoke and heard it back");
  await test.info().attach("managed-voice-result.json", { body: JSON.stringify(result), contentType: "application/json" });
  await capture(page, "../../output/playwright/windows-managed-voice/02-roundtrip.png");
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(page.getByText(/Remove every voice file/)).toBeVisible();
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: /Voice removed/ })).toBeVisible();
  await expect(page.getByText("On disk: 0 B", { exact: false })).toBeVisible();
  await capture(page, "../../output/playwright/windows-managed-voice/03-removed.png");
});
