import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { OWNER_CREDENTIALS, hostedProviderCard, keepModelAvailable, keepOffered, offeredModelIds, openModelDialog } from "./hosted-provider";
import { LIVE_BASE as BASE, ANTHROPIC_KEY } from "./live";

const SHOTS = join(import.meta.dirname, "..", "..", "output", "playwright");
const PASSWORD = OWNER_CREDENTIALS.password;
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
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 30_000 });
  return card;
}

async function chooseFirstModel(card: ReturnType<Page["locator"]>, preferred?: string) {
  const dialog = await openModelDialog(page, card);
  const values = await offeredModelIds(dialog);
  const model = preferred && values.includes(preferred) ? preferred : values[0];
  expect(model, "provider returned at least one selectable model").toBeTruthy();
  await keepOffered(dialog, model);
}

async function runTurn(marker: string) {
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("What would you like Raiker to do?");
  await expect(prompt).toBeVisible({ timeout: 30_000 });
  await prompt.fill(`Reply with exactly: ${marker}`);
  await page.getByRole("button", { name: "Send", exact: true }).click();
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
  await expect(page.getByText(/Checking Raiker/)).toBeHidden({ timeout: 30_000 });
  await page.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
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
  await capture(page, join(SHOTS, "add01-providers-connected-live.png"));

  await chooseFirstModel(anthropic, "claude-haiku-4-5-20251001");
  await runTurn("ADD01 ANTHROPIC LIVE");
  await capture(page, join(SHOTS, "add01-anthropic-turn-live.png"));

  const openrouterAgain = await hostedProviderCard(page, BASE, "OpenRouter");
  await chooseFirstModel(openrouterAgain);
  await runTurn("ADD01 OPENROUTER LIVE");
  await capture(page, join(SHOTS, "add01-openrouter-turn-live.png"));
});

test("Ollama gemma4:31b-cloud answers a real turn", async () => {
  test.setTimeout(360_000);
  await page.goto(`${BASE}/#/models`);
  const ollama = page.locator(".local-row").filter({ hasText: "Ollama" });
  await keepModelAvailable(page, ollama, "gemma4:31b-cloud");
  await runTurn("ADD01 OLLAMA LIVE");
  await capture(page, join(SHOTS, "add01-ollama-turn-live.png"));
});

test("commands run in the local sandbox and no container environment is offered", async () => {
  test.setTimeout(120_000);
  // Docker and Podman were removed: the only local target is the native OS
  // sandbox, and adding an environment offers remote targets only.
  await page.goto(`${BASE}/#/settings?tab=runtime`);
  const card = page.locator("article").filter({ hasText: "Local sandbox" });
  await expect(card).toBeVisible({ timeout: 60_000 });
  await page.getByText("Add execution profile").click();
  const kinds = await page.getByLabel("Environment type").locator("option").evaluateAll(
    (options) => options.map((option) => (option as HTMLOptionElement).value),
  );
  expect(kinds).toEqual(["ssh", "daytona"]);
  await capture(page, join(SHOTS, "add01-local-sandbox-live.png"));
  await page.goto(`${BASE}/#/build`);
  await expect(page.getByLabel("Execution environment")).toContainText("Local sandbox");
});
