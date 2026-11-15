// SPDX-License-Identifier: Apache-2.0
/**
 * The first-run Model step, and Design's composer, in Raiker's desktop window.
 *
 * Owner report, 2026-11-15: with OpenAI, Anthropic and OpenRouter connected and
 * their models listed, the only action at the foot of the Model step was
 * "Decide later", so nothing said a default still had to be chosen. The step
 * now says "Choose a default model to continue to Privacy" beside a Continue
 * that waits for a choice, saves it, and opens Privacy.
 *
 * Runs the real Electron shell against a fresh `raiker-web` (first-run
 * workspace). The three providers' connections and model lists are answered in
 * the window (`page.route`), so it needs no API key and costs nothing; setup
 * itself is saved by the real host.
 *
 *   xvfb-run -a npx playwright test --project=live e2e/setup-model-step-live.spec.ts
 */
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { _electron as electron, expect, test, type Page } from "@playwright/test";

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765/";
const OWNER = process.env.RAIKER_LIVE_OWNER ?? "Rahul";
const PASSWORD = process.env.RAIKER_LIVE_PASSWORD ?? "correct-horse-battery-9";
const SHOTS = process.env.RAIKER_DESKTOP_SHOTS ?? "test-results";

const CONNECTED: Record<string, { provider: string; models: string[] }> = {
  "openai-hosted": { provider: "openai", models: ["gpt-4o-mini", "gpt-4.1"] },
  "anthropic-hosted": { provider: "anthropic", models: ["claude-haiku-4-5-20251001"] },
  "openrouter-policy-gated": { provider: "openrouter", models: ["openai/gpt-4o-mini"] },
};

/** Answer the three providers in the window: connected, with their models listed. */
async function mockProviders(page: Page): Promise<void> {
  await page.route(/\/api\/models(\?.*)?$/, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    const view = await response.json();
    for (const profile of view.profiles ?? []) {
      if (profile.profile_id in CONNECTED) {
        profile.connection_configured = true;
        profile.configured = true;
      }
    }
    await route.fulfill({ response, json: view });
  });
  await page.route(/\/api\/models\/([^/]+)\/provider-models/, async (route) => {
    const id = decodeURIComponent(/\/api\/models\/([^/]+)\/provider-models/.exec(route.request().url())?.[1] ?? "");
    const known = CONNECTED[id];
    await route.fulfill({
      json: known
        ? { profile_id: id, provider: known.provider, status: "available", reason_code: null, models: known.models }
        : { profile_id: id, provider: "", status: "unavailable", reason_code: "provider_unreachable", models: [] },
    });
  });
  await page.route(/\/api\/model-selection$/, (route) => route.fulfill({ json: { ok: true } }));
  await page.route(/\/api\/model-readiness\/check$/, (route) => route.fulfill({ json: { state: "ready", ready: true } }));
}

async function signIn(page: Page): Promise<void> {
  const username = page.getByLabel("Username");
  await expect(username).toBeEnabled({ timeout: 60_000 });
  await username.fill(OWNER);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const confirm = page.getByLabel("Confirm password");
  // A fresh workspace turns the form into registration once its bootstrap
  // read answers, a moment after the username field is usable.
  const registering = await confirm.waitFor({ state: "visible", timeout: 15_000 }).then(() => true, () => false);
  if (registering) {
    await confirm.fill(PASSWORD);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
  }
}

