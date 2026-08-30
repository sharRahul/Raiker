import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");

test("a fresh workspace visibly defaults to Ollama gemma4:31b-cloud", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await expect(page.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 20_000 });

  await page.goto(`${BASE}/#/models`);
  await expect(page.getByText("Gemma 4:31B Cloud", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Ollama", { exact: true }).first()).toBeVisible();
  await capture(page, join(SHOTS, "default-ollama-models-live.png"));

  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByRole("button", { name: "Model for this turn: Gemma 4:31B Cloud" })).toBeVisible();
  await capture(page, join(SHOTS, "default-ollama-chat-live.png"));

  await page.goto(`${BASE}/#/build`);
  await expect(page.getByRole("button", { name: "Model for this turn: Gemma 4:31B Cloud" })).toBeVisible();
  await capture(page, join(SHOTS, "default-ollama-build-live.png"));
});
