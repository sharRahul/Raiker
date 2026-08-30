/**
 * B13 — the repository is on screen in Build, and a file in it can be read.
 *
 * The claim under test is the one GAP-BUILD makes: an owner can see the
 * repository the agent is working in, open a file, and read the result of a
 * change without leaving the app. The three properties that make that true —
 * lazy expansion, an honest refusal for a file that cannot be shown, and the
 * path carrying into the composer — are each asserted rather than photographed.
 *
 * Live, because the tree and the file come from the two routes added for it;
 * a fixture would prove the component renders, not that the boundary holds.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const OUT = "../../docs/plans/screenshots/working";
const CREDENTIALS = { user: "owner", password: "Survey-password-1!" };

test("Build shows the connected repository and reads a file from it", async ({ page }) => {
  test.setTimeout(180_000);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await signInAsOwner(page, BASE, CREDENTIALS);
  await page.goto(`${BASE}/#/build`);

  // Connect the workspace-contained demo folder, unless a previous run did.
  // Written to be re-runnable against a workspace that already holds it: a live
  // spec that only passes on an empty instance is BUG-229 all over again.
  const repoButton = page.locator("button.repo-button");
  await expect(repoButton).toBeVisible({ timeout: 30_000 });
  await repoButton.click();
  const connector = page.getByRole("region", { name: "Repositories" });
  await expect(connector).toBeVisible();
  // Wait for the list to arrive before deciding it is empty: asking too early
  // reconnects a repository that is already there and answers 422.
  await connector
    .locator(".repo-label")
    .first()
    .waitFor({ timeout: 5_000 })
    .catch(() => {});
  if ((await connector.locator(".repo-label").count()) === 0) {
    await page.getByLabel("Folder inside this workspace").fill("demo-repo");
    await page.getByRole("button", { name: "Connect repository" }).click();
  }
  // Connecting the first repository adopts it; a workspace that already had one
  // connected but inactive still needs the choice made.
  const use = connector.getByRole("button", { name: "Use" });
  await expect(use.or(connector.getByText("Active")).first()).toBeVisible({
    timeout: 30_000,
  });
  if ((await use.count()) > 0) await use.first().click();
  await expect(repoButton).toContainText("demo-repo", { timeout: 30_000 });
  await page.getByRole("button", { name: "Close repositories" }).click();

  // The control is where a coding session looks for it: on the Build header.
  const files = page.getByRole("button", { name: "Show repository files" });
  await expect(files).toBeEnabled();
  await files.click();

  // Lazy: the root listed, and `src` not walked until it is asked for.
  await expect(page.getByRole("tree", { name: "Repository files" })).toBeVisible();
  await expect(page.getByText("main.py")).toHaveCount(0);
  await page.getByRole("button", { name: "Expand src" }).click();
  await expect(page.getByRole("button", { name: "Read main.py" })).toBeVisible();

  // Reading a file shows it, highlighted, with the language named.
  await page.getByRole("button", { name: "Read main.py" }).click();
  const viewer = page.locator("pre.code");
  await expect(viewer).toContainText("def greet");
  await expect(page.getByText("Python", { exact: true })).toBeVisible();
  expect(await page.locator("pre.code .tok-keyword").count()).toBeGreaterThan(0);
  await capture(page, `${OUT}/b13-build-file-explorer.png`);

  // The path carries into the composer as the same `@` mention the completion
  // menu writes, so reading a file leads to asking about it.
  await page.getByRole("button", { name: /^Mention src\/main\.py/ }).click();
  await expect(page.locator("#build-prompt")).toHaveValue(/@src\/main\.py/);

  // A file that cannot be shown says which reason applies, in words.
  await page.getByRole("button", { name: "Read logo.png" }).click();
  await expect(page.getByText(/not text/)).toBeVisible();

  // Narrow windows get the same panel as a dismissible sheet, not a lost one.
  // Resized rather than reloaded: the session token lives in memory, so a
  // reload here would photograph the sign-in screen and prove nothing.
  await page.getByRole("button", { name: "Hide repository files" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Show repository files" }).click();
  await expect(page.getByRole("dialog", { name: "Repository files" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Read README.md" })).toBeVisible();
  await capture(page, `${OUT}/b13-build-file-explorer-narrow.png`);

  expect(consoleErrors).toEqual([]);
});
