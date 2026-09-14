/** Live closure evidence for restart persistence, provider reachability and the
 * final shared-composer behaviours. This spec uses the owner's existing Raiker
 * workspace; credentials are entered through Models before the run and never
 * appear in source or captures. */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "plans", "screenshots", "working");

async function runOverflowAction(page: Page, row: Locator, provider: string, action: string) {
  await row.getByRole("button", { name: new RegExp(`^More actions for ${provider}`, "i") }).click();
  await page.getByRole("menuitem", { name: action, exact: true }).click();
}

async function ensureOpenAiModel(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/models?tab=add`);
  const card = page.locator("article.provider-card", { hasText: "OpenAI" }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  if (await card.getByText("GPT-4o Mini", { exact: true }).isVisible().catch(() => false)) return;
  const direct = card.getByRole("button", { name: /^Select models/ });
  await expect(direct).toBeVisible({ timeout: 30_000 });
  await direct.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 60_000 });
  const custom = dialog.getByLabel("Custom model name");
  if (await custom.isVisible().catch(() => false)) {
    await custom.fill("gpt-4o-mini");
    await dialog.getByRole("button", { name: "Use model" }).click();
    return;
  }
  const wanted = dialog.getByRole("checkbox", { name: /^GPT-4o Mini$/i });
  await expect(wanted).toBeVisible({ timeout: 60_000 });
  await wanted.check();
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden({ timeout: 60_000 });
}

test.beforeEach(async ({ page }) => {
  await signInAsOwner(page, BASE);
});

test("memory authority and all four saved provider paths survive a host restart", async ({ page }) => {
  test.setTimeout(300_000);
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByLabel("Search capabilities");
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill("Memory store");
  const memory = page.locator(".cap.card", { hasText: "Memory store" }).first();
  await memory.getByRole("button", { name: "Memory store" }).click();
  await expect(memory.getByRole("button", { name: "Turn off" })).toBeVisible();
  await expect(memory.getByRole("button", { name: "Allow", exact: true })).toHaveAttribute("aria-pressed", "true");
  await capture(page, join(SHOTS, "memory-write-allow-after-restart.png"));

  await page.goto(`${BASE}/#/models?tab=add`);
  for (const provider of ["Anthropic", "OpenAI", "OpenRouter"]) {
    const card = page.locator("article.provider-card", { hasText: provider }).first();
    await expect(card.getByText("Connection saved", { exact: true })).toBeVisible();
    await runOverflowAction(page, card, provider, "Test connection");
    const result = card.locator("[data-test-result]");
    await expect(result, `${provider} did not return a connection result`).not.toBeEmpty({ timeout: 90_000 });
    test.info().annotations.push({ type: provider, description: (await result.innerText()).trim() });
  }

  const ollama = page.locator(".local-row", { has: page.getByRole("heading", { name: "Ollama", exact: true }) }).first();
  await expect(ollama.getByText("Cloud inference", { exact: true })).toBeVisible();
  await expect(ollama.getByText("Provider pricing may apply", { exact: true })).toBeVisible();
  await runOverflowAction(page, ollama, "Ollama", "Test connection");
  const ollamaResult = ollama.locator("[data-test-result]");
  await expect(ollamaResult, "Ollama did not return a connection result").not.toBeEmpty({ timeout: 120_000 });
  test.info().annotations.push({ type: "Ollama", description: (await ollamaResult.innerText()).trim() });
  await capture(page, join(SHOTS, "models-four-providers-after-restart.png"));
});

test("the Work draft follows its project and a large paste is reversible", async ({ page }) => {
  const draftText = "Shared draft across Chat, Build and Design";
  await page.goto(`${BASE}/#/new-chat`);
  await page.getByLabel("Prompt", { exact: true }).fill(draftText);
  await page.goto(`${BASE}/#/build`);
  await expect(page.getByLabel("Describe the change", { exact: true })).toHaveValue(draftText);
  await page.goto(`${BASE}/#/design`);
  await expect(page.getByLabel("Describe the image", { exact: true })).toHaveValue(draftText);

  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByLabel("Prompt", { exact: true });
  await prompt.fill("");
  const pasted = `BEGIN\n${"exact pasted text ".repeat(250)}\nEND`;
  await prompt.evaluate((element, text) => {
    const data = new DataTransfer();
    data.setData("text/plain", text);
    element.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: data }));
  }, pasted);
  await expect(page.getByText("pasted-text.txt", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(prompt).toHaveValue("");
  await capture(page, join(SHOTS, "composer-large-paste-attachment.png"));
  await page.getByRole("button", { name: "Show pasted-text.txt inline" }).click();
  await expect(prompt).toHaveValue(pasted);
});

test("memory_write executes directly and the fact can be recalled after restart", async ({ page }) => {
  test.setTimeout(300_000);
  const marker = `Raiker-memory-E2E-${Date.now()}`;
  const fact = `${marker}: restart verification completed on 2026-09-08.`;
  await ensureOpenAiModel(page);
  const before = await page.evaluate(async () => {
    const response = await fetch("/api/memory");
    return (await response.json()) as Array<{ memory_id: string; text: string }>;
  });
  // Sign-in may land on the last conversation. Leave the route first so Chat
  // mounts with no session id rather than inheriting an earlier parked turn.
  await page.goto(`${BASE}/#/home`);
  await page.goto(`${BASE}/#/new-chat`);
  const modelControl = page.getByRole("button", { name: /^Model for this turn/ });
  await modelControl.click();
  const openAiModels = page.getByRole("menu", { name: "Models" }).getByRole("group", { name: /OpenAI models/i });
  await openAiModels.getByRole("menuitemradio", { name: /GPT-4o Mini/i }).first().click();
  const prompt = page.getByLabel("Prompt", { exact: true });
  await prompt.fill(`Use memory_write to remember this exact durable fact: ${fact} Then reply with the tool name you used.`);
  const send = page.getByRole("button", { name: "Send", exact: true });
  await expect(send).toBeEnabled({ timeout: 30_000 });
  await send.click();
  const answer = page.locator(".message-group-raiker").last();
  await expect(answer).toContainText(/memory_write|remembered|saved/i, { timeout: 240_000 });

  const beforeIds = new Set(before.map((memory) => memory.memory_id));
  const after = await page.evaluate(async () => {
    const response = await fetch("/api/memory");
    return (await response.json()) as Array<{
      memory_id: string;
      text: string;
      approval_state: string;
    }>;
  });
  const created = after.find(
    (memory) => !beforeIds.has(memory.memory_id) && memory.text.includes(marker),
  );
  expect(created, "the turn should create a memory containing its unique marker").toBeDefined();
  expect(created?.approval_state).toBe("policy_allowed");

  await page.goto(`${BASE}/#/memory`);
  const search = page.getByLabel("Search memories");
  await expect(search).toBeVisible({ timeout: 30_000 });
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith("/api/memory") && response.ok()),
    page.getByRole("button", { name: "Refresh", exact: true }).click(),
  ]);
  await search.fill(marker);
  await expect(page.locator(".memory-card", { hasText: marker }).first()).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "memory-write-recalled-after-restart.png"));
});
