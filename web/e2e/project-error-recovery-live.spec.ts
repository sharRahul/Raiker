/** QUI-G06: running host, real project UI writes, explicit fault injection.
 * No deletion, move, folder attachment or export reaches the host. One disposable
 * fixture is archived and restored through the UI.
 */
import { expect as baseExpect, test, type Page } from "@playwright/test";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { capture } from "./capture";
const expect = baseExpect.configure({ timeout: 30_000 });
const failed = { status: 503, json: { detail: { reason_code: "injected_failure" } } };
const SHOTS = "../../output/playwright/2026-11-06-project-recovery";
const NAME = "Project recovery live";
test.describe.configure({ mode: "serial", timeout: 120_000 });

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=projects`);
  await expect(page.getByRole("tab", { name: /^Active/ }).or(page.getByText("No projects yet", { exact: true }))).toBeVisible();
  if (await page.getByRole("button", { name: `Open project ${NAME}`, exact: true }).count() === 0) {
    await page.getByRole("textbox", { name: "New project name", exact: true }).fill(NAME);
    await page.getByRole("button", { name: "Create project", exact: true }).click();
  }
  await expect(page.getByRole("button", { name: `Open project ${NAME}`, exact: true })).toBeVisible();
});
async function open(page: Page) {
  await page.getByRole("button", { name: `Open project ${NAME}`, exact: true }).click();
  await expect(page.getByRole("heading", { name: NAME, exact: true })).toBeVisible();
}
async function menu(page: Page, action: string) {
  await page.getByRole("button", { name: `More actions for ${NAME}`, exact: true }).click();
  await page.getByRole("menuitem", { name: action, exact: true }).click();
}

test("RT-PROJECT-RECOVERY-01: project list fails visibly and recovers against the host", async ({ page }) => {
  await page.route("**/api/projects", route => route.request().method() === "GET" ? route.fulfill(failed) : route.continue());
  await page.getByRole("button", { name: "Refresh projects", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Projects could not be read" })).toContainText("HTTP 503");
  await expect(page.getByText("No projects yet", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: `Open project ${NAME}`, exact: true })).toBeVisible();
  await capture(page, `${SHOTS}/01-list.png`);
  await page.unroute("**/api/projects");
  await page.getByRole("button", { name: "Retry projects", exact: true }).click();
  await expect(page.getByRole("button", { name: `Open project ${NAME}`, exact: true })).toBeVisible();
});

test("RT-PROJECT-RECOVERY-02: create and attach preserve input and explain uncertain writes", async ({ page }) => {
  await page.route("**/api/projects", route => route.request().method() === "POST" ? route.fulfill(failed) : route.continue());
  await page.getByRole("textbox", { name: "New project name", exact: true }).fill("Keep this project name");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Project creation was not confirmed" })).toContainText("check the project list");
  await expect(page.getByRole("textbox", { name: "New project name", exact: true })).toHaveValue("Keep this project name");
  await page.getByRole("button", { name: "Attach existing folder…", exact: true }).click();
  await page.getByRole("textbox", { name: "Attached project name", exact: true }).fill("Keep folder name");
  await page.getByRole("textbox", { name: "Folder path", exact: true }).fill("/tmp/owner-folder-example");
  await page.getByRole("button", { name: "Attach folder", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Attaching the folder was not confirmed" })).toContainText("HTTP 503");
  await expect(page.getByRole("textbox", { name: "Folder path", exact: true })).toHaveValue("/tmp/owner-folder-example");
  await capture(page, `${SHOTS}/02-drafts.png`);
});

test("RT-PROJECT-RECOVERY-03: failed tasks and images are unavailable and retry retains instructions", async ({ page }) => {
  await page.route("**/api/projects/*/files", route => route.fulfill(failed));
  await page.route("**/api/tasks?*", route => route.fulfill(failed));
  await page.route("**/api/images", route => route.fulfill(failed));
  await open(page);
  await expect(page.getByText("Unavailable", { exact: true })).toHaveCount(3);
  await page.getByRole("textbox", { name: "Project instructions", exact: true }).fill("Unsaved instructions remain here");
  await page.getByRole("tab", { name: "Work", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Project tasks could not be read" })).toContainText("Retry project content");
  await page.getByRole("tab", { name: "Project library", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Project images could not be read" })).toContainText("HTTP 503");
  await page.evaluate(() => { document.documentElement.dataset.theme = "dark"; });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await capture(page, `${SHOTS}/03-content-dark.png`);
  await page.unroute("**/api/projects/*/files");
  await page.unroute("**/api/tasks?*");
  await page.unroute("**/api/images");
  await page.getByRole("button", { name: "Retry project content", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry project content", exact: true })).toHaveCount(0);
  await page.getByRole("tab", { name: /Overview/ }).click();
  await expect(page.getByRole("textbox", { name: "Project instructions", exact: true })).toHaveValue("Unsaved instructions remain here");
});

test("RT-PROJECT-RECOVERY-04: instructions, root and export failures give safe recovery", async ({ page }) => {
  await open(page);
  await page.route("**/api/projects/*/context", route => route.fulfill(failed));
  await page.getByRole("textbox", { name: "Project instructions", exact: true }).fill("Copy this before reopening");
  await page.getByRole("button", { name: "Save context", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Saving project instructions was not confirmed" })).toContainText("copy it before reopening");
  await page.route("**/api/projects/*/root/attach", route => route.fulfill(failed));
  page.once("dialog", dialog => dialog.accept("/tmp/example-folder"));
  await page.getByRole("button", { name: "Attach a folder", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Changing the project folder was not confirmed" })).toContainText("check its folder");
  await page.route("**/api/projects/*/export", route => route.fulfill(failed));
  await page.getByRole("button", { name: "Export project", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "The project export did not finish" })).toContainText("download permissions");
  await capture(page, `${SHOTS}/04-context.png`);
});

test("RT-PROJECT-RECOVERY-05: archive and deletion-preview errors keep the project reachable", async ({ page }) => {
  await page.route("**/api/projects/*/archive", route => route.fulfill(failed));
  await menu(page, "Archive");
  await expect(page.getByRole("alert").filter({ hasText: "Project archiving was not confirmed" })).toContainText("check Active and Archived");
  await page.route("**/api/projects/*/deletion-preview", route => route.fulfill(failed));
  await menu(page, "Delete…");
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("alert")).toContainText("deletion is unavailable");
  await expect(dialog.getByRole("button", { name: "Delete project", exact: true })).toHaveCount(0);
  await capture(page, `${SHOTS}/05-deletion-preview.png`, dialog);
  await page.unroute("**/api/projects/*/deletion-preview");
  await dialog.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(dialog.getByText("This permanently removes", { exact: true })).toBeVisible();
});

test("RT-PROJECT-RECOVERY-06: details, chat move and hierarchy move expose recovery", async ({ page }) => {
  const SECOND = "Project recovery destination";
  if (await page.getByRole("button", { name: `Open project ${SECOND}`, exact: true }).count() === 0) {
    await page.getByRole("textbox", { name: "New project name", exact: true }).fill(SECOND);
    await page.getByRole("button", { name: "Create project", exact: true }).click();
    await expect(page.getByRole("button", { name: `Open project ${SECOND}`, exact: true })).toBeVisible();
  }
  await page.route(/\/api\/projects\/[^/?]+$/, route => route.fulfill(failed));
  await page.getByRole("button", { name: `Open project ${NAME}`, exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Could not load project details" })).toContainText("Open the project again");
  await page.unroute(/\/api\/projects\/[^/?]+$/);
  await page.route("**/api/sessions/recovery-fixture/project", route => route.fulfill(failed));
  const card = page.locator("article").filter({ has: page.getByRole("button", { name: `Open project ${NAME}`, exact: true }) });
  const dataTransfer = await page.evaluateHandle(() => {
    const data = new DataTransfer();
    data.setData("text/raiker-session-id", "recovery-fixture");
    return data;
  });
  await card.dispatchEvent("drop", { dataTransfer });
  await expect(page.getByRole("alert").filter({ hasText: "The chat move was not confirmed" })).toContainText("check the chat’s project");
  await page.route("**/api/projects/*/move", route => route.fulfill(failed));
  await menu(page, "Move…");
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("radio", { name: SECOND, exact: true }).check();
  await dialog.getByRole("button", { name: "Move here", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("check the project hierarchy");
  await expect(dialog.getByRole("radio", { name: SECOND, exact: true })).toBeChecked();
  await capture(page, `${SHOTS}/06-move.png`, dialog);
});

test("RT-PROJECT-RECOVERY-07: restore failure checks status then real restore recovers", async ({ page }) => {
  // Archive only this disposable fixture through the UI, then restore it.
  await menu(page, "Archive");
  await page.getByRole("tab", { name: /^Archived/ }).click();
  const card = page.locator("article").filter({ has: page.getByRole("button", { name: `Open project ${NAME}`, exact: true }) });
  await expect(card).toBeVisible();
  await page.route("**/api/projects/*/restore", route => route.fulfill(failed));
  await card.getByRole("button", { name: "Restore", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Project restoration was not confirmed" })).toContainText("check Active and Archived");
  await capture(page, `${SHOTS}/07-restore.png`);
  await page.unroute("**/api/projects/*/restore");
  await card.getByRole("button", { name: "Restore", exact: true }).click();
  await page.getByRole("tab", { name: /^Active/ }).click();
  await expect(page.getByRole("button", { name: `Open project ${NAME}`, exact: true })).toBeVisible();
});

test("RT-PROJECT-RECOVERY-08: project limits read and save errors recover honestly", async ({ page }) => {
  await page.route("**/api/projects/*/limits", route => route.fulfill(failed));
  await open(page);
  await expect(page.getByRole("alert").filter({ hasText: "Project limits could not be read" })).toContainText("saved work boundaries are unconfirmed");
  await page.unroute("**/api/projects/*/limits");
  await page.getByRole("button", { name: "Retry project limits", exact: true }).click();
  await page.getByRole("button", { name: "Set limits", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("textbox", { name: "Repositories it may push to", exact: true }).fill("example/project");
  await page.route("**/api/projects/*/limits", route => route.fulfill(failed));
  await dialog.getByRole("button", { name: "Save limits", exact: true }).click();
  await expect(dialog.getByText(/Saving project limits was not confirmed/)).toContainText("check the saved limits before starting work");
  await expect(dialog.getByRole("textbox", { name: "Repositories it may push to", exact: true })).toHaveValue("example/project");
  await capture(page, `${SHOTS}/08-limits.png`, dialog);
});
