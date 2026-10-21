/**
 * Home's Work parity and the Memory hub, on the running product.
 *
 * Both claims are about what an owner sees first: that Home opens with a
 * composer (QUI-H01), and that Memory answers
 * *is anything waiting on me* before it shows a category of records.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = "../../docs/plans/screenshots/working";

test.describe.configure({ mode: "serial" });

test("Home opens with a composer that hands its message to Chat", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/home`);

  // QUI-H01 / QUI-Q02 — the composer replaced the start cards.
  const box = page.getByLabel("Ask Raiker");
  await expect(box).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("navigation", { name: "Start work" })).toHaveCount(0);
  await capture(page, `${SHOTS}/home-composer.png`);
});

test("Memory opens on what is waiting, and each tab holds one kind of thing", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/memory`);

  // Overview leads, and says what Raiker can recall in a sentence.
  await expect(page.getByText(/Raiker (can recall|remembers nothing)/i)).toBeVisible({
    timeout: 30_000,
  });
  // The administration that used to share the page is not on this panel …
  await expect(page.getByText(/advanced memory management/i)).toHaveCount(0);
  await expect(page.getByLabel("Search memories")).toHaveCount(0);
  await capture(page, `${SHOTS}/memory-hub-overview.png`);

  // … each tab is reachable, and holds its own kind of thing.
  const strip = page.getByRole("tablist", { name: "Memory sections" });
  await expect(strip).toBeVisible();
  await strip.getByRole("tab", { name: "Memories" }).click();
  await expect(page.getByLabel("Search memories")).toBeVisible({ timeout: 15_000 });

  await strip.getByRole("tab", { name: "Recall & indexing" }).click();
  await expect(page.getByText(/advanced memory management/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByLabel("Search memories")).toHaveCount(0);

  await strip.getByRole("tab", { name: "Sources" }).click();
  await expect(page.getByRole("region", { name: "Memory document library" })).toBeVisible({
    timeout: 15_000,
  });

  // A deep link opens the panel it names, not the hub's front page.
  await page.goto(`${BASE}/#/memory?tab=suggestions`);
  await expect(page.getByRole("tab", { name: "Suggestions", selected: true })).toBeVisible({
    timeout: 15_000,
  });
  await capture(page, `${SHOTS}/memory-hub-suggestions.png`);
});
