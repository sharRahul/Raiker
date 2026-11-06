/** Real provider calls. Keys come only from a private, ephemeral local file. */
import { readFileSync, mkdirSync, existsSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { hostedProviderCard, openProviderDetails, openModelDialog, keepOffered, checkModelReady, signInAsOwner } from "./hosted-provider";
import { modelName } from "../src/lib/modelPresentation";
import { LIVE_BASE as BASE } from "./live";

const path = process.env.RAIKER_LIVE_CREDENTIALS_FILE;
const credentials: Record<string, string> = path ? JSON.parse(readFileSync(path, "utf8")) : {};
const shots = "../../output/playwright/2026-11-06-models-real-providers";
const report = resolve(import.meta.dirname, "../../output/playwright/2026-11-06-models-real-providers/outcomes.json");
const legs = [
  { id: "anthropic", name: "Anthropic", label: "Anthropic API key", profile: "anthropic-hosted", preferred: "claude-haiku-4-5-20251001" },
  { id: "openrouter", name: "OpenRouter", label: "OpenRouter API key", profile: "openrouter-policy-gated", preferred: "openai/gpt-4o-mini" },
  { id: "openai", name: "OpenAI", label: "OpenAI API key", profile: "openai-hosted", preferred: "gpt-4o-mini" },
];
function safe(value: string): string {
  return Object.values(credentials).filter(Boolean).reduce((text, secret) => text.replaceAll(secret, "[private value]"), value);
}
function record(id: string, value: Record<string, unknown>) {
  mkdirSync(resolve(report, ".."), { recursive: true });
  const previous = existsSync(report) ? JSON.parse(readFileSync(report, "utf8")) : {};
  writeFileSync(report, JSON.stringify({ ...previous, [id]: value }, null, 2), { mode: 0o600 });
}
async function assertNoKeyOnPage(page: Page, key: string) {
  expect((await page.content()).includes(key), "The saved key must never be rendered back").toBe(false);
}
for (const leg of legs) {
  test(`RT-MODELS-PROVIDER-${leg.id}: UI sign-in, exact model, real response`, async ({ page }) => {
    test.setTimeout(360_000);
    test.skip(!credentials[leg.id], "Provide a private credential file for this deliberate live run");
    page.setDefaultTimeout(30_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await signInAsOwner(page, BASE);
    let model = leg.preferred;
    try {
      const card = await hostedProviderCard(page, BASE, leg.name);
      const connect = card.getByRole("button", { name: "Connect", exact: true });
      if (await connect.isVisible()) await connect.click();
      else {
        await openProviderDetails(page, card);
        await page.getByRole("button", { name: "Reconnect", exact: true }).click();
      }
      const keyInput = page.getByLabel(leg.label, { exact: true });
      await expect(keyInput).toHaveAttribute("type", "password");
      await keyInput.fill(credentials[leg.id]);
      if (leg.id === "anthropic" && credentials.workspace) {
        await page.getByRole("button", { name: "Advanced", exact: true }).last().click();
        await page.getByLabel(/Workspace ID/).fill(credentials.workspace);
      }
      await page.locator(".signin-connect").click();
      await expect(page.locator(".signin-overlay")).toHaveCount(0, { timeout: 60_000 });
      await expect(card.getByText("Connection saved", { exact: true })).toBeVisible({ timeout: 60_000 });
      await assertNoKeyOnPage(page, credentials[leg.id]);
      const picker = await openModelDialog(page, card);
      const ids = await picker.locator('input[type="checkbox"]').evaluateAll(items => items.map(item => (item as HTMLInputElement).value));
      await captureElement(picker, `${shots}/${leg.id}-catalogue.png`);
      if (ids.length > 0) {
        model = ids.includes(leg.preferred) ? leg.preferred : ids.find(id => /haiku|mini/i.test(id)) ?? ids[0];
        await keepOffered(picker, model);
      } else {
        await picker.getByRole("textbox", { name: "Custom model name", exact: true }).fill(model);
        await picker.getByRole("button", { name: "Use model", exact: true }).click();
        await expect(picker).toHaveCount(0, { timeout: 60_000 });
      }
      const refreshed = await hostedProviderCard(page, BASE, leg.name);
      await checkModelReady(page, refreshed);
      const status = safe(await refreshed.innerText());
      await assertNoKeyOnPage(page, credentials[leg.id]);
      await capture(page, `${shots}/${leg.id}-ready.png`, refreshed);
      if (/no credit|no quota|key rejected|rejected.*key|could not be reached|cannot execute|identity-linked|needs a workspace/i.test(status)) {
        record(leg.id, { provider: leg.name, model, outcome: "blocked", status, credential_entry: "UI", captured_at: new Date().toISOString() });
        test.info().annotations.push({ type: "provider-blocked", description: status });
        return;
      }
      await page.goto(`${BASE}/#/new-chat`);
      const composer = page.getByRole("group", { name: "Message composer", exact: true });
      await expect(composer).toBeVisible({ timeout: 60_000 });
      await composer.getByRole("button", { name: /^Model for this turn:/ }).click();
      const group = page.getByRole("menu", { name: "Models", exact: true }).getByRole("group", { name: `${leg.name} models`, exact: true });
      await group.getByRole("menuitemradio").filter({ hasText: modelName(model) }).first().click();
      const calculations: Record<string, { question: string; answer: string }> = {
        anthropic: { question: "17 + 25", answer: "42" },
        openrouter: { question: "19 + 24", answer: "43" },
        openai: { question: "21 + 23", answer: "44" },
      };
      const check = calculations[leg.id];
      const marker = check.answer;
      await page.getByPlaceholder("What would you like Raiker to do?", { exact: true }).fill(`What is ${check.question}? Reply only with the number. Do not use tools.`);
      const sent = page.waitForRequest(request => request.url().endsWith("/api/prompts/stream") && request.method() === "POST");
      await composer.getByRole("button", { name: "Send", exact: true }).click();
      const request = (await sent).postDataJSON();
      expect(request.model_profile).toBe(leg.profile);
      expect(request.model).toBe(model);
      await expect(page.getByRole("button", { name: "Copy response", exact: true }).last()).toBeVisible({ timeout: 180_000 });
      await expect(page.locator(".message-group-raiker").last()).toContainText(marker);
      await assertNoKeyOnPage(page, credentials[leg.id]);
      await capture(page, `${shots}/${leg.id}-real-turn.png`, page.locator(".message-group-raiker").last());
      record(leg.id, { provider: leg.name, model, outcome: "passed", credential_entry: "UI", exact_pair: true, response_marker: marker, captured_at: new Date().toISOString() });
    } catch (error) {
      record(leg.id, { provider: leg.name, model, outcome: "failed", error: safe(error instanceof Error ? error.message : String(error)), credential_entry: "UI", captured_at: new Date().toISOString() });
      throw error;
    }
  });
}
