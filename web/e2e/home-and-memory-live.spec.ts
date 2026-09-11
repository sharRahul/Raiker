/**
 * Home's Work parity and the Memory hub, on the running product.
 *
 * Both claims are about what an owner sees first: that the three Work modes are
 * offered as peers on the page the session opens with, and that Memory answers
 * *is anything waiting on me* before it shows a category of records.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";

test.describe.configure({ mode: "serial" });

test("Home offers Chat, Build and Design as peers", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/home`);

  const start = page.getByRole("navigation", { name: "Start work" });
  await expect(start).toBeVisible({ timeout: 30_000 });
  const links = start.getByRole("link");
  await expect(links).toHaveCount(3);
  await expect(links.nth(0)).toHaveAttribute("href", "#/new-chat");
  await expect(links.nth(1)).toHaveAttribute("href", "#/build");
  await expect(links.nth(2)).toHaveAttribute("href", "#/design");

  // Tasks and Projects are workflow entries, not Work modes: their own row.
  const organise = page.getByRole("navigation", { name: "Organise work" });
  await expect(organise.getByRole("link")).toHaveCount(2);

  // The link reaches the surface it names.
  await links.nth(2).click();
  await expect(page.locator('[data-work-surface="design"]')).toBeVisible({ timeout: 30_000 });

  await page.goto(`${BASE}/#/home`);
  await capture(page, `${SHOTS}/home-start-work-parity.png`, start);
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
