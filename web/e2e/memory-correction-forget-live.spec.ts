/** T-04 slice: real owner import, correction and forget, then local-model recall.
 * Use a disposable instance with Qwen 2.5 coder:7B already selected through Models.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { checkModelReady, chooseModelForTurn, enableCapability, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE, sendTurn } from "./live";

const first = "My trial tea is jasmine green tea.";
const corrected = "My trial tea is roasted barley tea.";

async function recall(page: Page, newConversation = false) {
  await page.goto(`${BASE}/#/new-chat`);
  if (newConversation) await page.getByRole("button", { name: "New chat", exact: true }).click();
  await expect(page.locator(".message-group-raiker")).toHaveCount(0);
  await chooseModelForTurn(page, /Qwen.*2\.5.*coder.*7B/i);
  await sendTurn(page, "What is my trial tea?");
  await expect(page.getByTestId("turn-receipt").last()).toBeVisible({ timeout: 180_000 });
  await expect(page.locator(".message-group-raiker .response-actions")).toBeVisible({ timeout: 180_000 });
  return page.locator(".message-group-raiker").last();
}

test("T-04 owner correction replaces recall and forgetting removes it", async ({ page }) => {
  test.setTimeout(600_000);
  page.setDefaultTimeout(30_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/models?tab=add&source=local`);
  const ollama = page.locator(".local-row").filter({ has: page.getByRole("heading", { name: "Ollama", exact: true }) });
  await keepModelAvailable(page, ollama, "qwen2.5-coder:7b");
  await page.goto(`${BASE}/#/models?tab=add&source=local`);
  await checkModelReady(page, ollama);
  await enableCapability(page, BASE, "Memory store", "Disposable personal-beta test of a synthetic tea preference");
  await page.goto(`${BASE}/#/memory?tab=controls`);
  await page.getByText("Advanced memory management", { exact: true }).click();
  await page.locator('.file-button input[type="file"]').setInputFiles({
    name: "synthetic-tea.json", mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ memories: [{ text: first, scope: "account" }] })),
  });
  await page.getByRole("button", { name: /^Import (1 record|reviewed records)$/ }).click();
  await expect(page.getByText(/^Imported 1 record\./)).toBeVisible();
  let answer = await recall(page);
  await expect(answer.locator(".message-bubble-raiker")).toContainText(/jasmine green/i);
  await expect(answer.getByRole("region", { name: "Memories used in this answer" })).toBeVisible();
  await capture(page, "../../output/playwright/windows-memory/01-recalled.png");

  await page.goto(`${BASE}/#/memory?tab=memories`);
  const card = page.locator(".memory-card").filter({ hasText: first });
  await card.getByRole("button", { name: "Edit memory", exact: true }).click();
  await page.getByLabel("Memory text").fill(corrected);
  await page.getByRole("button", { name: "Save memory", exact: true }).click();
  await expect(page.getByRole("heading", { name: corrected, exact: true })).toBeVisible();
  answer = await recall(page, true);
  await expect(answer.locator(".message-bubble-raiker")).toContainText(/roasted barley/i);
  await expect(answer.locator(".message-bubble-raiker")).not.toContainText(/jasmine green/i);
  await capture(page, "../../output/playwright/windows-memory/02-corrected.png");

  await page.goto(`${BASE}/#/memory?tab=memories`);
  const revised = page.locator(".memory-card").filter({ hasText: corrected });
  await revised.getByRole("button", { name: /^More for/ }).click();
  await revised.getByRole("button", { name: "Forget", exact: true }).click();
  await page.getByRole("dialog", { name: "Forget this memory?" }).getByRole("button", { name: "Forget", exact: true }).click();
  await expect(page.getByRole("heading", { name: corrected, exact: true })).toHaveCount(0);
  answer = await recall(page, true);
  await expect(answer.getByRole("region", { name: "Memories used in this answer" })).toHaveCount(0);
  await expect(answer.locator(".message-bubble-raiker")).not.toContainText(/roasted barley|jasmine green/i);
  await capture(page, "../../output/playwright/windows-memory/03-forgotten.png");
});
