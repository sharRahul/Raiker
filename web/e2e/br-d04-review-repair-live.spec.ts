/**
 * BR-D04 / BR-D05 — the patch review's validator, history and bounded repair, on a running host.
 *
 * On a fresh `raiker-web` (`scripts/reset_live_workspace.py`), a git repository
 * is connected in Build and a file in it is broken so it no longer parses.
 *
 * 1. **Review this patch** names *File does not parse* at its line — the
 *    independent parse validator, not a model's opinion.
 * 2. **Ask Raiker to fix** writes a scoped repair request into the composer and
 *    sends nothing; the owner sends it, and a real Anthropic turn repairs the
 *    file (each write accepted by the owner).
 * 3. Changes now says the last review was of an earlier version; reviewing
 *    again lists *File does not parse* under **Fixed since the last review**.
 * 4. Asked to commit, the decision card says the commit will carry
 *    `Raiker-Session` and `Raiker-Turn` before the owner decides.
 *
 * Needs `RAIKER_LIVE_WORKSPACE`, `RAIKER_LIVE_ANTHROPIC_KEY` and, for an
 * identity-linked key, `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { chooseModelForTurn, hostedProviderCard, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-19-br-d04-review-repair");
const REPO = "calc";

test.skip(WORKSPACE === "" || KEY === "", "RAIKER_LIVE_WORKSPACE or RAIKER_LIVE_ANTHROPIC_KEY is unset");

function git(root: string, ...args: string[]): string {
  return execFileSync("git", ["-C", root, "-c", "user.name=Live", "-c", "user.email=live@example.invalid", ...args], {
    encoding: "utf8",
  }).trim();
}

function seedBrokenRepository(): void {
  const root = join(WORKSPACE, REPO);
  if (!existsSync(join(root, ".git"))) {
    mkdirSync(root, { recursive: true });
    writeFileSync(join(root, "calc.py"), "def add(a, b):\n    return a + b\n");
    git(root, "init", "-q", "-b", "main");
    git(root, "add", ".");
    git(root, "commit", "-qm", "init");
  }
  writeFileSync(join(root, "calc.py"), "def add(a, b):\n    return a + b\n\ndef sub(a, b:\n    return a - b\n");
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

async function setUpForBuild(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/capabilities`);
  await page.getByLabel("Search capabilities", { exact: true }).waitFor({ timeout: 60_000 });
  const preset = page.getByRole("region", { name: "Set up for Build" });
  if (!(await preset.isVisible().catch(() => false))) return;
  await preset.getByRole("button", { name: /^Turn on \d+$/ }).click();
  await expect(preset).toBeHidden({ timeout: 60_000 });
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
  const name = `Repair round ${Date.now()}`;
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

async function acceptEverything(page: Page): Promise<void> {
  const decisions = page.locator("section.decisions");
  for (let step = 0; step < 8; step += 1) {
    await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
    const accept = decisions.getByRole("button", { name: "Accept" }).first();
    await accept.waitFor({ state: "visible", timeout: 15_000 }).catch(() => {});
    if (!(await accept.isVisible().catch(() => false))) return;
    await accept.click();
    await page.waitForTimeout(1_000);
  }
}

test("a broken file is found, repaired on request, and the review says it was fixed", async ({ page }) => {
  test.setTimeout(1_200_000);
  seedBrokenRepository();
  await signInAsOwner(page, BASE);
  await connectAnthropic(page);
  await setUpForBuild(page);
  await connectRepository(page);
  await workInNewProject(page);
  await openChanges(page);

  // 1. The validator names the syntax error at its line.
  const review = page.getByTestId("patch-review");
  await expect(review).toBeVisible({ timeout: 30_000 });
  // Re-runnable: the same broken patch reviewed on an earlier run is the
  // stored review, and is shown rather than reviewed again.
  const reviewButton = review.getByRole("button", { name: "Review this patch" });
  if (await reviewButton.isVisible().catch(() => false)) await reviewButton.click();
  await expect(review).toContainText("File does not parse", { timeout: 30_000 });
  await expect(review).toContainText("calc.py:4");
  await captureElement(review, join(SHOTS, "01-does-not-parse.png"));

  // 2. Ask Raiker to fix: the request lands in the composer, nothing is sent.
  const finding = review.locator("li", { hasText: "File does not parse" });
  await finding.getByRole("button", { name: "Ask Raiker to fix" }).click();
  const composer = page.getByLabel("Describe the change");
  await expect(composer).toHaveValue(/Fix this patch review finding in calc.py at line 4: File does not parse/);
  await expect(page.getByTestId("turn-control")).toBeHidden();
  await capture(page, join(SHOTS, "02-repair-request-in-composer.png"), composer);
  await chooseModelForTurn(page, /haiku|sonnet|opus|claude/i, "Build composer");
  await composer.fill(
    (await composer.inputValue()) + ` The file is ${REPO}/calc.py in the workspace; fix it with write_file.`,
  );
  await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
  await acceptEverything(page);
  await expect
    .poll(() => readFileSync(join(WORKSPACE, REPO, "calc.py"), "utf8"), { timeout: 120_000 })
    .toMatch(/def sub\(a, b\):/);

  // 3. The stored review is now of an earlier patch; reviewing again shows the fix.
  await openChanges(page);
  const again = page.getByTestId("patch-review");
  await expect(again.getByTestId("patch-review-stale")).toBeVisible({ timeout: 60_000 });
  await again.getByRole("button", { name: "Review this patch" }).click();
  await expect(again.getByTestId("patch-review-resolved")).toContainText("File does not parse", { timeout: 30_000 });
  await expect(again).not.toContainText("calc.py:4");
  await captureElement(again, join(SHOTS, "03-fixed-since-last-review.png"));

  // 4. The commit decision says what provenance it records, before it is made.
  await composer.fill(`Commit the change to ${REPO}/calc.py with your git_commit tool, message 'Fix sub'.`);
  await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
  await page.goto(`${BASE}/#/approvals`);
  const commitRow = page.getByRole("row", { name: /Git commit/ }).first();
  await expect(commitRow).toBeVisible({ timeout: 60_000 });
  await commitRow.getByRole("button", { name: "Review" }).click();
  await expect(page.getByText(/Raiker-Session and Raiker-Turn lines/).first()).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "04-commit-approval-names-provenance.png"));
});
