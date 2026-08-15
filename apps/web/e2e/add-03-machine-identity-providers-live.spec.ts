import { expect, test, type BrowserContext, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";
import { hostedProviderCard } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const PASSWORD = "Add-03-live-review-password-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const OPENROUTER_KEY = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function connectProvider(provider: string, keyLabel: string, key: string): Promise<Locator> {
  const card = await hostedProviderCard(page, BASE, provider);
  await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
  await page.getByLabel(keyLabel).fill(key);
  await page.locator(".signin-connect").click();
  await expect(page.getByRole("dialog", { name: `Connect to ${provider}` })).toBeHidden({ timeout: 30_000 });
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 30_000 });
  return card;
}

async function chooseModel(card: Locator, preferred?: string): Promise<void> {
  await card.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = card.getByLabel("Available models");
  const custom = card.getByLabel("Custom model name");
  await expect(catalogue.or(custom)).toBeVisible({ timeout: 60_000 });
  if (await custom.isVisible()) {
    expect(preferred, `${await card.innerText()} needs an explicit model id`).toBeTruthy();
    await custom.fill(preferred!);
    await card.getByRole("button", { name: "Use model" }).click();
    return;
  }
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
  await expect(page.locator(".message-group-raiker").last()).toContainText(marker, { timeout: 240_000 });

  await page.goto(`${BASE}/#/activity`);
  const machine = page.locator(".identity-chip.machine").first();
  for (let retry = 0; retry < 8 && !(await machine.isVisible().catch(() => false)); retry += 1) {
    if (await page.getByText(/Unavailable \(429\)/).isVisible().catch(() => false)) {
      await page.waitForTimeout(5_000);
      await page.getByRole("button", { name: "Refresh events" }).click();
    } else {
      await page.waitForTimeout(500);
    }
  }
  await expect(machine).toBeVisible({ timeout: 30_000 });
  await expect(machine).toContainText("Raiker agent");
  await expect(machine).toContainText(/Agent · (active|inactive|expired)/);
  await page.screenshot({ path: join(SHOTS, screenshotName), fullPage: true });
}

async function waitForApprovalRow(status: "pending" | "denied"): Promise<Locator> {
  const row = page
    .getByRole("row")
    .filter({ has: page.getByRole("cell", { name: status, exact: true }) })
    .first();
  for (let retry = 0; retry < 8 && !(await row.isVisible().catch(() => false)); retry += 1) {
    if (await page.getByText(/Unavailable \(429\)/).isVisible().catch(() => false)) {
      await page.waitForTimeout(5_000);
      await page.getByRole("button", { name: "Refresh approvals" }).click();
    } else {
      await page.waitForTimeout(500);
    }
  }
  await expect(row).toBeVisible({ timeout: 30_000 });
  return row;
}

async function runGovernedProposal(marker: string, screenshotName: string): Promise<void> {
  await page.goto(`${BASE}/#/new-chat`);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await prompt.fill(
    `Use the write_file tool now to create add03-${marker.toLowerCase()}.txt containing exactly ${marker}. Do not answer without calling the tool.`,
  );
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Waiting for approval", { exact: true })).toBeVisible({ timeout: 240_000 });

  await page.goto(`${BASE}/#/approvals`);
  await page.getByLabel("Sort approvals").selectOption({ label: "Newest first" });
  const row = await waitForApprovalRow("pending");
  await row.getByRole("button", { name: "Review" }).click();
  await expect(page.getByRole("heading", { name: /^Review / })).toBeVisible({ timeout: 30_000 });
  let detail = page.getByLabel(/^Review /);
  await expect(detail.getByText("Proposed by", { exact: true })).toBeVisible();
  await expect(detail.locator(".identity-chip.machine")).toContainText("Raiker agent");
  await page.getByRole("button", { name: "Deny", exact: true }).click();
  await expect(page.getByText(/Recorded: denied/i)).toBeVisible({ timeout: 30_000 });
  for (let queued = 0; queued < 3; queued += 1) {
    const moreQueued = page.getByText(/more call.*queued behind it/i);
    if (!(await moreQueued.isVisible().catch(() => false))) break;
    await page.getByRole("tab", { name: "pending", exact: true }).click();
    const queuedRow = await waitForApprovalRow("pending");
    await queuedRow.getByRole("button", { name: "Review" }).click();
    await page.getByRole("button", { name: "Deny", exact: true }).click();
    await expect(page.getByText(/Recorded: denied/i)).toBeVisible({ timeout: 30_000 });
  }
  await page.getByRole("tab", { name: "denied", exact: true }).click();
  await page.getByRole("button", { name: "Refresh approvals" }).click();
  const deniedRow = await waitForApprovalRow("denied");
  await deniedRow.getByRole("button", { name: "Review" }).click();
  detail = page.getByLabel(/^Review /);
  await expect(detail.getByText("Authorized by", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(detail.locator(".identity-chip").filter({ hasText: "Human" })).toBeVisible();
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
  test.setTimeout(600_000);
  const card = await connectProvider("Anthropic", "Anthropic API key", ANTHROPIC_KEY);
  await chooseModel(card, "claude-haiku-4-5-20251001");
  await runAttributedTurn("ADD03 ANTHROPIC LIVE", "add03-anthropic-identity-live.png");
  await runGovernedProposal("anthropic", "add03-anthropic-approval-attribution-live.png");
});

test("OpenRouter turn records a signed machine actor", async () => {
  test.setTimeout(600_000);
  const card = await connectProvider("OpenRouter", "OpenRouter API key", OPENROUTER_KEY);
  await chooseModel(card, "openai/gpt-oss-20b:free");
  await runAttributedTurn("ADD03 OPENROUTER LIVE", "add03-openrouter-identity-live.png");
  await runGovernedProposal("openrouter", "add03-openrouter-approval-attribution-live.png");
});

test("Ollama gemma4:31b-cloud turn records a signed machine actor", async () => {
  test.setTimeout(600_000);
  await page.goto(`${BASE}/#/models`);
  const ollama = page.locator(".local-row").filter({ hasText: "Ollama" });
  await chooseModel(ollama, "gemma4:31b-cloud");
  await runAttributedTurn("ADD03 OLLAMA LIVE", "add03-ollama-identity-live.png");
  await runGovernedProposal("ollama", "add03-ollama-approval-attribution-live.png");
});
