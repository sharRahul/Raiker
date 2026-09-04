import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { dismissFirstRunModelSetup, requireFirstRunWorkspace } from "./hosted-provider";

async function unlock(page: import("@playwright/test").Page) {
  if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-C1!");
    await page.getByRole("button", { name: /Unlock Raiker/i }).click();
  }
}

test("live empty-account Workbench review", async ({ page }) => {
  // Registering an owner, walking the five-stage first-run wizard, and reading a
  // board that polls its own data does not fit the 30-second default.
  test.setTimeout(180_000);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  // BUG-250 — this is the *empty-account* review: it asserts that a workbench
  // with nothing on it offers nothing to resume. It also creates its own owner,
  // so it cannot run against a workspace another spec already signed into.
  await requireFirstRunWorkspace(
    page,
    "http://127.0.0.1:8765",
    "This is the empty-account Workbench review, and it registers its own owner.",
  );
  await page.goto("http://127.0.0.1:8765/#/workbench");
  if (await page.getByLabel("Confirm password").isVisible()) {
    await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
    await page.getByLabel("Username").fill("owner");
    await page.getByLabel("Password", { exact: true }).fill("Live-review-password-C1!");
    await page.getByLabel("Confirm password").fill("Live-review-password-C1!");
    const createAccount = page.getByRole("button", { name: "Create a User Account", exact: true });
    await expect(createAccount).toBeEnabled();
    await createAccount.click();
    // A brand-new instance opens the five-stage first-run wizard over the
    // Workbench, and it is modal: this review is about the screen underneath.
    await dismissFirstRunModelSetup(page);
    await expect(page.getByRole("heading", { name: "Welcome to your Work Dashboard" })).toBeVisible({ timeout: 30_000 });
  } else if (await page.getByRole("button", { name: /Unlock Raiker/i }).isVisible()) {
    await unlock(page);
  }
  await dismissFirstRunModelSetup(page);
  await expect(page.getByRole("heading", { name: "Welcome to your Work Dashboard" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Pick up where you left off", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Resume a conversation", { exact: true })).toHaveCount(0);
  // The composer is gone. The Workbench answers "what is Raiker doing right now"
  // in three groups that are three different facts, and starting work is a link
  // to the surface that owns a composer for it.
  await expect(page.getByLabel(/What would you like Raiker to do/)).toHaveCount(0);
  await expect(page.getByRole("tablist", { name: "Work mode" })).toHaveCount(0);
  for (const group of ["Running now", "Standing agents", "Scheduled runs"]) {
    await expect(page.getByRole("region", { name: group })).toBeVisible();
  }
  await expect(page.getByText("Nothing is running.")).toBeVisible();
  const start = page.getByRole("navigation", { name: "Start work" });
  for (const action of ["Start a conversation", "Start a build", "Plan a task or agent"]) {
    await expect(start.getByRole("link", { name: new RegExp(action) })).toBeVisible();
  }
  await expect(page.getByRole("link", { name: /Review issues/ })).toBeVisible();
  await capture(page, "../../docs/plans/screenshots/working/workbench-board-live.png");
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
  await capture(page, "../../docs/plans/screenshots/working/settings-redesign-live.png");
  await settingsNav.getByRole("button", { name: "Runtime configuration" }).click();
  await expect(page.getByRole("heading", { name: "Runtime configuration" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Danger zone" })).toBeVisible();
  await expect(page.getByText("Loading…", { exact: true })).toBeHidden();
  await capture(page, "../../docs/plans/screenshots/working/settings-runtime-live.png");
});
