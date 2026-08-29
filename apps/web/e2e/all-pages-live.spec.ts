import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { dismissFirstRunModelSetup } from "./hosted-provider";

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
  // The sweep is only a sweep if it covers every tab the nav offers. Skills and
  // Hooks were missing, so two of the six extension surfaces were never
  // photographed and a regression on either would have gone unseen.
  ["14-extensions-skills", "extensions?tab=skills"],
  ["15-extensions-hooks", "extensions?tab=hooks"],
  ["16-extensions-plugins", "extensions?tab=plugins"],
  ["17-extensions-channels", "extensions?tab=channels"],
  ["18-observability-overview", "observe?tab=overview"],
  ["19-observability-sessions", "observe?tab=sessions"],
  ["20-observability-activity", "observe?tab=activity"],
  ["21-observability-checkpoints", "observe?tab=checkpoints"],
  ["22-observability-diagnostics", "observe?tab=diagnostics"],
  ["23-observability-work", "observe?tab=work"],
  ["24-observability-notifications", "observe?tab=notifications"],
  ["25-settings", "settings"],
] as const;

test("capture every application page from a live fresh instance", async ({ page }) => {
  test.setTimeout(120_000);
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
  // FIXED-172 put the five-stage setup wizard over the workbench on a brand-new
  // instance, and it is modal: without dismissing it this sweep photographs the
  // sheet twenty-four times instead of the pages underneath. The shared helper
  // is what eighteen other live specs already use for exactly this — but it
  // *samples* rather than waits, and the sheet only mounts once the bootstrap
  // reads resolve, which is after account creation returns. So wait for either
  // the sheet or the workbench first, exactly as `openHostedProviders` does.
  const workbenchHeading = page.getByRole("heading", { name: "Welcome to your Work Dashboard" });
  await expect(
    page.getByRole("button", { name: "Decide later" }).or(workbenchHeading).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
  await expect(workbenchHeading).toBeVisible({ timeout: 30_000 });

  for (const [name, route] of pages) {
    await page.goto(`http://127.0.0.1:8765/#/${route}`);
    await expect(page.locator("main#main")).toBeVisible();
    await page.waitForLoadState("networkidle");
    // Several views render their shell immediately and then hydrate multiple
    // API-backed panels. Do not capture until every visible loading label has
    // gone; a slow or stuck panel should fail this evidence run.
    await page.waitForFunction(
      () =>
        ![...document.querySelectorAll("main#main *")].some((element) => {
          const node = element as HTMLElement;
          const visible = node.offsetWidth > 0 || node.offsetHeight > 0;
          return visible && /^(loading|reading|checking|verifying)\b/i.test((node.textContent ?? "").trim());
        }),
      undefined,
      { timeout: 20_000 },
    );
    await page.waitForTimeout(name === "01-workbench" ? 10_000 : 1_000);
    await capture(page, `../../docs/plans/screenshots/pages/${name}.png`);
  }
  expect(consoleErrors).toEqual([]);
});