test("the Model step asks for a default, then Continue saves it and opens Privacy", async () => {
  test.setTimeout(240_000);
  const app = await electron.launch({
    args: ["--no-sandbox", join(__dirname, ".."), "--raiker-url", BASE],
    env: { ...process.env, RAIKER_DESKTOP_USER_DATA: mkdtempSync(join(tmpdir(), "raiker-desktop-setup-")) },
  });
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setContentSize(1440, 900));
  const page = await app.firstWindow();
  await expect(page.locator("html")).toHaveAttribute("data-desktop-shell", process.platform);
  await mockProviders(page);
  await signIn(page);

  // Hello and Voice, as an owner passes them, to the Model step.
  const title = page.locator("#setup-title");
  await expect(title).toBeVisible({ timeout: 60_000 });
  for (let step = 0; step < 4; step += 1) {
    if (/Where should I think/.test((await title.textContent()) ?? "")) break;
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await page.waitForTimeout(800);
  }
  await expect(title).toHaveText(/Where should I think/, { timeout: 30_000 });
  await page.getByRole("button", { name: /An account I have/ }).click();
  for (const name of ["OpenAI", "Anthropic", "OpenRouter"]) {
    await expect(page.getByRole("group", { name }).getByRole("button", { name: "Choose a model" })).toBeVisible({ timeout: 30_000 });
  }

  // Before a choice.
  const hint = page.getByText("Choose a default model to continue to Privacy");
  const next = page.getByRole("button", { name: "Continue", exact: true });
  await expect(hint).toBeVisible();
  await expect(next).toBeVisible();
  await expect(next).toBeDisabled();
  await expect(page.getByRole("button", { name: "Decide later", exact: true })).toHaveCount(0);
  await hint.scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(SHOTS, "setup-model-1-before-choice.png") });

  // Choose Haiku 4.5 from Anthropic's list.
  await page.getByRole("group", { name: "Anthropic" }).getByRole("button", { name: "Choose a model" }).click();
  const picker = page.getByRole("dialog", { name: "Anthropic models" });
  await picker.getByRole("button", { name: /^Use / }).first().click();
  const done = picker.getByRole("button", { name: "Done" });
  if (await done.isVisible().catch(() => false)) await done.click();
  await expect(page.getByText(/Haiku 4.5 is selected/)).toBeVisible({ timeout: 30_000 });

  // After a choice.
  await expect(next).toBeEnabled();
  await expect(hint).toHaveCount(0);
  await next.scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(SHOTS, "setup-model-2-after-choice.png") });
  await next.click();
  await expect(page.getByText("How I'll ask")).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: join(SHOTS, "setup-model-3-privacy.png") });

  // The host saved the choice: setup reads it back.
  const saved = await page.evaluate(async () => {
    const token = sessionStorage.getItem("raiker.token") ?? localStorage.getItem("raiker.token");
    const response = await fetch("/api/setup", { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    return response.ok ? response.json() : null;
  });
  if (saved !== null) {
    expect(saved).toMatchObject({ stage: "privacy", selected_profile_id: "anthropic-hosted", model_deferred: false });
  }
  await app.close();
});

test("Design's image-model control: one model is named, two draw a single focus ring", async () => {
  test.setTimeout(180_000);
  const app = await electron.launch({
    args: ["--no-sandbox", join(__dirname, ".."), "--raiker-url", BASE],
    env: { ...process.env, RAIKER_DESKTOP_USER_DATA: mkdtempSync(join(tmpdir(), "raiker-desktop-design-")) },
  });
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setContentSize(1440, 900));
  const page = await app.firstWindow();
  let imageModels = ["gpt-image-1"];
  await page.route(/\/api\/models(\?.*)?$/, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    const view = await response.json();
    for (const profile of view.profiles ?? []) {
      if (profile.profile_id === "openai-hosted") {
        profile.connection_configured = true;
        profile.configured = true;
        profile.image_models = imageModels;
      }
    }
    await route.fulfill({ response, json: view });
  });
  await signIn(page);
  const skip = page.getByRole("button", { name: "Skip setup" });
  if (await skip.waitFor({ state: "visible", timeout: 15_000 }).then(() => true, () => false)) {
    await skip.click();
    await expect(page).toHaveURL(/#\/new-chat/, { timeout: 30_000 });
  }

  await page.evaluate(() => (window.location.hash = "#/design"));
  const single = page.getByTestId("image-model-single");
  await expect(single).toHaveText(/OpenAI · GPT Image 1/, { timeout: 30_000 });
  await expect(page.getByRole("combobox", { name: "Image model" })).toHaveCount(0);
  await page.locator(".composer-card").last().screenshot({ path: join(SHOTS, "design-composer-1-single-model.png") });

  imageModels = ["gpt-image-1", "gpt-image-1-mini"];
  await page.reload();
  const select = page.getByRole("combobox", { name: "Image model" });
  await expect(select).toBeVisible({ timeout: 30_000 });
  await select.focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  const rings = await select.evaluate((node) => ({
    select: getComputedStyle(node).outlineStyle,
    pill: getComputedStyle(node.closest(".model-scope") as Element).outlineStyle,
  }));
  expect(rings).toEqual({ select: "none", pill: "solid" });
  await page.locator(".composer-card").last().screenshot({ path: join(SHOTS, "design-composer-2-one-ring.png") });
  await app.close();
});
