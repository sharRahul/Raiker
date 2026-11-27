/** Real owner controls and a local-model proposal; no consequential effect accepted. */
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

test("shared approval actions stay reviewable at desktop and phone widths", async ({ page }) => {
  test.setTimeout(600_000);
  page.setDefaultTimeout(60_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/capabilities?category=advanced`);
  await page.getByRole("button", { name: /Approval mode:/ }).click();
  await page.getByRole("menuitemradio", { name: /Manually approve/ }).click();
  await expect(page.getByRole("button", { name: /Approval mode: Manually approve/ })).toBeVisible();
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /9B/i, "Message composer");
  await page.getByPlaceholder("What would you like Raiker to do?").fill(
    "Use write_file once to prepare approval-demo.txt containing exactly 'Synthetic approval review'. " +
    "Do not run commands or do anything else. Let the runtime ask for its decision.",
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("button", { name: "Approve once", exact: true }).first()).toBeVisible({ timeout: 240_000 });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    if (width < 600) {
      const navigationToggle = page.getByRole("banner").getByRole("button", { name: /^(Open|Close) navigation$/ });
      await expect(navigationToggle).toBeVisible();
      if (await navigationToggle.getAttribute("aria-label") === "Close navigation") await navigationToggle.click();
      await expect(navigationToggle).toHaveAttribute("aria-label", "Open navigation");
      await expect.poll(async () => {
        const box = await page.locator("#all-navigation").boundingBox();
        return box === null ? 0 : box.x + box.width;
      }).toBeLessThanOrEqual(1);
    }
    await expect(page.getByRole("button", { name: "Don't do this", exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Allow for this task…", exact: true }).first()).toBeVisible();
    expect(await page.locator("main").evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
    await capture(page, join(import.meta.dirname, "..", "..", "output", "playwright", `approval-redesign-chat-${width}.png`));
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${BASE}/#/approvals`);
  const item = page.getByRole("option", { name: /Write file.*approval-demo/i }).first();
  await expect(item).toBeVisible();
  await item.click();
  await expect(page.getByRole("button", { name: "Approve once", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Don't do this", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Allow for this task…", exact: true })).toBeVisible();
  await capture(page, join(import.meta.dirname, "..", "..", "output", "playwright", "approval-redesign-inbox.png"));
  await page.getByRole("button", { name: "Don't do this", exact: true }).click();
  await expect(page.getByRole("main")).toContainText(/declined|denied/i);
});
