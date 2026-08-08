import { expect, test } from "@playwright/test";
import { join } from "node:path";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");

test("a fresh workspace visibly defaults to Ollama gemma4:31b-cloud", async ({ page }) => {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 20_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill("Default-ollama-review-password-1!");
  await page.getByLabel("Confirm password").fill("Default-ollama-review-password-1!");
  await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 20_000 });

  await page.goto(`${BASE}/#/models`);
  await expect(page.getByText("Gemma 4:31B Cloud", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Ollama", { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "default-ollama-models-live.png"), fullPage: true });

  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByRole("button", { name: "Model for this turn: Gemma 4:31B Cloud" })).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "default-ollama-chat-live.png"), fullPage: true });

  await page.goto(`${BASE}/#/build`);
  await expect(page.getByRole("button", { name: "Model for this turn: Gemma 4:31B Cloud" })).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "default-ollama-build-live.png"), fullPage: true });
});
