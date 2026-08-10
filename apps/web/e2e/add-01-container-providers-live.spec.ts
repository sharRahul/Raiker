import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { join } from "node:path";
import { hostedProviderCard } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const PASSWORD = "Add-01-live-review-password-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const OPENROUTER_KEY = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function connectProvider(provider: string, keyLabel: string, key: string) {
  const card = await hostedProviderCard(page, BASE, provider);
  await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
  await page.getByLabel(keyLabel).fill(key);
  await page.locator(".signin-connect").click();
  await expect(page.getByRole("dialog", { name: `Connect to ${provider}` })).toBeHidden({ timeout: 30_000 });
  await expect(card.getByText("Connected")).toBeVisible({ timeout: 30_000 });
  return card;
}

async function chooseFirstModel(card: ReturnType<Page["locator"]>, preferred?: string) {
  await card.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = card.getByLabel("Available models");
  await expect(catalogue).toBeVisible({ timeout: 60_000 });
  const values = await catalogue.locator("option").evaluateAll((options) =>
    options.map((option) => (option as HTMLOptionElement).value).filter(Boolean),
  );
  const model = preferred && values.includes(preferred) ? preferred : values[0];
  expect(model, "provider returned at least one selectable model").toBeTruthy();
  await catalogue.selectOption(model);
  await card.getByRole("button", { name: "Use model" }).click();
}

async function runTurn(marker: string) {
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 30_000 });
  await prompt.fill(`Reply with exactly: ${marker}`);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("button", { name: "Copy response" }).last()).toBeVisible({
    timeout: 240_000,
  });
  await expect(page.locator(".message-group-raiker").last()).toContainText(marker);
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

test("Anthropic and OpenRouter credentials are entered through UI and answer real turns", async () => {
  test.setTimeout(600_000);
  const anthropic = await connectProvider("Anthropic", "Anthropic API key", ANTHROPIC_KEY);
  await connectProvider("OpenRouter", "OpenRouter API key", OPENROUTER_KEY);
  await page.screenshot({ path: join(SHOTS, "add01-providers-connected-live.png"), fullPage: true });

  await chooseFirstModel(anthropic, "claude-haiku-4-5-20251001");
  await runTurn("ADD01 ANTHROPIC LIVE");
  await page.screenshot({ path: join(SHOTS, "add01-anthropic-turn-live.png"), fullPage: true });

  const openrouterAgain = await hostedProviderCard(page, BASE, "OpenRouter");
  await chooseFirstModel(openrouterAgain);
  await runTurn("ADD01 OPENROUTER LIVE");
  await page.screenshot({ path: join(SHOTS, "add01-openrouter-turn-live.png"), fullPage: true });
});

test("Ollama gemma4:31b-cloud answers a real turn", async () => {
  test.setTimeout(360_000);
  await page.goto(`${BASE}/#/models`);
  const ollama = page.locator(".local-row").filter({ hasText: "Ollama" });
  await ollama.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = ollama.getByLabel("Available models");
  await expect(catalogue).toBeVisible({ timeout: 60_000 });
  await catalogue.selectOption("gemma4:31b-cloud");
  await ollama.getByRole("button", { name: "Use model" }).click();
  await runTurn("ADD01 OLLAMA LIVE");
  await page.screenshot({ path: join(SHOTS, "add01-ollama-turn-live.png"), fullPage: true });
});

test("container profile is enabled, configured, selected, and visibly bounded", async () => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/capabilities`);
  const capability = page.locator(".cap.card").filter({ hasText: "Container execution" });
  await capability.locator("button.cap-toggle").click();
  const turnOn = capability.getByRole("button", { name: "Turn on" });
  if (await turnOn.isVisible()) {
    await turnOn.click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Reason (required)").fill("Live validation of the approved container boundary");
    const token = dialog.getByLabel(/Confirmation token/);
    if (await token.isVisible()) await token.fill("ADD01 LIVE CONFIRM");
    const acknowledgement = dialog.getByLabel(/reviewed the threat model/);
    if (await acknowledgement.isVisible()) await acknowledgement.check();
    await dialog.getByRole("button", { name: "Confirm change" }).click();
    await expect(dialog).toBeHidden({ timeout: 30_000 });
  }

  await page.goto(`${BASE}/#/settings?tab=runtime`);
  const profileName = `Docker repository review ${Date.now()}`;
  await page.getByText("Add execution profile").click();
  await page.getByLabel("Environment type").selectOption("container");
  await page.getByLabel("Display name").fill(profileName);
  await page.getByLabel("Container runtime").selectOption("docker");
  await page.getByLabel("Approved image").selectOption("python:3.12-alpine");
  await page.getByLabel("read_file").check();
  await page.getByLabel("grep").check();
  await page.getByRole("button", { name: "Save environment" }).click();

  const card = page.locator("article").filter({ hasText: profileName });
  await expect(card.getByText("Docker · python:3.12-alpine")).toBeVisible({ timeout: 30_000 });
  await expect(card.getByText("Read-only repository → writable output")).toBeVisible();
  await expect(card.getByText("2 tools")).toBeVisible();
  await card.getByRole("button", { name: "Select" }).click();
  await expect(card.getByRole("button", { name: "Selected" })).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: join(SHOTS, "add01-container-profile-live.png"), fullPage: true });
  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByLabel("Execution environment")).toContainText(`${profileName} · Docker · Ready`);
});
