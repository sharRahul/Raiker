/**
 * BUG-340 — a cloud Ollama model was described as never leaving the device.
 *
 * A running Ollama lists its cloud models (`gpt-oss:20b-cloud`, served from
 * ollama.com) beside the ones it runs here. First-run setup recommended it with
 * "its models never leave this device", and kept saying so after the owner chose
 * the cloud model. This round drives the real first run against a real Ollama
 * on 127.0.0.1:11434 that serves at least one cloud model, and checks that no
 * screen on the way makes the device-only claim for it.
 *
 * Needs a workspace reset with `scripts/reset_live_workspace.py` and an Ollama
 * signed in to ollama.com so the cloud model answers. No API key.
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { settled } from "./destinations";
import { OWNER_CREDENTIALS } from "./hosted-provider";
import { LIVE_BASE, sendTurn } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-17-bug-340-ollama-cloud");
const CLOUD_LABEL = process.env.RAIKER_LIVE_OLLAMA_CLOUD_LABEL ?? "GPT oss:20B Cloud";
const DEVICE_CLAIM = /never leave this device|runs on this device/i;

test.describe.configure({ mode: "serial" });

async function createOwner(page: Page): Promise<boolean> {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const username = page.getByLabel("Username");
  await expect(username).toBeEnabled({ timeout: 60_000 });
  const confirm = page.getByLabel("Confirm password");
  if (!(await confirm.isVisible().catch(() => false))) return false;
  await username.fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
  await confirm.fill(OWNER_CREDENTIALS.password);
  await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  return true;
}

test("choosing a cloud Ollama model in setup names ollama.com and never claims the device", async ({ page }) => {
  test.setTimeout(300_000);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  test.skip(!(await createOwner(page)), "This scenario is about first run and needs a reset workspace.");

  const title = page.locator("#setup-title");
  await expect(title).toBeVisible({ timeout: 60_000 });
  // Welcome, then This device (when shown), until the model stage.
  for (let step = 0; step < 3; step += 1) {
    if (/Choose how Raiker should think/.test((await title.textContent()) ?? "")) break;
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForTimeout(500);
  }
  await expect(title).toHaveText(/Choose how Raiker should think/, { timeout: 30_000 });

  // Before a choice the runtime is offered from its own row. Nothing on the
  // screen may promise that a Cloud model stays here.
  const setupContent = page.locator(".setup-content");
  const ollama = page.getByRole("group", { name: "Ollama", exact: true });
  await expect(ollama.getByText("Running on this device", { exact: false })).toBeVisible({ timeout: 60_000 });
  await expect(setupContent).not.toContainText(DEVICE_CLAIM);
  await capture(page, join(SHOTS, "01-setup-ollama-running.png"));

  await ollama.getByRole("button", { name: "Choose a model" }).click();
  const picker = page.getByRole("dialog", { name: "Ollama models" });
  const use = picker.getByRole("button", { name: `Use ${CLOUD_LABEL}` });
  await expect(use).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "02-picker-lists-the-cloud-model.png"));
  await use.click();

  const picked = page.locator(".picked");
  await expect(picked).toContainText(`${CLOUD_LABEL} is selected.`, { timeout: 30_000 });
  await expect(picked).toContainText("Its requests are sent to ollama.com, off this device.");
  // The recommendation that appears once Ollama has a model is the screen the
  // defect was seen on: it names the cloud destination instead.
  const recommended = page.locator(".recommended");
  await expect(recommended).toContainText("Ollama is running here", { timeout: 30_000 });
  await expect(recommended).toContainText("ollama.com");
  await expect(setupContent).not.toContainText(DEVICE_CLAIM);
  await capture(page, join(SHOTS, "03-chosen-cloud-model-says-where-it-runs.png"));

  await page.getByRole("button", { name: "Continue" }).click();
  await expect(title).toHaveText(/Where may Raiker send model requests\?/, { timeout: 30_000 });
  await expect(page.getByRole("note")).toContainText(`${CLOUD_LABEL} is selected. Its requests are sent to ollama.com`);
  await capture(page, join(SHOTS, "04-privacy-step-names-the-chosen-models-destination.png"));
  await page.getByRole("button", { name: /Local, and the providers I connect/ }).click();

  // Past Permissions and Check to the last stage.
  const ready = page.getByRole("heading", { name: "Your Raiker is ready" });
  for (let step = 0; step < 4 && !(await ready.isVisible().catch(() => false)); step += 1) {
    const next = page.getByRole("button", { name: "Continue" });
    if (await next.isVisible().catch(() => false)) await next.click();
    await page.waitForTimeout(1_500);
  }
  await expect(ready).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "Start using Raiker" }).click();
  await expect(title).toBeHidden({ timeout: 30_000 });

  // The selection stands, and the turn is answered by the cloud model.
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  await expect(page.getByRole("button", { name: `Model for this turn: ${CLOUD_LABEL}` }).first()).toBeVisible({
    timeout: 30_000,
  });
  await sendTurn(page, "Reply with exactly RAIKER_E2E_OK and nothing else.");
  // The answer, not the prompt that contains the same token.
  await expect(page.locator(".message-bubble-raiker").last()).toContainText("RAIKER_E2E_OK", { timeout: 120_000 });
  await capture(page, join(SHOTS, "05-chat-answered-by-the-cloud-model.png"));
  // The provider receipt: which profile and model answered this turn.
  await page.locator("summary", { hasText: "Evidence" }).last().click();
  await page.waitForTimeout(1_000);
  await capture(page, join(SHOTS, "06-turn-evidence-names-the-cloud-model.png"));

  // The comparison places it where it runs, not where its runtime runs.
  await page.goto(`${BASE}/#/models?tab=compare`);
  await settled(page);
  const row = page.getByRole("row", { name: new RegExp(CLOUD_LABEL) }).first();
  if (await row.isVisible().catch(() => false)) {
    await expect(row).toContainText("Hosted service");
    await expect(row).toContainText("Prompts leave this device");
    await capture(page, join(SHOTS, "07-comparison-places-it-off-device.png"));
  }
  expect(consoleErrors.filter((text) => !/favicon/i.test(text)), consoleErrors.join("\n")).toEqual([]);
});
