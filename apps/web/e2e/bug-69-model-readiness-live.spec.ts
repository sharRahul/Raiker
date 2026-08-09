import { expect, test, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(
  import.meta.dirname,
  "..",
  "..",
  "..",
  "output",
  "playwright",
);
const PASSWORD = "Bug-69-live-review-password-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const OPENROUTER_KEY = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";

async function connectProvider(
  page: Page,
  provider: string,
  label: string,
  key: string,
) {
  const card = page
    .locator("article.provider-card")
    .filter({ hasText: provider });
  await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
  await page.getByLabel(label).fill(key);
  await page.locator(".signin-connect").click();
  await expect(card.getByText("Connected")).toBeVisible({ timeout: 30_000 });
  return card;
}

async function chooseModel(card: Locator, preferred?: string) {
  await card.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = card.getByLabel("Available models");
  const custom = card.getByLabel("Custom model name");
  await expect(catalogue.or(custom)).toBeVisible({ timeout: 60_000 });
  if (await catalogue.isVisible()) {
    const values = await catalogue
      .locator("option")
      .evaluateAll((options) =>
        options
          .map((option) => (option as HTMLOptionElement).value)
          .filter(Boolean),
      );
    const choice =
      preferred && values.includes(preferred) ? preferred : values[0];
    expect(choice).toBeTruthy();
    await catalogue.selectOption(choice);
  } else {
    expect(preferred, "provide an exact fallback model id").toBeTruthy();
    await custom.fill(preferred!);
  }
  await card.getByRole("button", { name: "Use model" }).click();
}

async function runReadyTurn(
  page: Page,
  provider: string,
  marker: string,
  generate = true,
  readyExpected = true,
  allowParkedApproval = false,
) {
  await page.goto(`${BASE}/#/new-chat`);
  const modelButton = page.getByRole("button", {
    name: /Model for this turn:/,
  });
  await modelButton.click();
  const providerGroup = page
    .locator(".model-provider-group")
    .filter({ hasText: provider });
  await expect(providerGroup).toBeVisible();
  await expect(modelButton.locator("img")).toHaveAttribute(
    "src",
    new RegExp(`/provider-logos/${provider.toLowerCase()}`),
  );
  await modelButton.click();
  const prompt = page.getByPlaceholder("How can I help you today?");
  await prompt.fill(`Reply with exactly: ${marker}`);
  const send = page.getByRole("button", { name: "Send" });
  if (await send.isDisabled()) {
    await modelButton.click();
    const selectedModel = (await modelButton.textContent())?.trim() ?? "";
    const setup = providerGroup
      .locator(".setup-choice")
      .filter({ hasText: selectedModel })
      .getByRole("button", { name: new RegExp(`^Set up ${provider} for`) });
    await expect(setup).toBeVisible();
    await setup.click();
    const dialog = page.getByRole("dialog", { name: /model/i });
    await dialog.getByRole("button", { name: "Check again" }).click();
    await expect(dialog.getByText("Check complete")).toBeVisible({
      timeout: 90_000,
    });
    if (!readyExpected) {
      await expect(
        dialog.getByText(/cannot execute|not reachable|rejected/i),
      ).toBeVisible();
    }
    await dialog.getByRole("button", { name: "Close" }).click();
  }
  if (!readyExpected) {
    await expect(send).toBeDisabled();
    return;
  }
  await expect(send).toBeEnabled({ timeout: 30_000 });
  if (!generate) return;
  await send.click();
  await expect(page.locator(".message-group-raiker").last()).toContainText(
    allowParkedApproval
      ? new RegExp(`${marker}|Approval required for local action`)
      : marker,
    { timeout: 240_000 },
  );
}

test("BUG-69 first-run, universal readiness gate, and three live providers", async ({
  page,
}) => {
  test.setTimeout(900_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  expect(OPENROUTER_KEY, "set RAIKER_LIVE_OPENROUTER_KEY").not.toBe("");
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({
    timeout: 30_000,
  });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirmPassword = page.getByLabel("Confirm password");
  if (await confirmPassword.isVisible()) {
    await confirmPassword.fill(PASSWORD);
    await page
      .getByRole("button", { name: "Create a User Account", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Choose how to run models" }),
    ).toBeVisible();
    await page.screenshot({
      path: join(SHOTS, "bug69-first-run-model-setup-live.png"),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Skip for now" }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker" }).click();
  }

  await page.goto(`${BASE}/#/workbench`);
  await page
    .getByLabel(/What would you like Raiker to do/)
    .fill("Draft a short project brief");
  await expect(
    page.getByRole("button", { name: "Start build" }),
  ).toBeDisabled();
  await page.screenshot({
    path: join(SHOTS, "bug69-workbench-readiness-gate-live.png"),
    fullPage: true,
  });

  await page.goto(`${BASE}/#/models`);
  await expect(page.getByRole("tab", { name: "Library" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Discover" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Activity" })).toBeVisible();
  await connectProvider(page, "Anthropic", "Anthropic API key", ANTHROPIC_KEY);
  await connectProvider(
    page,
    "OpenRouter",
    "OpenRouter API key",
    OPENROUTER_KEY,
  );
  await page.screenshot({
    path: join(SHOTS, "bug69-provider-setup-live.png"),
    fullPage: true,
  });

  await page.goto(`${BASE}/#/models`);
  const ollama = page.locator(".local-row").filter({ hasText: "Ollama" });
  await chooseModel(ollama, "gemma4:31b-cloud");
  await runReadyTurn(page, "Ollama", "BUG69 OLLAMA LIVE", false);
  await page.screenshot({
    path: join(SHOTS, "bug69-ollama-ready-live.png"),
    fullPage: true,
  });

  await page.goto(`${BASE}/#/models`);
  await chooseModel(
    page.locator("article.provider-card").filter({ hasText: "Anthropic" }),
    "claude-opus-4-8",
  );
  await runReadyTurn(page, "Anthropic", "BUG69 ANTHROPIC LIVE", false, false);
  await page.screenshot({
    path: join(SHOTS, "bug69-anthropic-account-block-live.png"),
    fullPage: true,
  });

  await page.goto(`${BASE}/#/models`);
  const openrouter = page
    .locator("article.provider-card")
    .filter({ hasText: "OpenRouter" });
  await chooseModel(openrouter, "openai/gpt-4o-mini");
  await runReadyTurn(
    page,
    "OpenRouter",
    "BUG69 OPENROUTER LIVE",
    true,
    true,
    true,
  );
  await page.screenshot({
    path: join(SHOTS, "bug69-three-provider-ready-live.png"),
    fullPage: true,
  });

  expect(consoleErrors).toEqual([]);
});
