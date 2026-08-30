/**
 * Four-provider live proof for the governed Build terminal.
 *
 * Every leg uses the product UI to select/connect the provider, asks the real
 * model to propose the exact same bounded command, approves that proposal in
 * Approvals, and verifies Build's redacted output plus immutable receipt. No
 * credential is committed or sent through a test-only API.
 *
 * Prerequisites:
 *   1. `raiker-web --workspace <fresh ws> --port 8765 --no-browser`
 *   2. the three RAIKER_LIVE_*_KEY variables and RAIKER_LIVE_OLLAMA_MODEL
 */
import { expect, test, type BrowserContext, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";
import { dismissFirstRunModelSetup, hostedProviderCard, OWNER_CREDENTIALS, useHostedModel } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");
const PASSWORD = OWNER_CREDENTIALS.password;

interface ProviderLeg {
  provider: string;
  keyLabel?: string;
  key?: string;
  model: string;
}

const LEGS: ProviderLeg[] = [
  {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "",
    model: "claude-sonnet-4-6",
  },
  {
    provider: "OpenRouter",
    keyLabel: "OpenRouter API key",
    key: process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "",
    model: "openai/gpt-oss-20b:free",
  },
  {
    provider: "OpenAI",
    keyLabel: "OpenAI API key",
    key: process.env.RAIKER_LIVE_OPENAI_KEY ?? "",
    model: "gpt-4o-mini",
  },
  {
    provider: "Ollama",
    model: process.env.RAIKER_LIVE_OLLAMA_MODEL ?? "",
  },
];

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

async function signIn(): Promise<void> {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 30_000 });
  await page.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  const welcome = page.getByRole("heading", { name: /Welcome/ });
  const setup = page.getByRole("button", { name: /Decide later|Skip for now/ });
  await expect(welcome.or(setup).first()).toBeVisible({ timeout: 30_000 });
  if (await setup.isVisible().catch(() => false)) await dismissFirstRunModelSetup(page);
  await expect(welcome).toBeVisible({ timeout: 30_000 });
}

async function setCapability(label: string, reason: string): Promise<void> {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByPlaceholder("Search capabilities…");
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill(label);
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible();
  if ((await card.getByRole("button", { name: label }).getAttribute("aria-expanded")) !== "true") {
    await card.getByRole("button", { name: label }).click();
  }
  const turnOn = card.getByRole("button", { name: "Turn on" });
  if (!(await turnOn.isVisible().catch(() => false))) return;
  await turnOn.click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Reason (required)").fill(reason);
  const token = dialog.getByLabel(/Confirmation token/);
  if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
  const acknowledgement = dialog.getByRole("checkbox");
  if (await acknowledgement.isVisible().catch(() => false)) await acknowledgement.check();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

async function chooseOllama(model: string): Promise<void> {
  await page.goto(`${BASE}/#/models?tab=local`);
  const row = page.locator(".local-row").filter({ hasText: "Ollama" });
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByRole("button", { name: /Choose model|Change model/ }).click();
  const catalogue = row.getByLabel("Available models");
  await expect(catalogue).toBeVisible({ timeout: 60_000 });
  await catalogue.selectOption(model);
  await row.getByRole("button", { name: "Use model" }).click();
  const pinned = page.locator(".local-row").filter({ hasText: "Ollama" });
  await pinned.getByRole("button", { name: "Test", exact: true }).click();
  await expect(pinned.getByText(/can reach/i)).toBeVisible({ timeout: 120_000 });
}

async function selectProvider(leg: ProviderLeg): Promise<void> {
  if (leg.provider === "Ollama") {
    await chooseOllama(leg.model);
    return;
  }
  await useHostedModel(page, BASE, {
    provider: leg.provider,
    keyLabel: leg.keyLabel!,
    key: leg.key!,
    model: leg.model,
  });
}

async function newestShellApproval(): Promise<Locator> {
  await page.goto(`${BASE}/#/approvals`);
  await page.getByLabel("Sort approvals").selectOption({ label: "Newest first" });
  const row = page.getByRole("row", { name: /Shell/i }).filter({ hasText: "pending" }).first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByRole("button", { name: "Review" }).click();
  const detail = page.getByLabel(/^Review /);
  await expect(detail).toContainText("git --version");
  return detail;
}

async function runGovernedBuildCommand(leg: ProviderLeg): Promise<void> {
  await page.goto(`${BASE}/#/build`);
  const newChat = page.getByRole("button", { name: "New chat", exact: true });
  if (await newChat.isEnabled().catch(() => false)) await newChat.click();
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  const prompt = page.getByLabel("Describe the change");
  await prompt.fill(
    `Use the shell tool exactly once with command "git --version". ` +
      `Do not use another tool and do not answer without proposing that exact command. ` +
      `This is the ${leg.provider} governed-shell verification.`,
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Waiting for approval", { exact: true })).toBeVisible({ timeout: 240_000 });

  await newestShellApproval();
  await page.getByRole("button", { name: "Approve and execute once" }).click();
  await expect(page.locator(".notice-ok").first()).toContainText("Executed once", { timeout: 60_000 });

  await page.goto(`${BASE}/#/build`);
  const terminal = page.getByRole("button", { name: /Governed terminal/i });
  if ((await terminal.getAttribute("aria-expanded")) !== "true") await terminal.click();
  await expect(page.locator(".output-head")).toContainText("git --version", { timeout: 30_000 });
  await expect(page.locator(".output-shell pre")).toContainText(/git version/i);
  await expect(page.getByText("Selected environment is authoritative")).toBeVisible();
  const receipt = page.locator(".receipt-card");
  await expect(receipt).toBeVisible();
  await receipt.locator("summary").click();
  await expect(receipt).toContainText("approval");
  await expect(receipt).toContainText(/local[_ ]strict/i);
  // Normal 1440 × 1000 viewport capture — deliberately not a full-page/high-res image.
  await page.screenshot({ path: join(SHOTS, `governed-shell-${leg.provider.toLowerCase()}-live.png`) });
}

test.beforeAll(async ({ browser }) => {
  test.setTimeout(300_000);
  for (const leg of LEGS) {
    expect(leg.model, `${leg.provider} model is required`).not.toBe("");
    if (leg.provider !== "Ollama") expect(leg.key, `${leg.provider} key is required`).not.toBe("");
  }
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: "light" });
  page = await context.newPage();
  await signIn();
  await setCapability("Approval execution relay", "execute each approved command exactly once");
  await setCapability("Shell commands", "run bounded governed Build commands");
});

test.afterAll(async () => await context?.close());

for (const leg of LEGS) {
  test(`${leg.provider} completes a governed Build command with receipt`, async () => {
    test.setTimeout(600_000);
    await selectProvider(leg);
    await runGovernedBuildCommand(leg);
    if (leg.provider !== "Ollama") {
      await expect(await hostedProviderCard(page, BASE, leg.provider)).toContainText("Connected");
    }
  });
}
