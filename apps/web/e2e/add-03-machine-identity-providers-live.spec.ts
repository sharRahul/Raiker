import { expect, test, type BrowserContext, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const PASSWORD = "Add-03-live-review-password-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const OPENROUTER_KEY = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function connectProvider(provider: string, keyLabel: string, key: string): Promise<Locator> {
  await page.goto(`${BASE}/#/models`);
  const card = page.locator("article.provider-card").filter({ hasText: provider });
  await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
  await page.getByLabel(keyLabel).fill(key);
  await page.locator(".signin-connect").click();
  await expect(page.getByRole("dialog", { name: `Connect to ${provider}` })).toBeHidden({ timeout: 30_000 });
  await expect(card.getByText("Connected")).toBeVisible({ timeout: 30_000 });
  return card;
}

async function chooseModel(card: Locator, preferred?: string): Promise<void> {
  await card.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = card.getByLabel("Available models");
  await expect(catalogue).toBeVisible({ timeout: 60_000 });
  const values = await catalogue.locator("option").evaluateAll((options) =>
    options.map((option) => (option as HTMLOptionElement).value).filter(Boolean),
  );
  const selected = preferred && values.includes(preferred) ? preferred : values[0];
  expect(selected, `${await card.innerText()} returned a selectable model`).toBeTruthy();
  await catalogue.selectOption(selected);
  await card.getByRole("button", { name: "Use model" }).click();
}

async function runAttributedTurn(marker: string, screenshotName: string): Promise<void> {
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 30_000 });
  await prompt.fill(`Reply with exactly: ${marker}`);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("button", { name: "Copy response" }).last()).toBeVisible({ timeout: 240_000 });
  await expect(page.locator(".message-group-raiker").last()).toContainText(marker);

  await page.goto(`${BASE}/#/activity`);
  const machine = page.locator(".identity-chip.machine").first();
  await expect(machine).toBeVisible({ timeout: 30_000 });
  await expect(machine).toContainText("Raiker agent");
  await expect(machine).toContainText(/Agent · (active|inactive|expired)/);
  await page.screenshot({ path: join(SHOTS, screenshotName), fullPage: true });
}

test.beforeAll(async ({ browser }) => {
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  expect(OPENROUTER_KEY, "set RAIKER_LIVE_OPENROUTER_KEY").not.toBe("");
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  page = await context.newPage();
  await page.goto(`${BASE}/#/models`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 30_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible()) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }
  await expect(page.getByRole("heading", { name: "Models", level: 1 })).toBeVisible({ timeout: 30_000 });
});

test.afterAll(async () => await context?.close());

test("Permissions separates owner controls from signed-turn authority", async () => {
  await page.goto(`${BASE}/#/capabilities`);
  await expect(page.getByRole("heading", { name: "Owner sets the boundary. The agent inherits less." })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Owner control" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Raiker agent" })).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "add03-owner-agent-authority-live.png"), fullPage: true });
});

test("Anthropic turn records a signed machine actor", async () => {
  test.setTimeout(360_000);
  const card = await connectProvider("Anthropic", "Anthropic API key", ANTHROPIC_KEY);
  await chooseModel(card, "claude-haiku-4-5-20251001");
  await runAttributedTurn("ADD03 ANTHROPIC LIVE", "add03-anthropic-identity-live.png");
});

test("OpenRouter turn records a signed machine actor", async () => {
  test.setTimeout(360_000);
  const card = await connectProvider("OpenRouter", "OpenRouter API key", OPENROUTER_KEY);
  await chooseModel(card);
  await runAttributedTurn("ADD03 OPENROUTER LIVE", "add03-openrouter-identity-live.png");
});

test("Ollama gemma4:31b-cloud turn records a signed machine actor", async () => {
  test.setTimeout(360_000);
  await page.goto(`${BASE}/#/models`);
  const ollama = page.locator(".local-row").filter({ hasText: "Ollama" });
  await chooseModel(ollama, "gemma4:31b-cloud");
  await runAttributedTurn("ADD03 OLLAMA LIVE", "add03-ollama-identity-live.png");
});
