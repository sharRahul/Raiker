import { expect, test } from "@playwright/test";

async function unlock(page: import("@playwright/test").Page) {
  if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-C1!");
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }
}

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
    await unlock(page);
  }
  await expect(page.getByRole("heading", { name: "Welcome to your Work Dashboard" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Pick up where you left off", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Resume a conversation", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel(/What would you like Raiker to do/)).toBeVisible();
  await expect(page.getByRole("tab", { name: "Run work" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("button", { name: "Start work" })).toBeDisabled();
  await expect(page.getByRole("link", { name: /Review issues/ })).toBeVisible();
  await page.screenshot({
    path: "../../docs/plans/screenshots/working/workbench-dashboard-live.png",
    fullPage: true,
  });
  expect(consoleErrors).toEqual([]);
});

test("live Settings review", async ({ page }) => {
  await page.goto("http://127.0.0.1:8765/#/settings");
  await unlock(page);
  await page.goto("http://127.0.0.1:8765/#/settings");
  await expect(page.getByRole("heading", { name: "Settings", exact: true, level: 2 })).toBeVisible();
  const settingsNav = page.getByRole("navigation", { name: "Settings sections" });
  await expect(settingsNav.getByRole("button", { name: "Notifications" })).toBeVisible();
  await page.getByLabel(/Language Controls/).selectOption("en-US");
  await expect(page.getByText("You have unsaved changes")).toBeVisible();
  await expect(page.getByRole("button", { name: "Save changes" })).toBeVisible();
  await page.screenshot({
    path: "../../docs/plans/screenshots/working/settings-redesign-live.png",
    fullPage: true,
  });
  await settingsNav.getByRole("button", { name: "Runtime configuration" }).click();
  await expect(page.getByRole("heading", { name: "Runtime configuration" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Danger zone" })).toBeVisible();
  await expect(page.getByText("Loading…", { exact: true })).toBeHidden();
  await page.screenshot({
    path: "../../docs/plans/screenshots/working/settings-runtime-live.png",
    fullPage: true,
  });
});
