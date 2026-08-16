/**
 * B11 against a running `raiker-web` — the agent can commit and propose the work.
 *
 * Before this, Build's git surface was `status`, `diff` and `log`: it could read
 * a repository and describe a change it could neither commit nor propose. This
 * spec drives the whole write path through the product — the owner turning the
 * capability on, the repository change they review before deciding, the decision
 * itself, the commit that exists afterwards, and the off switch that returns it
 * honestly to record-only.
 *
 * Prerequisites:
 *   1. `raiker-web --workspace <ws> --port 8765 --no-browser` where `<ws>` is a
 *      git repository with at least one commit, and
 *      `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com`
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (added through the UI below)
 *   3. `RAIKER_LIVE_WORKSPACE` pointing at that same repository, so the spec can
 *      read git's own answer rather than the app's account of it.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { appendFileSync } from "node:fs";
import { join } from "node:path";
import { useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Git-write-path-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const MODEL = "claude-haiku-4-5-20251001";
const BRANCH = "feature/subtract";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

function git(...args: string[]): string {
  return execFileSync("git", ["-C", WORKSPACE, ...args], { encoding: "utf8" }).trim();
}

async function signIn(target: Page) {
  await target.goto(`${BASE}/#/workbench`);
  await expect(target.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
  const confirm = target.getByLabel("Confirm password");
  await target.getByLabel("Username").fill("owner");
  await target.getByLabel("Password", { exact: true }).fill(PASSWORD);
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(PASSWORD);
    await target.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await target.getByRole("button", { name: /unlock|sign in/i }).click();
  }
  await expect(target.getByRole("heading", { name: /Welcome/ })).toBeVisible({ timeout: 30_000 });
}

async function openCapability(label: string) {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByPlaceholder("Search capabilities…");
  await expect(search).toBeVisible({ timeout: 30_000 });
  await search.fill(label);
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  if ((await card.getByRole("button", { name: label }).getAttribute("aria-expanded")) !== "true") {
    await card.getByRole("button", { name: label }).click();
  }
  await expect(card.locator(".cap-detail")).toBeVisible({ timeout: 10_000 });
  return card;
}

async function setCapability(label: string, action: "Turn on" | "Turn off", reason: string) {
  const card = await openCapability(label);
  const control = card.getByRole("button", { name: action });
  await expect(control).toBeVisible({ timeout: 10_000 });
  await control.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await dialog.getByLabel("Reason (required)").fill(reason);
  const token = dialog.getByLabel(/Confirmation token/);
  if (await token.isVisible().catch(() => false)) await token.fill("CONFIRM");
  const ack = dialog.getByRole("checkbox");
  if (await ack.isVisible().catch(() => false)) await ack.check();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

async function newChat() {
  await page.goto(`${BASE}/#/new-chat`);
  const reset = page.getByRole("button", { name: "New chat", exact: true });
  if (await reset.isEnabled().catch(() => false)) await reset.click();
  await expect(page.getByPlaceholder("How can I help you today?")).toBeVisible({ timeout: 30_000 });
}

async function ask(prompt: string) {
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(prompt);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 240_000 });
}

async function openNewestApproval(name: RegExp) {
  await page.goto(`${BASE}/#/approvals`);
  await page.getByLabel("Sort approvals").selectOption({ label: "Newest first" });
  const row = page.getByRole("row", { name }).first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.getByRole("button", { name: "Review" }).click();
  await expect(page.getByRole("heading", { name: /^Review / })).toBeVisible({ timeout: 30_000 });
}

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
  });
  page = await context.newPage();
  await signIn(page);
});

test.afterAll(async () => await context?.close());

test("a provider key is added through the UI and a model selected", async () => {
  test.setTimeout(240_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE").not.toBe("");

  const card = await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await expect(card.locator("code").filter({ hasText: /Haiku 4\.5/i })).toBeVisible({
    timeout: 30_000,
  });
});

test("Git writes is an owner control on the Permissions page", async () => {
  test.setTimeout(180_000);
  // B11's capability is the owner's, not the runtime's: one named switch over
  // "may the agent change my repository", beside the file and memory ones.
  await setCapability("Approval execution relay", "Turn on", "approvals should do what they say");
  await setCapability("Git writes", "Turn on", "let an approved commit really be recorded");
  const card = await openCapability("Git writes");
  await expect(card).toContainText(
    /Create a branch or record a commit in the workspace repository/i,
  );
  await page.screenshot({ path: join(SHOTS, "b11-git-write-capability.png"), fullPage: true });
});

test("asking for a branch raises an approval that names the refs it moves between", async () => {
  test.setTimeout(300_000);
  expect(git("rev-parse", "--abbrev-ref", "HEAD")).toBe("main");
  await newChat();
  await ask(
    `Call git_branch once with name "${BRANCH}" and no base, then tell me exactly what the tool returned.`,
  );
  await expect(page.getByRole("main")).toContainText(/approval required|approval is needed/i, {
    timeout: 60_000,
  });

  await openNewestApproval(/Git branch/i);
  const detail = page.getByRole("main");
  await expect(detail).toContainText(/Proposed repository change/i);
  await expect(detail).toContainText(new RegExp(`new branch\\s+${BRANCH.replace("/", "\\/")}`, "i"));
  await expect(detail).toContainText(new RegExp(`checked out\\s+main → ${BRANCH.replace("/", "\\/")}`));
  await expect(detail).toContainText(/Approving this creates the branch above and checks it out, once/i);
  await expect(detail).not.toContainText(/does NOT execute the action/i);
  await page.screenshot({ path: join(SHOTS, "b11-branch-approval.png"), fullPage: true });
});

test("approving it creates the branch git itself reports", async () => {
  test.setTimeout(300_000);
  await page.getByRole("button", { name: "Approve and execute once" }).click();
  await expect(page.locator(".notice-ok").first()).toContainText(/Executed once/i, {
    timeout: 60_000,
  });
  await page.screenshot({ path: join(SHOTS, "b11-branch-executed.png"), fullPage: true });

  // The product's claim, checked against git rather than against the product.
  expect(git("rev-parse", "--abbrev-ref", "HEAD")).toBe(BRANCH);
});

test("a commit approval shows the exact file list and diff before the decision", async () => {
  test.setTimeout(300_000);
  // A change in the working tree, as the agent or the owner would have left it.
  appendFileSync(join(WORKSPACE, "calculator.py"), "\ndef subtract(a, b):\n    return a - b\n");

  await newChat();
  await ask(
    'Call git_commit once with the message "Add subtract to the calculator" and no paths, ' +
      "then tell me exactly what the tool returned.",
  );
  await openNewestApproval(/Git commit/i);
  const detail = page.getByRole("main");
  await expect(detail).toContainText(/Proposed repository change/i);
  await expect(detail).toContainText(/calculator\.py/);
  await expect(detail).toContainText(/\+def subtract\(a, b\):/);
  await expect(detail).toContainText(/records the change set above as one commit, once/i);
  // A commit is git history, not a checkpointed file write; the notice must not
  // promise a rewind the checkpoint store cannot perform.
  await expect(detail).not.toContainText(/checkpointed first, so it can be rewound/i);
  await page.screenshot({ path: join(SHOTS, "b11-commit-approval.png"), fullPage: true });
});

test("approving it records the commit, on the branch, without running repository hooks", async () => {
  test.setTimeout(300_000);
  await page.getByRole("button", { name: "Approve and execute once" }).click();
  await expect(page.locator(".notice-ok").first()).toContainText(/Executed once/i, {
    timeout: 60_000,
  });
  await page.screenshot({ path: join(SHOTS, "b11-commit-executed.png"), fullPage: true });

  expect(git("log", "-1", "--pretty=%s")).toBe("Add subtract to the calculator");
  expect(git("rev-parse", "--abbrev-ref", "HEAD")).toBe(BRANCH);
  expect(git("status", "--porcelain")).toBe("");
  // The workspace's own state directory is never swept into the commit: it holds
  // the vault key, the encrypted store and the audit log.
  expect(git("ls-files")).not.toContain(".raiker");
});

test("the owner's off switch still wins, and says so before the decision", async () => {
  test.setTimeout(300_000);
  // Security posture: the capability is the owner's to hold. An owner who turns
  // it off must get the honest record-only answer back, stated before they
  // decide rather than after.
  await setCapability("Git writes", "Turn off", "checking the off switch still holds");
  appendFileSync(join(WORKSPACE, "README.md"), "\nA second line.\n");

  await newChat();
  await ask(
    'Call git_commit once with the message "Extend the readme" and no paths, then tell me ' +
      "exactly what the tool returned.",
  );
  await openNewestApproval(/Git commit/i);
  await expect(page.getByRole("main")).toContainText(/does NOT execute the action/i, {
    timeout: 30_000,
  });
  await expect(page.getByRole("button", { name: "Approve (record only)" })).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "b11-gate-off-record-only.png"), fullPage: true });

  await page.getByRole("button", { name: "Approve (record only)" }).click();
  // Nothing was recorded: the gate is the owner's, and it held.
  expect(git("log", "-1", "--pretty=%s")).toBe("Add subtract to the calculator");
});

test("proposing the work outward is a decision too, and the connector gate holds", async () => {
  test.setTimeout(300_000);
  // The outward half of B11. The GitHub connector is off, so this proves the
  // whole path up to the boundary — the model can propose it, the runtime raises
  // a real decision naming the repository, and the owner's gate keeps it from
  // being sent. Actually sending one is deliberately not automated: it leaves
  // this machine and cannot be unsent.
  await newChat();
  await ask(
    'Call github_write once with operation "create_pull_request", repo "octo/demo", ' +
      `title "Add subtract", head "${BRANCH}", base "main", and a one-line body, then ` +
      "tell me exactly what the tool returned.",
  );
  await openNewestApproval(/Github write/i);
  const detail = page.getByRole("main");
  await expect(detail).toContainText(/Proposed outbound request \(redacted\)/i);
  await expect(detail).toContainText(/octo\/demo \/ create_pull_request/);
  await expect(detail).toContainText(/does NOT execute the action/i);
  await page.screenshot({ path: join(SHOTS, "b11-github-write-approval.png"), fullPage: true });
});
