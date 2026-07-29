import { expect, test } from "@playwright/test";

test("live empty-account Workbench review", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.goto("http://127.0.0.1:8765/#/workbench");
  if (await page.getByLabel("Confirm password").isVisible()) {
    await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-C1!");
    await page.getByLabel("Confirm password").fill("Live-review-password-C1!");
    const createAccount = page.getByRole("button", { name: "Create a User Account", exact: true });
    await expect(createAccount).toBeEnabled();
    await createAccount.click();
    await expect(page.getByRole("heading", { name: "Welcome to your Work Dashboard" })).toBeVisible({ timeout: 15_000 });
  } else if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-C1!");
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }
  await expect(page.getByRole("heading", { name: "Welcome to your Work Dashboard" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Pick up where you left off", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Resume a conversation", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Start a new chat/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /View and flag runtime issues/ })).toBeVisible();
  await page.screenshot({
    path: "../../docs/plans/screenshots/working/workbench-dashboard-live.png",
    fullPage: true,
  });
  expect(consoleErrors).toEqual([]);
});
