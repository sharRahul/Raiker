/**
 * BR-D01 / BR-D02 / BR-D04 — where a Build turn runs, and the review of its patch, on a running host.
 *
 * On a fresh `raiker-web` (`scripts/reset_live_workspace.py`), a git repository
 * is created inside the workspace and connected in Build. Then:
 *
 * 1. The header names the target — branch, commit and where code runs — from
 *    the server's own description.
 * 2. Anthropic is connected through Models with the round's key (and workspace
 *    ID, for an identity-linked key), and a real Build turn creates a file in
 *    the repository. Accepting applies it, and the outcome says where the turn
 *    ran and that nothing verified the change.
 * 3. A seeded uncommitted change is reviewed from Changes: the possible
 *    credential and the missing test are named at their file and line, and
 *    after a reload the same patch reads **Reviewed** instead of being reviewed
 *    again.
 * 4. The repository's folder is moved away: the header says so, and a Build
 *    turn is refused before it starts instead of running in the workspace root.
 *
 * Needs `RAIKER_LIVE_WORKSPACE` (the host's workspace directory),
 * `RAIKER_LIVE_ANTHROPIC_KEY` and, for an identity-linked key,
 * `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`. No key is written into this file.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { chooseModelForTurn, hostedProviderCard, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-19-br-d02-d04-build-target-review");
const REPO = "app";

test.skip(WORKSPACE === "", "RAIKER_LIVE_WORKSPACE is unset");

function git(root: string, ...args: string[]): string {
  return execFileSync("git", ["-C", root, ...args], { encoding: "utf8" }).trim();
}

function seedRepository(): string {
  const root = join(WORKSPACE, REPO);
  if (existsSync(join(WORKSPACE, `${REPO}-moved`))) renameSync(join(WORKSPACE, `${REPO}-moved`), root);
  if (!existsSync(join(root, ".git"))) {
    mkdirSync(join(root, "src"), { recursive: true });
    writeFileSync(join(root, "src", "service.py"), "def total(items):\n    return sum(items)\n");
    git(root, "init", "-q", "-b", "main");
    git(root, "-c", "user.name=Live", "-c", "user.email=live@example.invalid", "add", ".");
    git(root, "-c", "user.name=Live", "-c", "user.email=live@example.invalid", "commit", "-qm", "init");
  }
  return git(root, "rev-parse", "--short", "HEAD");
}

async function connectRepository(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/build`);
  const repoButton = page.locator("button.repo-button");
  await expect(repoButton).toBeVisible({ timeout: 30_000 });
  if ((await repoButton.textContent())?.includes(REPO)) return;
  await repoButton.click();
  const connector = page.getByRole("region", { name: "Repositories" });
  await expect(connector).toBeVisible();
  await connector.locator(".repo-label").first().waitFor({ timeout: 5_000 }).catch(() => {});
  if ((await connector.locator(".repo-label").filter({ hasText: REPO }).count()) === 0) {
    await page.getByLabel("Folder inside this workspace").fill(REPO);
    await page.getByRole("button", { name: "Connect repository" }).click();
  }
  const use = connector.getByRole("button", { name: "Use" });
  await expect(use.or(connector.getByText("Active")).first()).toBeVisible({ timeout: 30_000 });
  if ((await use.count()) > 0) await use.first().click();
  await expect(repoButton).toContainText(REPO, { timeout: 30_000 });
  await page.getByRole("button", { name: "Close repositories" }).click();
}

async function connectAnthropic(page: Page): Promise<void> {
  expect(KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
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

/** Build turns are filed into a project; create one and choose it for this turn. */
async function workInNewProject(page: Page, label: string): Promise<void> {
  const name = `${label} ${Date.now()}`;
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
  const changesTab = page.getByRole("tab", { name: /^Changes/ });
  if (!(await changesTab.isVisible().catch(() => false))) {
    await page.getByRole("button", { name: "Show background work" }).click();
  }
  await page.getByRole("tab", { name: /^Changes/ }).click();
}

test("the Build header names the target a turn would run against", async ({ page }) => {
  test.setTimeout(180_000);
  const head = seedRepository();
  await signInAsOwner(page, BASE);
  await connectRepository(page);
  const chip = page.getByTestId("build-target");
  await expect(chip).toContainText(`main · ${head}`, { timeout: 30_000 });
  await expect(chip).toHaveAttribute("title", /Folder: app/);
  await expect(chip).toHaveAttribute("title", /Target fingerprint: [0-9a-f]{12}/);
  await capture(page, join(SHOTS, "01-build-target-chip.png"), chip);
});

