import { expect, test } from "@playwright/test";

test("live Observability and Sessions visual review", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.goto("http://127.0.0.1:5174/#/observe");
  const firstRun = page.getByRole("button", { name: "Create a User Account", exact: true });
  const register = page.getByRole("button", { name: /Create account and open Raiker/i });
  if (await page.getByLabel("Confirm password").isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-19!");
    await page.getByLabel("Confirm password").fill("Live-review-password-19!");
    await firstRun.click();
  } else if (await register.isVisible()) {
    await page.getByLabel("Instance name").fill("Raiker live review");
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-19!");
    await page.getByLabel("Confirm password").fill("Live-review-password-19!");
    await register.click();
  } else if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-19!");
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }
  await page.goto("http://127.0.0.1:5174/#/observe");
  await expect(page.getByRole("tab", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Sessions" })).toBeVisible();
  await expect(page.getByText("Reading runtime status…")).toBeHidden({ timeout: 15_000 });
  await page.screenshot({ path: "../../docs/plans/screenshots/working/observability-overview.png", fullPage: true });
  await page.getByRole("tab", { name: "Sessions" }).click();
  await expect(page.getByText(/Every conversation with the runtime/)).toBeVisible();
  if (await page.locator(".layout").count()) {
    await expect(page.locator(".layout")).toHaveCSS("display", "flex");
  } else {
    await expect(page.getByText("No sessions yet")).toBeVisible();
  }
  await page.screenshot({ path: "../../docs/plans/screenshots/working/observability-sessions.png", fullPage: true });
  expect(consoleErrors).toEqual([]);
});
