import { expect, test } from "@playwright/test";

const routes = [
  "home", "new-chat", "build", "search-chat", "tasks", "projects", "memory", "brain",
  "approvals", "capabilities", "models", "extensions?tab=connectors", "extensions?tab=mcp",
  "extensions?tab=plugins", "extensions?tab=channels", "observe?tab=overview",
  "observe?tab=sessions", "observe?tab=activity", "observe?tab=checkpoints",
  "observe?tab=diagnostics", "observe?tab=work", "observe?tab=notifications", "settings",
] as const;

test("every application page renders in explicit light and dark themes", async ({ page }) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("http://127.0.0.1:8765/#/home");
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
  if (await page.getByLabel("Confirm password").isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-C1!");
    await page.getByLabel("Confirm password").fill("Live-review-password-C1!");
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-C1!");
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }
  await expect(page.locator("main#main")).toBeVisible({ timeout: 15_000 });

  const observed = new Map<string, { light: string; dark: string }>();
  for (const theme of ["light", "dark"] as const) {
    await page.evaluate((choice) => {
      localStorage.setItem("raiker.theme", choice);
      document.documentElement.dataset.theme = choice;
    }, theme);
    for (const route of routes) {
      await page.goto(`http://127.0.0.1:8765/#/${route}`);
      await expect(page.locator("main#main")).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      const palette = await page.evaluate(() => {
        const style = getComputedStyle(document.documentElement);
        return `${style.colorScheme}|${style.getPropertyValue("--bg").trim()}|${style.getPropertyValue("--surface").trim()}|${style.getPropertyValue("--text-1").trim()}`;
      });
      expect(palette.startsWith(`${theme}|`)).toBe(true);
      const previous = observed.get(route) ?? { light: "", dark: "" };
      previous[theme] = palette;
      observed.set(route, previous);
    }
  }

  for (const route of routes) expect(observed.get(route)?.light).not.toBe(observed.get(route)?.dark);
  expect(errors).toEqual([]);
});
