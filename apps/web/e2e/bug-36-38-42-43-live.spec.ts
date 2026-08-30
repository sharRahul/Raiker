import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { hostedProviderCard, OWNER_CREDENTIALS } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = OWNER_CREDENTIALS.password;
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const OPENROUTER_KEY = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";

test.describe.configure({ mode: "serial" });

test("BUG-36, BUG-38, BUG-42, BUG-43 and cross-surface attachments", async ({ page }) => {
  test.setTimeout(480_000);
  expect(ANTHROPIC_KEY).not.toBe("");
  expect(OPENROUTER_KEY).not.toBe("");

  await page.goto(`${BASE}/#/models`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 20_000 });
  if (await page.getByLabel("Confirm password").isVisible()) {
    await page.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByLabel("Confirm password").fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByLabel("Username").fill(OWNER_CREDENTIALS.user);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }
  await expect(page.getByRole("heading", { name: "Models", level: 1 })).toBeVisible({ timeout: 20_000 });

  for (const [provider, label, key] of [
    ["Anthropic", "Anthropic API key", ANTHROPIC_KEY],
    ["OpenRouter", "OpenRouter API key", OPENROUTER_KEY],
  ] as const) {
    const card = await hostedProviderCard(page, BASE, provider);
    await card.getByRole("button", { name: /^(Connect|Reconnect)$/ }).click();
    await page.getByLabel(label).fill(key);
    await page.locator(".signin-connect").click();
    await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 20_000 });
  }

  const ollama = page.locator(".local-row").filter({ hasText: "Ollama" });
  if (!(await ollama.getByText("selected", { exact: true }).isVisible())) {
    await ollama.getByRole("button", { name: /Choose model/ }).click();
    await expect(ollama.getByLabel("Available models")).toBeVisible({ timeout: 30_000 });
    await ollama.getByLabel("Available models").selectOption("gemma4:31b-cloud");
    await ollama.getByRole("button", { name: "Use model" }).click();
  }
  await expect(ollama.getByText(/Gemma 4:31B Cloud/)).toBeVisible({ timeout: 20_000 });

  await page.getByRole("tab", { name: "Pricing" }).click();
  await expect(page.getByText("Review current").first()).toBeVisible();
  await expect(page.getByText("Review due").first()).toBeVisible();
  await capture(page, join(SHOTS, "180-BUG-36-price-review-cadence-live.png"));

  const attachment = {
    name: "passage-proof.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Stored coordinates identify this exact passage inside its source turn."),
  };
  await page.goto(`${BASE}/#/new-chat`);
  await page.getByRole("button", { name: "Add attachment" }).click();
  await page.getByLabel("Upload document").setInputFiles(attachment);
  await expect(page.locator(".attachment-row > .attachment-card").filter({ hasText: "passage-proof.txt" })).toBeVisible({ timeout: 20_000 });
  await page.getByPlaceholder("How can I help you today?").fill("Reply with exactly: COORDINATE LIVE");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("COORDINATE LIVE", { exact: true })).toBeVisible({ timeout: 180_000 });
  const chatAttachment = page.locator(".message-group-user .attachment-card").first();
  await expect(chatAttachment).toBeVisible();
  expect(await chatAttachment.evaluate((node) => node.closest(".message-bubble-user"))).toBeNull();

  const actions = page.getByRole("button", { name: "Conversation actions" });
  await actions.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("menuitem", { name: /Export conversation/ }).press("Enter");
  const exportDialog = page.getByRole("dialog", { name: "Export conversation" });
  await expect(exportDialog).toBeVisible();
  expect((await new AxeBuilder({ page }).include("dialog").analyze()).violations).toEqual([]);
  await capture(page, join(SHOTS, "181-BUG-43-export-keyboard-live.png"));
  await page.keyboard.press("Escape");
  await expect(exportDialog).toBeHidden();
  await expect(actions).toBeFocused();

  await page.goto(`${BASE}/#/tasks`);
  await page.getByRole("button", { name: "Schedule once" }).click();
  await page.getByLabel("Task title").fill("Review attached passage");
  await page.getByLabel("Instructions").fill("Use the attached source without embedding it in these instructions.");
  await page.getByLabel("Attachment path").fill("docs/plans/TO_BE_FIXED.md");
  await page.getByRole("button", { name: "Attach" }).click();
  const tomorrow = new Date(Date.now() + 86_400_000).toISOString().slice(0, 16);
  await page.getByLabel("Start time").fill(tomorrow);
  await page.getByRole("button", { name: "Schedule task" }).click();
  await expect(page.getByLabel("Files attached to this task").getByText("docs/plans/TO_BE_FIXED.md").first()).toBeVisible();
  await capture(page, join(SHOTS, "182-schedule-attachment-outside-instructions-live.png"));

  await page.goto(`${BASE}/#/settings`);
  await page.getByRole("button", { name: "Runtime configuration" }).click();
  await page.getByText("Add SSH or Daytona profile").click();
  await page.getByLabel("Environment type").selectOption("daytona");
  await page.getByLabel("Display name").fill("Budget evidence sandbox");
  await page.getByLabel("Sandbox ID").fill("budget-evidence-sandbox");
  await page.getByLabel("Maximum run cost (USD)").fill("5");
  await page.getByRole("button", { name: "Save environment" }).click();
  await expect(page.getByText(/USD 0\.00 committed.*5\.00 remaining.*not started/i).first()).toBeVisible();
  await capture(page, join(SHOTS, "183-BUG-42-cumulative-budget-live.png"));

  await page.goto(`${BASE}/#/brain`);
  const addSource = page.getByRole("button", { name: "Add workspace source" });
  await addSource.press("Enter");
  const sourceDialog = page.getByRole("dialog", { name: "Review workspace source" });
  await expect(sourceDialog).toBeVisible();
  expect((await new AxeBuilder({ page }).include("dialog").analyze()).violations).toEqual([]);
  await capture(page, join(SHOTS, "184-BUG-43-knowledge-map-keyboard-live.png"));
  await page.keyboard.press("Escape");
  await expect(sourceDialog).toBeHidden();
  await expect(addSource).toBeFocused();
  expect((await new AxeBuilder({ page }).include("main#main").analyze()).violations).toEqual([]);
});
