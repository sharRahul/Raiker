/**
 * BR-D01 — the checks an owner declares on a project, on a running host.
 *
 * The owner declares one check on Projects, saves it, and reads it back after a
 * reload. Then the real-turn half (BUG-346): on the same instance, Ollama's
 * cloud model is kept through the Models picker, Permissions' **Set up for
 * Build** is pressed, and a Build turn in a project with a declared check is
 * asked to create a file. **Accept** applies the write once, the turn carries
 * on, and the outcome reads **Not verified** with the check *not run after the
 * last change* — read from the runtime's own records, not the model's account.
 *
 * Needs a fresh `raiker-web` (`scripts/reset_live_workspace.py`) and an Ollama
 * on 127.0.0.1:11434 signed in to ollama.com so the cloud model answers. No API
 * key is typed anywhere.
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { chooseModelForTurn, keepOffered, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const OLLAMA_MODEL = process.env.RAIKER_LIVE_OLLAMA_CLOUD_MODEL ?? "gpt-oss:120b-cloud";
const OLLAMA_MODEL_LABEL = process.env.RAIKER_LIVE_OLLAMA_CLOUD_LABEL ?? "GPT oss:120B Cloud";

const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-18-br-d01-build-outcome");
const CHECK = "python -m pytest -q";

test("the owner's checks are saved on the project and read back after a reload", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  const name = `Outcome round ${Date.now()}`;
  await page.goto(`${BASE}/#/projects`);
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: `Open project ${name}` }).first().click();
  const checks = page.getByLabel("Project checks");
  await expect(checks).toBeVisible({ timeout: 30_000 });
  await checks.fill(CHECK);
  await expect(page.getByText(/Verified/).first()).toBeVisible();
  await page.getByRole("button", { name: "Save context" }).click();
  await expect(page.getByText(/unsaved changes/)).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: `Open project ${name}` }).first().click();
  await expect(page.getByLabel("Project checks")).toHaveValue(CHECK, { timeout: 30_000 });
  await capture(page, join(SHOTS, "01-project-checks.png"));
});

/** Keep Ollama's cloud model through the Models picker, as the BUG-346 round did — no Check. */
async function keepOllamaModel(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/models?tab=add`);
  const row = page.locator(".local-row", { has: page.getByRole("heading", { name: "Ollama", exact: true }) });
  await expect(row).toBeVisible({ timeout: 60_000 });
  await row.getByRole("button", { name: /^(Choose a model|Select|Select models…|Change model)$/ }).first().click();
  const picker = page.getByRole("dialog", { name: "Ollama models" });
  await expect(picker).toBeVisible({ timeout: 60_000 });
  await keepOffered(picker, OLLAMA_MODEL);
}

/** Permissions' own Build preset — now including the switch that makes Accept apply. */
async function setUpForBuild(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/capabilities`);
  await page.getByLabel("Search capabilities", { exact: true }).waitFor({ timeout: 60_000 });
  const preset = page.getByRole("region", { name: "Set up for Build" });
  if (!(await preset.isVisible().catch(() => false))) return;
  await preset.getByRole("button", { name: "What this turns on" }).click();
  await expect(preset.getByText("Approval execution relay")).toBeVisible();
  await capture(page, join(SHOTS, "02-set-up-for-build.png"), preset);
  await preset.getByRole("button", { name: /^Turn on \d+$/ }).click();
  await expect(preset).toBeHidden({ timeout: 60_000 });
}

test("an accepted Build write is applied once and the outcome names the check not run after it", async ({ page }) => {
  test.setTimeout(900_000);
  await signInAsOwner(page, BASE);
  await keepOllamaModel(page);
  await setUpForBuild(page);

  const name = `Outcome turn ${Date.now()}`;
  await page.goto(`${BASE}/#/projects`);
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: `Open project ${name}` }).first().click();
  const checks = page.getByLabel("Project checks");
  await expect(checks).toBeVisible({ timeout: 30_000 });
  await checks.fill(CHECK);
  await page.getByRole("button", { name: "Save context" }).click();
  await expect(page.getByText(/unsaved changes/)).toHaveCount(0);

  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  await page.getByLabel("Project for this build").selectOption({ label: name });
  const escaped = OLLAMA_MODEL_LABEL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  await chooseModelForTurn(page, new RegExp(escaped, "i"), "Build composer");

  const decisions = page.locator("section.decisions");
  // A real model sometimes answers in prose instead of calling a tool; that is
  // the model, not the product, so the request is repeated a bounded number of
  // times until it proposes the write.
  for (let attempt = 0; attempt < 4; attempt += 1) {
    await page
      .getByLabel("Describe the change")
      .fill(
        "Create a file named notes.txt in this project containing exactly the line " +
          "'hello from Build'. Use your write_file tool; do not print it to me.",
      );
    await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
    await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
    if (await decisions.getByRole("button", { name: "Accept" }).first().isVisible().catch(() => false)) break;
  }
  await expect(decisions.getByText("notes.txt").first()).toBeVisible({ timeout: 60_000 });
  // The relay is on, so the card carries no "will not be applied" warning.
  await expect(decisions.getByTestId("decision-record-only")).toHaveCount(0);
  await captureElement(decisions, join(SHOTS, "03-waiting-on-you.png"));

  await decisions.getByRole("button", { name: "Accept" }).first().click();
  // The resumed call's own row says it ran — not "failed", as BUG-346 read.
  await expect(page.getByRole("list", { name: "What Raiker did in this turn" }).getByRole("listitem").filter({ hasText: /Write file\s*notes\.txt\s*done/ }).first()).toBeVisible({ timeout: 300_000 });

  const outcome = page.getByTestId("build-outcome").last();
  await expect(outcome).toHaveAttribute("data-outcome", "completed_unverified", { timeout: 300_000 });
  await expect(outcome).toContainText(CHECK);
  await expect(outcome).toContainText("not run after the last change");
  // The live row for the resumed call says it ran, not that it failed.
  await expect(page.getByRole("listitem").filter({ hasText: /Write file\s*notes\.txt\s*failed/ })).toHaveCount(0);
  await capture(page, join(SHOTS, "04-accepted-write-not-verified.png"), outcome);

  // After the turn, Run is still available for the model the owner kept.
  await expect(page.getByText("No readiness check exists for this exact model")).toHaveCount(0);
  await page.getByLabel("Describe the change").fill("Add a second line to notes.txt.");
  await expect(page.getByRole("button", { name: "Run", exact: true })).toBeEnabled({ timeout: 30_000 });
  await page.getByLabel("Describe the change").fill("");
});
