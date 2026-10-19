/**
 * BR-03 / BR-D05 — a task worktree, and a commit that says Raiker made it, on a running host.
 *
 * On a fresh `raiker-web` (`scripts/reset_live_workspace.py`), a git repository
 * is created inside the workspace and connected in Build. Then:
 *
 * 1. **New worktree** makes `svc.worktrees/notes` on a new `raiker/notes`
 *    branch, connected as its own repository; choosing it moves the header's
 *    target to that branch while the main checkout stays on `main`.
 * 2. Anthropic is connected through Models with the round's key (and workspace
 *    ID), and a real Build turn in the worktree creates a file and commits it.
 *    Accepting each step applies it, and **Changes → Recent commits** labels the
 *    commit **Made in Raiker**, read back from its own trailers.
 * 3. **Remove worktree** with uncommitted work in it is refused and the work
 *    stays; once it is clean the worktree goes and its branch is kept.
 *
 * Needs `RAIKER_LIVE_WORKSPACE`, `RAIKER_LIVE_ANTHROPIC_KEY` and, for an
 * identity-linked key, `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`. No key is written
 * into this file.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { chooseModelForTurn, hostedProviderCard, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-19-br-d02-d05-worktree-provenance");
const REPO = "svc";
const WORKTREE = `${REPO}.worktrees/notes`;

test.skip(WORKSPACE === "" || KEY === "", "RAIKER_LIVE_WORKSPACE or RAIKER_LIVE_ANTHROPIC_KEY is unset");

function git(root: string, ...args: string[]): string {
  return execFileSync("git", ["-C", root, "-c", "user.name=Live", "-c", "user.email=live@example.invalid", ...args], {
    encoding: "utf8",
  }).trim();
}

function seedRepository(): void {
  const root = join(WORKSPACE, REPO);
  if (existsSync(join(root, ".git"))) return;
  mkdirSync(root, { recursive: true });
  writeFileSync(join(root, "service.py"), "def ping():\n    return 'pong'\n");
  git(root, "init", "-q", "-b", "main");
  git(root, "add", ".");
  git(root, "commit", "-qm", "init");
}

async function openRepositories(page: Page) {
  await page.locator("button.repo-button").click();
  const connector = page.getByRole("region", { name: "Repositories" });
  await expect(connector).toBeVisible();
  return connector;
}

async function connectRepository(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/build`);
  const repoButton = page.locator("button.repo-button");
  await expect(repoButton).toBeVisible({ timeout: 30_000 });
  const connector = await openRepositories(page);
  await connector.locator(".repo-label").first().waitFor({ timeout: 5_000 }).catch(() => {});
  if ((await connector.locator(".repo-label").filter({ hasText: new RegExp(`^${REPO}$`) }).count()) === 0) {
    await page.getByLabel("Folder inside this workspace").fill(REPO);
    await page.getByRole("button", { name: "Connect repository" }).click();
    await expect(connector.locator(".repo-label").filter({ hasText: new RegExp(`^${REPO}$`) })).toBeVisible({
      timeout: 30_000,
    });
  }
  await page.getByRole("button", { name: "Close repositories" }).click();
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

async function workInNewProject(page: Page): Promise<void> {
  const name = `Worktree round ${Date.now()}`;
  await page.goto(`${BASE}/#/projects`);
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("button", { name: `Open project ${name}` }).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  await page.getByLabel("Project for this build").selectOption({ label: name });
}

test("a task worktree, a real commit in it, and its provenance read back", async ({ page }) => {
  test.setTimeout(1_200_000);
  seedRepository();
  const mainHead = git(join(WORKSPACE, REPO), "rev-parse", "--short", "HEAD");
  await signInAsOwner(page, BASE);
  await connectAnthropic(page);
  await setUpForBuild(page);
  await connectRepository(page);

  // 1. A worktree on an owned branch, chosen as the target.
  let connector = await openRepositories(page);
  if ((await connector.locator(".repo-label").filter({ hasText: "· notes" }).count()) === 0) {
    await connector.getByRole("button", { name: `New worktree from ${REPO}` }).click();
    await connector.getByLabel("Worktree name").fill("notes");
    await connector.getByRole("button", { name: "Create worktree" }).click();
    await expect(connector.getByText(`Created raiker/notes in ${WORKTREE}`)).toBeVisible({ timeout: 30_000 });
  }
  await captureElement(connector, join(SHOTS, "01-worktree-created.png"));
  const worktreeRow = connector.locator("li.repo", { has: page.locator(".repo-label", { hasText: "· notes" }) });
  const use = worktreeRow.getByRole("button", { name: "Use" });
  if (await use.isVisible().catch(() => false)) await use.click();
  await expect(worktreeRow.getByText("Active")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Close repositories" }).click();
  await expect(page.getByTestId("build-target")).toContainText(`raiker/notes · ${mainHead}`, { timeout: 30_000 });
  expect(git(join(WORKSPACE, REPO), "branch", "--show-current")).toBe("main");
  await capture(page, join(SHOTS, "02-worktree-target.png"), page.getByTestId("build-target"));

  // 2. A real turn writes and commits inside the worktree.
  await workInNewProject(page);
  await chooseModelForTurn(page, /haiku|sonnet|opus|claude/i, "Build composer");
  const decisions = page.locator("section.decisions");
  await page
    .getByLabel("Describe the change")
    .fill(
      `Create the file ${WORKTREE}/NOTES.md containing exactly the line 'Worktree round', using your ` +
        "write_file tool. Then commit it with your git_commit tool, message 'Add notes'. Do not print the file.",
    );
  await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
  for (let step = 0; step < 8; step += 1) {
    await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
    const accept = decisions.getByRole("button", { name: "Accept" }).first();
    // The next proposal's card can render a moment after the stream settles.
    await accept.waitFor({ state: "visible", timeout: 15_000 }).catch(() => {});
    if (!(await accept.isVisible().catch(() => false))) break;
    await accept.click();
    await page.waitForTimeout(1_000);
  }
  await expect
    .poll(() => git(join(WORKSPACE, WORKTREE), "log", "-1", "--format=%s"), { timeout: 120_000 })
    .toBe("Add notes");
  expect(git(join(WORKSPACE, WORKTREE), "log", "-1", "--format=%B")).toMatch(/Raiker-Session: sess_/);
  expect(existsSync(join(WORKSPACE, REPO, "NOTES.md"))).toBe(false);
  expect(git(join(WORKSPACE, REPO), "rev-parse", "--short", "HEAD")).toBe(mainHead);

  const changesTab = page.getByRole("tab", { name: /^Changes/ });
  if (!(await changesTab.isVisible().catch(() => false))) {
    await page.getByRole("button", { name: "Show background work" }).click();
  }
  await page.getByRole("tab", { name: /^Changes/ }).click();
  const commits = page.getByTestId("recent-commits");
  await expect(commits).toBeVisible({ timeout: 30_000 });
  const ours = commits.locator("li", { hasText: "Add notes" });
  await expect(ours).toHaveAttribute("data-provenance", "recorded");
  await expect(ours).toContainText("Made in Raiker");
  await expect(commits.locator("li", { hasText: "init" })).toHaveAttribute("data-provenance", "none");
  await captureElement(commits, join(SHOTS, "03-recent-commits-provenance.png"));

  // 3. Removing the worktree never takes the owner's uncommitted work.
  writeFileSync(join(WORKSPACE, WORKTREE, "wip.txt"), "still thinking\n");
  connector = await openRepositories(page);
  await connector.getByRole("button", { name: /^Remove worktree / }).click();
  await expect(connector.getByText(/has uncommitted changes/)).toBeVisible({ timeout: 30_000 });
  expect(existsSync(join(WORKSPACE, WORKTREE, "wip.txt"))).toBe(true);
  await captureElement(connector, join(SHOTS, "04-remove-refused-dirty.png"));
  rmSync(join(WORKSPACE, WORKTREE, "wip.txt"));
  await connector.getByRole("button", { name: /^Remove worktree / }).click();
  await expect(connector.getByText("Removed the worktree. Its branch raiker/notes and its commits are kept.")).toBeVisible({
    timeout: 30_000,
  });
  expect(existsSync(join(WORKSPACE, WORKTREE))).toBe(false);
  expect(git(join(WORKSPACE, REPO), "log", "-1", "--format=%s", "raiker/notes")).toBe("Add notes");
  await captureElement(connector, join(SHOTS, "05-worktree-removed-branch-kept.png"));
});
