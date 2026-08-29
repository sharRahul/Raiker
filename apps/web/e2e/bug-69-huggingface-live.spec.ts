import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";
import { mkdirSync } from "node:fs";

const BASE = "http://127.0.0.1:8765";
const PASSWORD = "Bug-69-live-review-password-1!";
const SHOT = join(
  import.meta.dirname,
  "..",
  "..",
  "..",
  "output",
  "playwright",
  "bug69-huggingface-catalogue-live.png",
);
const DOWNLOAD_ROOT = join(
  import.meta.dirname,
  "..",
  "..",
  "..",
  "output",
  "playwright",
  "bug69-huggingface-download",
);

async function unlock(page: Page) {
  if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }
}

test("BUG-69 live Hub search presents immutable GGUF-first choices", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/models?tab=huggingface`);
  if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await unlock(page);
    await page.goto(`${BASE}/#/models?tab=huggingface`);
  }
  await page.getByRole("tab", { name: "Hugging Face" }).click();
  await page.getByLabel("Search Hugging Face models").fill("Qwen2.5 0.5B GGUF");
  await page.getByRole("button", { name: "Search models" }).click();
  await page
    .getByText("Qwen/Qwen2.5-0.5B-Instruct-GGUF", { exact: true })
    .click();
  await expect(page.getByText("Ready to deploy").first()).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText("Q4_K_M").first()).toBeVisible();
  await expect(
    page.getByText("apache-2.0", { exact: true }).first(),
  ).toBeVisible();
  await capture(page, SHOT);
});

test("BUG-69 downloads a selected immutable GGUF into an approved library", async ({
  page,
}) => {
  test.setTimeout(240_000);
  mkdirSync(DOWNLOAD_ROOT, { recursive: true });
  await page.goto(`${BASE}/#/models?tab=local`);
  await unlock(page);
  await page.goto(`${BASE}/#/models?tab=local`);
  await page.getByRole("tab", { name: "Local" }).click();
  await page.getByLabel("Absolute model folder").fill(DOWNLOAD_ROOT);
  await page.getByRole("button", { name: "Add and scan" }).click();

  await page.getByRole("tab", { name: "Hugging Face" }).click();
  await page
    .getByLabel("Search Hugging Face models")
    .fill("tensorblock TinyStories-656K GGUF");
  await page.getByRole("button", { name: "Search models" }).click();
  await page
    .getByText("tensorblock/TinyStories-656K-GGUF", { exact: true })
    .click();
  const variants = page.getByLabel("Model download options");
  await variants.getByRole("button", { name: /Q2_K/ }).first().click({
    timeout: 60_000,
  });
  await expect(page.getByText("Approved destination folder")).toBeVisible();
  await page.getByRole("button", { name: "Confirm download" }).click();
  await expect(
    page.getByText("GGUF downloaded and indexed in your local library."),
  ).toBeVisible({ timeout: 180_000 });
  await page.getByRole("tab", { name: "Local" }).click();
  const modelCard = page.locator("article.model-card").filter({
    hasText: /TinyStories 656K/i,
  });
  await expect(modelCard).toBeVisible();
  await modelCard.getByRole("button", { name: "Deploy" }).click();
  await expect(
    page.getByText("Deployment queued. Track it in Activity."),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Activity" }).click();
  const deployment = page
    .locator("article")
    .filter({ hasText: "deploy" })
    .first();
  await expect(deployment).toContainText("complete", { timeout: 60_000 });
  await capture(page, join(
      import.meta.dirname,
      "..",
      "..",
      "..",
      "output",
      "playwright",
      "bug69-huggingface-deploy-live.png",
    ));
});
