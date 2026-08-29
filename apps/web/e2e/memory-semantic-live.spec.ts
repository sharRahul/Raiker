import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { join } from "node:path";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");

test("managed content exposes governed semantic indexing and curated local acquisition", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText(/Verifying runtime/)).toBeHidden({ timeout: 60_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill("Review-provider-matrix-1!");
  await page.getByRole("button", { name: "Unlock Raiker" }).click();

  await page.goto(`${BASE}/#/memory`);
  const input = page.locator('section[aria-label="Memory document library"] input[type="file"]').first();
  await input.setInputFiles({
    name: "semantic-review.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("The release codename is moonstone and the launch window is Thursday."),
  });
  await expect(page.getByText("semantic-review.txt", { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByLabel("Embedding model", { exact: true })).toBeVisible({ timeout: 60_000 });
  await page.getByLabel("Embedding model", { exact: true }).selectOption("openai:text-embedding-3-small");
  await expect(page.getByRole("button", { name: "Embed 1" })).toBeEnabled();
  await capture(page, join(SHOTS, "review-05-managed-semantic-index.png"));

  await page.goto(`${BASE}/#/models?tab=huggingface`);
  await expect(page.getByRole("heading", { name: "Nomic Embed v1.5" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Apache-2.0/)).toBeVisible();
  await expect(page.getByText(/81 MiB/)).toBeVisible();
  await capture(page, join(SHOTS, "review-06-curated-local-embedding.png"));
});
