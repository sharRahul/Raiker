/** MD-1: requires provider credentials already saved through the owner UI. */
import { expect, test } from "@playwright/test";
import { hostedProviderCard, keepModelAvailable, refreshHostedReadiness, chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE, sendTurn } from "./live";
import { capture } from "./capture";

test.describe.configure({ mode: "serial", timeout: 240_000 });
for (const provider of ["OpenAI", "OpenRouter"]) {
  test(`MD-1 saved ${provider} answers a real Chat turn`, async ({ page }) => {
    await signInAsOwner(page, BASE);
    const card = await hostedProviderCard(page, BASE, provider);
    await expect(card.getByText("Connection saved", { exact: true })).toBeVisible();
    const model = provider === "OpenAI" ? "gpt-5-nano" : "openai/gpt-4o-mini";
    await keepModelAvailable(page, card, model);
    await refreshHostedReadiness(page, BASE, provider);
    await page.goto(`${BASE}/#/new-chat`);
    await chooseModelForTurn(page, provider === "OpenAI" ? /GPT-5 Nano/i : /GPT-4o Mini/i);
    await sendTurn(page, "Reply with exactly: RAIKER_PROVIDER_OK");
    await expect(page.getByTestId("turn-receipt").last()).toBeVisible({ timeout: 180_000 });
    await expect(page.getByText("RAIKER_PROVIDER_OK", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Stop all work (nothing is running)", exact: true })).toBeVisible({ timeout: 30_000 });
    await capture(page, `../../output/playwright/windows-provider-${provider.toLowerCase()}.png`);
  });
}

for (const [provider, model, label] of [
  ["Ollama", "qwen2.5-coder:7b", /Qwen.*2\.5.*coder.*7B/i],
  ["LM Studio", "qwen/qwen3-8b", /Qwen.*3.*8B/i],
] as const) {
  test(`MD-1 local ${provider} answers a real Chat turn`, async ({ page }) => {
    await signInAsOwner(page, BASE);
    await page.goto(`${BASE}/#/models?tab=add&source=local`);
    const card = page.locator(".local-row").filter({ has: page.getByRole("heading", { name: provider, exact: true }) });
    await expect(card).toBeVisible();
    await keepModelAvailable(page, card, model);
    await page.goto(`${BASE}/#/models?tab=add&source=local`);
    const { checkModelReady } = await import("./hosted-provider");
    await checkModelReady(page, card);
    await page.goto(`${BASE}/#/new-chat`);
    await chooseModelForTurn(page, label);
    await sendTurn(page, "Reply with exactly: RAIKER_LOCAL_OK");
    await expect(page.getByTestId("turn-receipt").last()).toBeVisible({ timeout: 180_000 });
    await expect(page.getByText("RAIKER_LOCAL_OK", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Stop all work (nothing is running)", exact: true })).toBeVisible({ timeout: 30_000 });
    await capture(page, `../../output/playwright/windows-provider-${provider.toLowerCase().replaceAll(" ", "-")}.png`);
  });
}
