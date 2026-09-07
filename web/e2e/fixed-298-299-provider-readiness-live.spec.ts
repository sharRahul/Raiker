import { expect, test, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");

/**
 * BUG-229 — sign in through the one shared helper.
 *
 * Every spec used to carry its own copy, and each copy encoded an assumption
 * about the *state* of the instance — usually the empty-workspace greeting —
 * that had nothing to do with what the spec asserts. A suite then passed on a
 * fresh instance and failed at its first step on a used one.
 */
async function signIn(page: Page) {
  await signInAsOwner(page, BASE, { user: "Rahul", password: "Ithink@10" });
}

async function testCard(card: Locator, provider: string, requiresConnection = true) {
  if (requiresConnection) {
    await expect(card.getByText("Connection saved", { exact: true })).toBeVisible();
  }
  await card.getByRole("button", { name: "Test", exact: true }).click();
  const result = card.locator("[data-test-result]");
  await expect(result).toBeVisible({ timeout: 180_000 });
  const answer = (await result.textContent())?.trim() ?? "";
  expect(answer, `${provider} returned an empty test result`).not.toBe("");
  test.info().annotations.push({ type: "provider-result", description: `${provider}: ${answer}` });
}

test("all configured requested providers answer through the live Models UI", async ({ page }) => {
  test.setTimeout(600_000);
  await signIn(page);

  for (const provider of ["Anthropic", "OpenAI"]) {
    await page.goto(`${BASE}/#/models?tab=hosted`);
    const card = page.locator("article.provider-card").filter({ has: page.getByRole("heading", { name: provider, exact: true }) });
    await testCard(card, provider);
  }

  await page.goto(`${BASE}/#/models?tab=hosted`);
  await testCard(
    page.locator("article.provider-card").filter({ has: page.getByRole("heading", { name: "OpenRouter", exact: true }) }),
    "OpenRouter",
  );

  await page.goto(`${BASE}/#/models?tab=local`);
  await testCard(
    page.locator(".local-row").filter({ has: page.getByRole("heading", { name: "Ollama", exact: true }) }).first(),
    "Ollama",
    false,
  );
});

test("an owner-authored skill command appears in both governed composers", async ({ page }) => {
  await signIn(page);
  const trigger = "raiker299";
  const skillName = "algorithm-creator";

  try {
    await page.goto(`${BASE}/#/extensions?tab=skills`);
    const skill = page.locator("li.card").filter({ hasText: skillName }).first();
    await expect(skill).toBeVisible({ timeout: 30_000 });
    await skill.getByRole("button", { name: /^(Add|Edit) command$/ }).click();
    await skill.getByLabel("Slash command").fill(trigger);
    await skill.getByRole("button", { name: "Save", exact: true }).click();
    await expect(skill.getByText(`/${trigger}`, { exact: true })).toBeVisible();

    await page.goto(`${BASE}/#/new-chat`);
    await page.getByLabel("Prompt").fill(`/${trigger}`);
    const chatMenu = page.getByRole("listbox", { name: "Commands" });
    await expect(chatMenu.getByText(`/${trigger}`, { exact: true })).toBeVisible();
    await page.screenshot({ path: join(SHOTS, "fixed-299-chat-skill-command.png") });

    await page.goto(`${BASE}/#/build`);
    await page.getByLabel("Describe the change").fill(`/${trigger}`);
    await expect(page.getByRole("listbox", { name: "Commands" }).getByText(`/${trigger}`, { exact: true })).toBeVisible();
  } finally {
    await page.goto(`${BASE}/#/extensions?tab=skills`);
    const skill = page.locator("li.card").filter({ hasText: skillName }).first();
    if (await skill.getByRole("button", { name: "Edit command" }).isVisible().catch(() => false)) {
      await skill.getByRole("button", { name: "Edit command" }).click();
      await skill.getByRole("button", { name: "Remove", exact: true }).click();
      await expect(skill.getByRole("button", { name: "Add command" })).toBeVisible();
    }
  }
});
