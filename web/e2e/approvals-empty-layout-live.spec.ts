/** Empty approval queues use the full page width, including after a saved split. */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

for (const size of [
  { width: 1280, height: 900, savedSplit: false },
  { width: 1440, height: 1000, savedSplit: true },
  { width: 390, height: 844, savedSplit: true },
]) {
  test(`empty approval states are centered at ${size.width}px (saved split ${size.savedSplit})`, async ({ page }) => {
    page.setDefaultTimeout(30_000);
    await page.setViewportSize(size);
    await page.addInitScript((saved) => {
      if (saved) localStorage.setItem("raiker.split.approvals", "320");
      else localStorage.removeItem("raiker.split.approvals");
    }, size.savedSplit);
    await signInAsOwner(page, BASE);
    await page.goto(`${BASE}/#/approvals`);
    for (const tab of ["Pending", "History"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      const title = page.getByText(tab === "Pending" ? "Nothing waiting on you" : "No decisions yet", { exact: true });
      await expect(title).toBeVisible();
      const layout = await page.locator(".list-detail").boundingBox();
      const text = await title.boundingBox();
      expect(layout).not.toBeNull();
      expect(text).not.toBeNull();
      await capture(page, `../../output/playwright/approvals-empty-centered/${size.width}-${tab.toLowerCase()}.png`);
      expect(Math.abs(text!.x + text!.width / 2 - layout!.x - layout!.width / 2)).toBeLessThanOrEqual(1);
      expect(await page.locator("main").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
      await expect(page.getByRole("separator", { name: "Resize the list" })).toHaveCount(0);
    }
  });
}
