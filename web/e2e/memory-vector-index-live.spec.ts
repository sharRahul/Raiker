import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { signInAsOwner } from "./hosted-provider";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "output", "playwright");

test("Memory exposes the revision-checked vector search strategy", async ({ page }) => {
  await signInAsOwner(page, BASE);

  await page.goto(`${BASE}/#/memory`);
  await expect(page.getByRole("heading", { name: "Recall backend" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByLabel("Memory permission posture")).toContainText(/memory store is off/i);
  await expect(page.getByLabel("Memory permission posture")).not.toContainText(/could not read/i);
  await expect(page.getByText(/Recall keeps a revision-checked index/i)).toBeVisible();
  await expect(page.getByText(/exact score re-ranking/i)).toBeVisible();

  // Normal 1440 × 1000 viewport capture — deliberately not a full-page/high-res image.
  await page.screenshot({ path: join(SHOTS, "memory-vector-index-live.png") });
});
