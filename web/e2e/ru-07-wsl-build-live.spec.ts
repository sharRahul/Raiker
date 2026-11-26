/**
 * RT-WSL-BUILD-01: real model + enforced WSL2; no approval is accepted.
 * Known failing qualification: the broker parks copied medium-risk writes
 * before RuntimeAuthority sees the owner's Allow mode (TO_BE_FIXED.md).
 * Needs a running host and a local model that actually emits tool calls.
 */
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, dismissFirstRunModelSetup, keepOffered, pressCardAction, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const MODEL = process.env.RAIKER_LIVE_OLLAMA_MODEL ?? "qwen3.5:9b";
const MODEL_LABEL = process.env.RAIKER_LIVE_OLLAMA_MODEL_LABEL ?? "Qwen 3.5:9B";

test.afterEach(async ({ page }) => {
  await capture(page, join(import.meta.dirname, "..", "..", "output", "playwright", "ru-07-wsl-build-last.png")).catch(() => undefined);
});

test("RT-WSL-BUILD-01 — sandbox posture writes and tests without approval", async ({ page }) => {
  test.setTimeout(1_200_000);
  page.setDefaultTimeout(60_000);
  await signInAsOwner(page, BASE);
  console.log("WSL journey: signed in");
  await dismissFirstRunModelSetup(page).catch(() => undefined);
  await page.goto(`${BASE}/#/models?tab=add&source=local`);
  console.log("WSL journey: opened local models");
  const row = page.locator(".local-row", { has: page.getByRole("heading", { name: "Ollama", exact: true }) });
  await pressCardAction(page, row, /^(Choose a model|Select models…)$/);
  console.log("WSL journey: opened Ollama picker");
  await capture(page, join(import.meta.dirname, "..", "..", "output", "playwright", "ru-07-ollama-picker.png"));
  await keepOffered(page.getByRole("dialog", { name: "Ollama models" }), MODEL);
  console.log("WSL journey: kept local coding model");
  await page.goto(`${BASE}/#/capabilities`);
  await page.getByRole("navigation", { name: "Permission categories" }).waitFor({ timeout: 60_000 });
  const panel = page.getByTestId("postures");
  await expect(panel).toBeVisible({ timeout: 60_000 });
  const preset = page.getByRole("region", { name: "Set up for Build" });
  if (await preset.isVisible().catch(() => false)) {
    await preset.getByRole("checkbox").check();
    await preset.getByRole("button", { name: /^Turn on \d+$/ }).click();
    await expect(preset).toBeHidden({ timeout: 60_000 });
  }
  await expect(panel.getByRole("radio", { name: /Work in the sandbox/ })).toBeEnabled({ timeout: 60_000 });
  if (!(await panel.textContent())?.includes("Now: Work in the sandbox.")) {
    await panel.getByRole("radio", { name: /Work in the sandbox/ }).check();
    await panel.getByRole("button", { name: "Apply" }).click();
  }
  await expect(panel).toContainText("Now: Work in the sandbox.", { timeout: 60_000 });
  const name = `WSL posture ${Date.now()}`;
  await page.goto(`${BASE}/#/projects`);
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: `Open project ${name}` }).first().click();
  await page.getByLabel("Project checks").fill("python3 -m unittest -q");
  await page.getByRole("button", { name: "Save context" }).click();
  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  await page.getByLabel("Project for this build").selectOption({ label: name });
  await chooseModelForTurn(page, new RegExp(MODEL_LABEL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"), "Build composer");
  await page.getByLabel("Describe the change").fill(
    "Create pricing.py with final_price(total), giving a 10% discount for totals over 100. " +
    "Create test_pricing.py with unittest tests for 50, 100 and 150, then run python3 -m unittest -q. " +
    "Use your tools to create the files and execute the tests in this project's disposable copy.",
  );
  await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
  setTimeout(() => {
    void capture(page, join(import.meta.dirname, "..", "..", "output", "playwright", "ru-07-wsl-build-progress.png")).catch(() => undefined);
  }, 15_000);
  const approval = page.getByRole("button", { name: "Allow once", disabled: false }).or(
    page.locator("section.decisions").getByRole("button", { name: "Accept", disabled: false }),
  ).first();
  const outcome = page.getByTestId("build-outcome").last();
  const answered = page.getByRole("button", { name: "Copy response" }).last();
  await expect(approval.or(outcome).or(answered).first()).toBeVisible({ timeout: 300_000 });
  await capture(page, join(import.meta.dirname, "..", "..", "output", "playwright", "ru-07-wsl-build.png"));
  await expect(approval, "The sandbox posture must not ask for in-copy writes or tests").toBeHidden();
  await expect(outcome, "A model's prose is not evidence that files or checks ran").toHaveAttribute("data-outcome", "completed_verified", { timeout: 120_000 });
  await expect(outcome).toContainText("python3 -m unittest -q — passed");
});
