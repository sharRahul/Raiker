/** Owner-requested simplification, QUI-L08; real host, no model keys or inference. */
import { expect, test } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const stage = process.env.RAIKER_MODELS_CAPTURE_STAGE ?? "after";
const shots = `../../output/playwright/2026-11-06-models-simplification/${stage}`;
test("RT-MODELS-SIMPLE-01: main page, every Add source, and model settings", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  if (stage === "after") await page.route("**/api/hugging-face/trending", route => route.fulfill({ json: {
    items: [{ repo_id: "layout-fixture/a-long-repository-name-for-checking-dialog-width-GGUF", downloads: 42, likes: 3, gated: false }],
  } }));
  const decisions = page.waitForResponse(response => response.url().endsWith("/api/model-decisions") && response.ok());
  await page.goto(`${BASE}/#/models`);
  await expect(page.getByRole("heading", { name: "My models", exact: true })).toBeVisible({ timeout: 30_000 });
  await decisions;
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => resolve())));
  await capture(page, `${shots}/models.png`);
  for (const source of ["account", "local", "huggingface", "custom"]) {
    await page.goto(`${BASE}/#/models?tab=add&source=${source}`);
    const dialog = page.getByRole("dialog", { name: "Add model", exact: true });
    await expect(dialog).toBeVisible({ timeout: 30_000 });
    if (stage === "after") {
      expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 2)).toBe(true);
      if (source === "account") {
        const search = dialog.getByRole("searchbox", { name: "Search providers" });
        await search.fill("Anthropic");
        await expect(dialog.getByRole("heading", { name: "Anthropic", exact: true })).toBeVisible({ timeout: 30_000 });
        await expect(dialog.getByRole("heading", { name: "OpenAI", exact: true })).toHaveCount(0);
        await search.clear();
      }
      if (source === "local") {
        expect(await dialog.locator(".row-main").first().evaluate(element => element.getBoundingClientRect().width)).toBeGreaterThan(250);
        await expect(dialog.getByRole("button", { name: "Pull model", exact: true })).not.toBeVisible({ timeout: 30_000 });
      }
    }
    await captureElement(dialog, `${shots}/add-${source}.png`);
  }
  await page.goto(`${BASE}/#/settings?tab=advanced&kind=models`);
  await expect(page.getByRole("heading", { name: "Work defaults", exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Reading your defaults…", { exact: true })).toHaveCount(0, { timeout: 30_000 });
  await expect(page.getByText("Checking this computer…", { exact: true })).toHaveCount(0, { timeout: 30_000 });
  await capture(page, `${shots}/model-settings.png`);
  if (stage === "after") {
    const tabs = page.getByRole("tablist", { name: "Model settings" });
    await expect(tabs.getByRole("tab")).toHaveText(["Running models", "Library", "Activity", "Advanced"]);
    for (const [label, id] of [["Library", "library"], ["Activity", "activity"], ["Advanced", "advanced"]]) {
      await tabs.getByRole("tab", { name: label, exact: true }).click();
      await expect(page.getByRole("tabpanel", { name: label, exact: true })).toBeVisible({ timeout: 30_000 });
      await expect(page).toHaveURL(new RegExp(`modelsPanel=${id}`));
      await expect(page.getByRole("heading", { name: "Work defaults", exact: true })).toBeVisible({ timeout: 30_000 });
      await expect(page.getByText("Loading your model library…", { exact: true })).toHaveCount(0, { timeout: 30_000 });
      await expect(page.getByText("Reading your models…", { exact: true })).toHaveCount(0, { timeout: 30_000 });
      if (id === "library") await page.getByRole("textbox", { name: "Absolute model folder", exact: true }).fill("/tmp/unsaved-layout-fixture");
      await capture(page, `${shots}/settings-${id}.png`);
    }
    await tabs.getByRole("tab", { name: "Library", exact: true }).click();
    await expect(page.getByRole("textbox", { name: "Absolute model folder", exact: true })).toHaveValue("/tmp/unsaved-layout-fixture");
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto(`${BASE}/#/models?tab=add&source=huggingface`);
    const dialog = page.getByRole("dialog", { name: "Add model", exact: true });
    await expect(dialog).toBeVisible({ timeout: 30_000 });
    expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 2)).toBe(true);
    await captureElement(dialog, `${shots}/huggingface-dark-1280.png`);
    await dialog.getByRole("button", { name: "Close", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await page.getByRole("button", { name: "More pages and settings", exact: true }).click();
    await expect(page.getByRole("link", { name: "Settings", exact: true })).toBeVisible({ timeout: 30_000 });
    await capture(page, `${shots}/settings-cog-menu.png`);
  }
});

test("RT-MODELS-SIMPLE-02: model details and picker keep advanced controls reachable", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  // A declared read fixture exposes a model's controls without storing a key,
  // selecting a real model, changing a default or contacting a provider.
  await page.route("**/api/models", async route => {
    const response = await route.fetch();
    const body = await response.json();
    const profile = {
      ...body.profiles.find((row: { provider: string }) => row.provider === "anthropic"),
      model: "layout-fixture-model", connection_configured: true, configured: true,
      ready: true, readiness_state: "ready", selected: true,
    };
    body.profiles = body.profiles.map((row: { provider: string }) => row.provider === "anthropic" ? profile : { ...row, selected: false });
    body.chat_profiles = [profile];
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/models/capacities", route => route.fulfill({ json: { can_override: true, entries: [], sync: [] } }));
  await page.route("**/api/models/anthropic-hosted/provider-models", route => route.fulfill({ json: {
    profile_id: "anthropic-hosted", status: "available", reason_code: null,
    models: ["layout-fixture-model", "layout-fixture-alternative"], model_count: 2,
  } }));
  await page.goto(`${BASE}/#/models`);
  await page.getByRole("button", { name: "Details and connection", exact: true }).click();
  const details = page.getByRole("dialog").last();
  await expect(details.getByText("Usage and limits", { exact: true })).toBeVisible();
  await expect(details.getByText("Context window override", { exact: true })).toBeVisible();
  await expect(details.getByRole("button", { name: "Save override", exact: true })).not.toBeVisible();
  await details.getByText("Context window override", { exact: true }).click();
  await expect(details.getByRole("button", { name: "Save override", exact: true })).toBeVisible();
  await captureElement(details, `${shots}/model-details.png`);
  await details.getByRole("button", { name: "Close model details", exact: true }).click();
  await page.getByRole("button", { name: "Add model", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add model", exact: true });
  await expect(add).toBeVisible({ timeout: 30_000 });
  await add.getByRole("button", { name: /An account I have/ }).click();
  const card = add.locator(".provider-card").filter({ has: page.getByRole("heading", { name: "Anthropic", exact: true }) });
  await card.getByRole("button", { name: /More actions/ }).click();
  await page.getByRole("menuitem", { name: "Select models…", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Anthropic models", exact: true });
  await expect(picker).toBeVisible({ timeout: 30_000 });
  await expect(picker.getByRole("checkbox", { name: "Layout Fixture Alternative", exact: true })).toBeVisible();
  await captureElement(picker, `${shots}/model-picker.png`);
});