test("a real Build turn's outcome says where it ran and what it can claim", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(900_000);
  const head = seedRepository();
  await signInAsOwner(page, BASE);
  await connectAnthropic(page);
  await setUpForBuild(page);
  await connectRepository(page);
  await workInNewProject(page, "Target round");
  await chooseModelForTurn(page, /haiku|sonnet|opus|claude/i, "Build composer");

  const decisions = page.locator("section.decisions");
  for (let attempt = 0; attempt < 4; attempt += 1) {
    await page
      .getByLabel("Describe the change")
      .fill(
        "Create the file app/NOTES.md containing exactly the line 'Build target round'. " +
          "Use your write_file tool with the path app/NOTES.md; do not print it to me.",
      );
    await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
    await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
    if (await decisions.getByRole("button", { name: "Accept" }).first().isVisible().catch(() => false)) break;
  }
  await expect(decisions.getByText("NOTES.md").first()).toBeVisible({ timeout: 60_000 });
  await decisions.getByRole("button", { name: "Accept" }).first().click();

  const outcome = page.getByTestId("build-outcome").last();
  await expect(outcome).toHaveAttribute("data-outcome", "completed_unverified", { timeout: 300_000 });
  await expect(outcome).toContainText(`Ran in app on main from ${head}`);
  await expect(outcome).toContainText("No checks are declared");
  expect(existsSync(join(WORKSPACE, REPO, "NOTES.md"))).toBe(true);
  await capture(page, join(SHOTS, "02-real-turn-outcome-target.png"), outcome);
});

test("the exact patch is reviewed once and named at its lines", async ({ page }) => {
  test.setTimeout(240_000);
  seedRepository();
  const root = join(WORKSPACE, REPO);
  // Seeded faults: a credential-shaped assignment, a breakpoint, and no test.
  writeFileSync(
    join(root, "src", "service.py"),
    "def total(items):\n    password = '" + "hunter2".repeat(2) + "'\n    breakpoint()\n    return sum(items)\n",
  );
  await signInAsOwner(page, BASE);
  await connectRepository(page);
  await openChanges(page);
  const review = page.getByTestId("patch-review");
  await expect(review).toBeVisible({ timeout: 30_000 });
  await review.getByRole("button", { name: "Review this patch" }).click();
  await expect(review.getByRole("status")).toContainText(/finding/, { timeout: 30_000 });
  await expect(review).toContainText("Possible credential added");
  await expect(review).toContainText("src/service.py:2");
  await expect(review).toContainText("Debugging statement left in");
  await expect(review).toContainText("src/service.py:3");
  await expect(review).toContainText("Source changed without a test change");
  await expect(review).not.toContainText("hunter2");
  await captureElement(review, join(SHOTS, "03-patch-review-findings.png"));

  // The same patch, after a reload, is the stored review — not a second one.
  await page.reload();
  await openChanges(page);
  await expect(page.getByTestId("patch-review")).toContainText(/^.*Reviewed ·/, { timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Review this patch" })).toHaveCount(0);
  await captureElement(page.getByTestId("patch-review"), join(SHOTS, "04-patch-review-stored.png"));

  git(root, "checkout", "--", ".");
  rmSync(join(root, "NOTES.md"), { force: true });
});

test("a Build turn on a moved repository folder is refused before it starts", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(240_000);
  seedRepository();
  await signInAsOwner(page, BASE);
  await connectRepository(page);
  renameSync(join(WORKSPACE, REPO), join(WORKSPACE, `${REPO}-moved`));
  try {
    await page.reload();
    await expect(page.getByText("That folder is no longer in the workspace.")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("build-target")).toHaveCount(0);
    await workInNewProject(page, "Moved round");
    await expect(page.getByText("That folder is no longer in the workspace.")).toBeVisible({ timeout: 30_000 });
    await chooseModelForTurn(page, /haiku|sonnet|opus|claude/i, "Build composer");
    await page.getByLabel("Describe the change").fill("Add a README to this repository.");
    await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
    await expect(page.getByText(/The repository folder app is no longer in the workspace/).first()).toBeVisible({
      timeout: 120_000,
    });
    expect(existsSync(join(WORKSPACE, "README.md"))).toBe(false);
    await capture(page, join(SHOTS, "05-missing-target-refused.png"));
  } finally {
    renameSync(join(WORKSPACE, `${REPO}-moved`), join(WORKSPACE, REPO));
  }
});
