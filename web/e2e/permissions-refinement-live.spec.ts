import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE } from "./live";

test("real account permissions distinguish access from action decisions", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, LIVE_BASE);
  await page.goto(`${LIVE_BASE}/#/capabilities`);
  await expect(page.getByRole("heading", { name: "Default mode" })).toBeVisible();
  const summary = page.getByText("Permission summary", { exact: true });
  await expect(summary.locator("..")).not.toHaveAttribute("open");
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(summary.locator("..")).toHaveAttribute("open", "");
  await page.keyboard.press("Enter");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    if (width < 600) {
      const close = page.getByRole("banner").getByRole("button", { name: "Close navigation", exact: true });
      if (await close.isVisible()) await close.click();
      await expect.poll(async () => {
        const box = await page.locator("#all-navigation").boundingBox();
        return box === null ? 0 : box.x + box.width;
      }).toBeLessThanOrEqual(1);
    }
    for (const theme of ["light", "dark"]) {
      await page.evaluate((value) => { document.documentElement.dataset.theme = value; }, theme);
      await capture(page, join(import.meta.dirname, "..", "..", "output", "playwright", `permissions-live-${width}-${theme}.png`));
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("navigation", { name: "Permission categories" }).getByRole("button", { name: /^Commands/ }).click();
  await page.getByRole("option", { name: /Shell commands/ }).click();
  const detail = page.getByRole("article", { name: "Shell commands" });
  const headings = await detail.getByRole("heading", { level: 3 }).allTextContents();
  expect(headings).toEqual(["Can Raiker use this?", "When Raiker wants to use it"]);
  await capture(page, join(import.meta.dirname, "..", "..", "output", "playwright", "permissions-live-detail.png"));
  await page.goto(`${LIVE_BASE}/#/work`);
  await expect(page.getByRole("tab", { name: "Chats", exact: true })).toBeVisible();
});
