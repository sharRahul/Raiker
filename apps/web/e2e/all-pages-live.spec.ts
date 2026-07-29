import { expect, test } from "@playwright/test";

const pages = [
  ["01-workbench", "workbench"],
  ["02-chat", "new-chat"],
  ["03-build", "build"],
  ["04-search-chat", "search-chat"],
  ["05-tasks", "tasks"],
  ["06-projects", "projects"],
  ["07-memory", "memory"],
  ["08-brain", "brain"],
  ["09-approvals", "approvals"],
  ["10-permissions", "capabilities"],
  ["11-models", "models"],
  ["12-extensions-connectors", "extensions?tab=connectors"],
  ["13-extensions-mcp", "extensions?tab=mcp"],
  ["14-extensions-plugins", "extensions?tab=plugins"],
  ["15-extensions-channels", "extensions?tab=channels"],
  ["16-observability-overview", "observe?tab=overview"],
  ["17-observability-sessions", "observe?tab=sessions"],
  ["18-observability-activity", "observe?tab=activity"],
  ["19-observability-checkpoints", "observe?tab=checkpoints"],
  ["20-observability-diagnostics", "observe?tab=diagnostics"],
  ["21-observability-work", "observe?tab=work"],
  ["22-observability-notifications", "observe?tab=notifications"],
  ["23-settings", "settings"],
] as const;

test("capture every application page from a live fresh instance", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.goto("http://127.0.0.1:8765/#/workbench");
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password", { exact: true }).fill("All-pages-review-password-1!");
  await page.getByLabel("Confirm password").fill("All-pages-review-password-1!");
  await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Welcome to your Work Dashboard" })).toBeVisible({ timeout: 15_000 });

  for (const [name, route] of pages) {
    await page.goto(`http://127.0.0.1:8765/#/${route}`);
    await expect(page.locator("main#main")).toBeVisible();
    await page.waitForTimeout(250);
    await page.screenshot({
      path: `../../docs/plans/screenshots/pages/${name}.png`,
      fullPage: true,
    });
  }
  expect(consoleErrors).toEqual([]);
});
