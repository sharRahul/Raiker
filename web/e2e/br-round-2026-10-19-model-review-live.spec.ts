/**
 * BR-D04 / BR-D05 / BR-01 — this round's Build delivery items, on a running host.
 *
 * On a fresh `raiker-web` (`scripts/reset_live_workspace.py`), a git repository
 * with a GitHub `origin` is connected in Build and a change with a real bug is
 * left uncommitted. Anthropic is connected through Models, as an owner does.
 *
 * 1. The Build header's target chip says what a turn here may do without
 *    asking: no delegation, so *Writes ask you* (BR-01).
 * 2. **Review this patch** takes the deterministic review, and it reads
 *    **Signed here** — signed by this installation and verified on read
 *    (BR-D05).
 * 3. **Ask … to review** sends the redacted patch to the composer's model and
 *    shows its reading under **Model review**, labelled as the model's reading,
 *    not a check, and signed too (BR-D04 selected model review).
 * 4. Asking again on the same patch reads the stored reading — the same model
 *    is never asked twice about one patch.
 *
 * Needs `RAIKER_LIVE_WORKSPACE`, `RAIKER_LIVE_ANTHROPIC_KEY` and, for an
 * identity-linked key, `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { chooseModelForTurn, hostedProviderCard, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-19-build-round-four");
const REPO = "widget";

test.skip(WORKSPACE === "" || KEY === "", "RAIKER_LIVE_WORKSPACE or RAIKER_LIVE_ANTHROPIC_KEY is unset");

function git(root: string, ...args: string[]): string {
  return execFileSync("git", ["-C", root, "-c", "user.name=Live", "-c", "user.email=live@example.invalid", ...args], {
    encoding: "utf8",
  }).trim();
}

function seedRepository(): void {
  const root = join(WORKSPACE, REPO);
  if (!existsSync(join(root, ".git"))) {
    mkdirSync(root, { recursive: true });
    writeFileSync(join(root, "stats.py"), "def mean(values):\n    return sum(values) / len(values)\n");
    git(root, "init", "-q", "-b", "main");
    git(root, "remote", "add", "origin", "https://github.com/octo/widget.git");
    git(root, "add", ".");
    git(root, "commit", "-qm", "init");
  }
  // A real bug for a reviewer to find: an off-by-one that drops the last value.
  writeFileSync(
    join(root, "stats.py"),
    "def mean(values):\n    return sum(values) / len(values)\n\n\ndef total(values):\n" +
      "    result = 0\n    for index in range(len(values) - 1):\n        result += values[index]\n    return result\n",
  );
}

async function connectAnthropic(page: Page): Promise<void> {
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    if (WORKSPACE_ID) {
      await page.getByRole("button", { name: "Advanced" }).click();
      await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE_ID);
    }
    await page.locator(".signin-connect").click();
    await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  }
  await keepModelAvailable(page, card, MODEL);
}

async function connectRepository(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/build`);
  const repoButton = page.locator("button.repo-button");
  await expect(repoButton).toBeVisible({ timeout: 30_000 });
  if ((await repoButton.textContent())?.includes(REPO)) return;
  await repoButton.click();
  const connector = page.getByRole("region", { name: "Repositories" });
  await connector.locator(".repo-label").first().waitFor({ timeout: 5_000 }).catch(() => {});
  if ((await connector.locator(".repo-label").filter({ hasText: new RegExp(`^${REPO}$`) }).count()) === 0) {
    await page.getByLabel("Folder inside this workspace").fill(REPO);
    await page.getByRole("button", { name: "Connect repository" }).click();
  }
  const row = connector.locator("li.repo", { has: page.locator(".repo-label", { hasText: new RegExp(`^${REPO}$`) }) });
  const use = row.getByRole("button", { name: "Use" });
  await expect(use.or(row.getByText("Active")).first()).toBeVisible({ timeout: 30_000 });
  if (await use.isVisible().catch(() => false)) await use.click();
  await page.getByRole("button", { name: "Close repositories" }).click();
  await expect(repoButton).toContainText(REPO, { timeout: 30_000 });
}

async function workInNewProject(page: Page): Promise<void> {
  const name = `Review round ${Date.now()}`;
  await page.goto(`${BASE}/#/projects`);
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("button", { name: `Open project ${name}` }).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  await page.getByLabel("Project for this build").selectOption({ label: name });
}

async function openChanges(page: Page): Promise<void> {
  const tab = page.getByRole("tab", { name: /^Changes/ });
  if (!(await tab.isVisible().catch(() => false))) {
    await page.getByRole("button", { name: "Show background work" }).click();
  }
  await page.getByRole("tab", { name: /^Changes/ }).click();
}

test("the target says writes ask, the review is signed, and a real model reads the patch once", async ({ page }) => {
  test.setTimeout(900_000);
  seedRepository();
  await signInAsOwner(page, BASE);
  await connectAnthropic(page);
  await connectRepository(page);
  await workInNewProject(page);

  // 1. BR-01 — no delegation on octo/widget, so every repository write asks.
  const chip = page.getByTestId("build-target");
  await expect(chip).toContainText("Writes ask you", { timeout: 30_000 });
  await expect(chip).toHaveAttribute("title", /Merging is never delegated/);
  await captureElement(chip, join(SHOTS, "01-target-writes-ask-you.png"));

  // 2. BR-D05 — the deterministic review, signed by this installation.
  await openChanges(page);
  const review = page.getByTestId("patch-review");
  await expect(review).toBeVisible({ timeout: 30_000 });
  // A rerun on the same workspace finds this patch already reviewed — the
  // stored review, not a second one — so the button is pressed only if shown.
  const reviewButton = review.getByRole("button", { name: "Review this patch" });
  if (await reviewButton.isVisible().catch(() => false)) await reviewButton.click();
  await expect(review.locator(".head").first().getByText("Signed here")).toBeVisible({ timeout: 60_000 });
  await captureElement(review, join(SHOTS, "02-review-signed-here.png"));

  // 3. BR-D04 — with no model chosen in the composer, asking says so and
  // reaches no provider (FIXED-978); with one chosen, that model reads the patch.
  const modelPart = page.getByTestId("patch-model-review");
  const composerModel = page
    .getByRole("group", { name: "Build composer" })
    .getByRole("button", { name: /^Model for this turn:/ });
  const chosen = (await composerModel.getAttribute("aria-label")) ?? (await composerModel.textContent()) ?? "";
  // A rerun on the same workspace finds this patch already read by this model.
  const alreadyRead = await modelPart.getByText(/These are its reading, not checks/).isVisible().catch(() => false);
  if (!alreadyRead && /Not selected/.test(chosen)) {
    await modelPart.getByRole("button", { name: /^Ask .+ to review$/ }).click();
    await expect(modelPart.getByRole("alert")).toContainText("Choose a model in the composer first", { timeout: 30_000 });
    await captureElement(modelPart, join(SHOTS, "03a-no-model-chosen.png"));
  }
  await chooseModelForTurn(page, /haiku|sonnet|opus|claude/i, "Build composer");
  if (!alreadyRead) {
    const ask = modelPart.getByRole("button", { name: /^Ask .+ to review$/ });
    await expect(ask).toBeVisible();
    await ask.click();
  }
  await expect(modelPart.getByText(/These are its reading, not checks/)).toBeVisible({ timeout: 180_000 });
  await expect(modelPart.getByText("Signed here")).toBeVisible();
  await captureElement(modelPart, join(SHOTS, "03-model-review.png"));
  await capture(page, join(SHOTS, "04-build-with-model-review.png"));

  // 4. The same patch, the same model: after a reload the stored reading is
  // shown, and no "Ask" button invites a second request.
  await page.reload();
  await chooseModelForTurn(page, /haiku|sonnet|opus|claude/i, "Build composer");
  await openChanges(page);
  const stored = page.getByTestId("patch-model-review");
  await expect(stored.getByText(/These are its reading, not checks/)).toBeVisible({ timeout: 60_000 });
  await expect(stored.getByRole("button", { name: /^Ask .+ to review$/ })).toHaveCount(0);
});
