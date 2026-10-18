// SPDX-License-Identifier: Apache-2.0
/**
 * DESK-14 — Raiker, in its desktop window, against a real host and a real model.
 *
 * Run by hand against a running `raiker-app` whose workspace is fresh or owned
 * by RAIKER_LIVE_OWNER / RAIKER_LIVE_PASSWORD:
 *
 *   RAIKER_LIVE_ANTHROPIC_KEY=… RAIKER_LIVE_ANTHROPIC_WORKSPACE=… \
 *     xvfb-run -a npx playwright test --project=live e2e/desktop-live.spec.ts
 *
 * The key is typed into the product the way an owner pastes it — Raiker stores
 * it, not this spec — and the turn is answered by the provider, not a fixture.
 * Every step is done through the window: its first-run wizard, its native menu
 * commands, its theme, and a narrow window.
 */
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { _electron as electron, expect, test, type ElectronApplication, type Page } from "@playwright/test";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765/";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const WORKSPACE = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL_LABEL ?? "Haiku 5.5";
const OWNER = process.env.RAIKER_LIVE_OWNER ?? "Rahul";
const PASSWORD = process.env.RAIKER_LIVE_PASSWORD ?? "correct-horse-battery-9";
const SHOTS = process.env.RAIKER_DESKTOP_SHOTS ?? "test-results";

async function shot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: join(SHOTS, `${name}.png`) });
}

async function menu(app: ElectronApplication, command: string): Promise<void> {
  // Exactly what the native menu item sends; the accelerators are unit-tested.
  await app.evaluate(({ BrowserWindow }, name) => {
    BrowserWindow.getAllWindows()[0].webContents.send("raiker:command", name);
  }, command);
}

async function signIn(page: Page): Promise<void> {
  const username = page.getByLabel("Username");
  await expect(username).toBeEnabled({ timeout: 60_000 });
  await shot(page, "desktop-01-sign-in");
  await username.fill(OWNER);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  await expect(page.getByRole("navigation", { name: "All navigation" })).toBeVisible({ timeout: 60_000 });
}

/** The first-run wizard, answered with the round's real provider. */
async function finishSetup(page: Page): Promise<void> {
  const title = page.locator("#setup-title");
  if (!(await title.isVisible({ timeout: 10_000 }).catch(() => false))) return;
  await expect(title).not.toHaveText(/Preparing/, { timeout: 30_000 });
  if (/Meet Raiker/.test((await title.textContent()) ?? "")) {
    await page.getByRole("button", { name: "Continue" }).click();
  }
  await expect(title).toHaveText(/Choose how Raiker should think/, { timeout: 30_000 });

  const appears = (locator: ReturnType<Page["getByText"]>, timeout = 30_000) =>
    locator.waitFor({ state: "visible", timeout }).then(() => true, () => false);
  const keyField = page.getByLabel("Anthropic API key");
  if (await appears(keyField)) {
    await keyField.fill(KEY);
    await keyField.press("Enter");
  }
  // An identity-linked key acts inside one Anthropic workspace; the product
  // asks for it after the provider says so (BUG-274), and so does this spec.
  const addWorkspace = page.getByRole("button", { name: "Add the workspace ID" });
  if (await appears(addWorkspace)) {
    expect(WORKSPACE, "set RAIKER_LIVE_ANTHROPIC_WORKSPACE").not.toBe("");
    await addWorkspace.click();
    await page.getByLabel("Anthropic workspace ID").fill(WORKSPACE);
    await page.getByRole("button", { name: "Add workspace", exact: true }).click();
  }
  await expect(page.getByText("Anthropic is connected")).toBeVisible({ timeout: 60_000 });

  // One press opens that provider's picker (BUG-344).
  await page.getByRole("button", { name: "Choose a model" }).click();
  const picker = page.getByRole("dialog", { name: "Anthropic models" });
  await expect(picker.getByText(MODEL, { exact: true })).toBeVisible({ timeout: 30_000 });
  await shot(page, "desktop-02-choose-model");
  await picker.getByRole("button", { name: `Use ${MODEL}` }).click();
  const done = picker.getByRole("button", { name: "Done" });
  if (await done.isVisible().catch(() => false)) await done.click();

  await page.getByRole("button", { name: "Continue" }).click();
  await expect(title).toHaveText(/Where your model requests go/, { timeout: 30_000 });
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Start using Raiker" }).click();
  await expect(title).toBeHidden({ timeout: 30_000 });
}

test("Raiker works end to end in its desktop window", async () => {
  test.skip(KEY === "", "set RAIKER_LIVE_ANTHROPIC_KEY");
  test.setTimeout(300_000);
  const app = await electron.launch({
    args: ["--no-sandbox", join(__dirname, ".."), "--raiker-url", BASE],
    env: { ...process.env, RAIKER_DESKTOP_USER_DATA: mkdtempSync(join(tmpdir(), "raiker-desktop-live-")) },
  });
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setContentSize(1440, 900));
  const page = await app.firstWindow();
  await expect(page.locator("html")).toHaveAttribute("data-desktop-shell", process.platform);

  await signIn(page);
  await finishSetup(page);

  // The top bar is the window's title bar: draggable, with its controls opted out.
  const drag = await page.evaluate(() => {
    const bar = document.querySelector(".topbar");
    const button = bar?.querySelector("button");
    return {
      bar: bar ? getComputedStyle(bar).getPropertyValue("-webkit-app-region") : "",
      button: button ? getComputedStyle(button).getPropertyValue("-webkit-app-region") : "",
    };
  });
  expect(drag).toEqual({ bar: "drag", button: "no-drag" });

  await menu(app, "go-home");
  await expect(page).toHaveURL(/#\/home/);
  await page.waitForTimeout(1500);
  await shot(page, "desktop-03-home");

  // A real turn, answered by the provider through the governed runtime.
  await menu(app, "new-chat");
  await expect(page).toHaveURL(/#\/new-chat/);
  const composer = page.getByRole("group", { name: "Message composer" });
  await composer.getByRole("textbox").first().fill("Reply with exactly the words: desktop window ready");
  await composer.getByRole("button", { name: /^Send/ }).click();
  // Anchored, so the owner's own message ("Reply with exactly…") cannot match.
  await expect(page.getByText(/^\s*desktop window ready\.?\s*$/i)).toBeVisible({ timeout: 120_000 });
  await expect(composer.getByRole("button", { name: /^Send/ })).toBeVisible({ timeout: 120_000 });
  await shot(page, "desktop-04-chat-answer");

  await menu(app, "go-approvals");
  await expect(page).toHaveURL(/#\/approvals/);
  await page.waitForTimeout(1000);
  await shot(page, "desktop-05-approvals");

  await menu(app, "open-palette");
  await expect(page.getByRole("dialog").first()).toBeVisible();
  await shot(page, "desktop-06-palette");
  await page.keyboard.press("Escape");

  // The native controls follow the page's theme.
  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
  await page.waitForTimeout(500);
  await shot(page, "desktop-07-dark");
  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "light"));

  // A narrow window gets the drawer, and the controls still have their room.
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setContentSize(820, 760));
  await page.waitForTimeout(800);
  const room = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--desktop-controls-w").trim(),
  );
  if (process.platform !== "darwin") expect(room).not.toBe("0px");
  await shot(page, "desktop-08-narrow");

  await app.close();
});
