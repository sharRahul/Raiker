/**
 * BUG-67 and BUG-66 against a running `raiker-web` — the agent can publish what
 * it committed, in the repository the owner picked.
 *
 * B11 stopped one step short of the motion every product this is measured
 * against performs in one go: make the change, commit it, open the PR. The
 * branch existed only on this machine, so `github_write` had no head to point
 * at. And every git tool ran against the workspace root, so a repository the
 * owner connected as a sub-folder was not the one the agent was working in.
 *
 * This spec drives both through the product: the owner's two separate switches,
 * the sub-folder repository the tools now read, the decision that names the
 * remote and the commits before it is taken, the push that really happens, the
 * honest refusal when there is nothing left to send, and the off switch.
 *
 * Prerequisites:
 *   1. `raiker-web --workspace <ws> --port 8765 --no-browser` where `<ws>` is a
 *      git repository with an HTTPS GitHub remote it may push to, holding a
 *      second git repository at `projects/service`, and
 *        RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com
 *        RAIKER_CONNECTOR_EGRESS_ALLOWLIST=github.com
 *        RAIKER_GITHUB_TOKEN=<a token that may push to that remote>
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (added through the UI below)
 *   3. `RAIKER_LIVE_WORKSPACE` pointing at that same workspace, so the spec can
 *      read git's own answer rather than the app's account of it.
 */
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { appendFileSync } from "node:fs";
import { join } from "node:path";
import { useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "..", "docs", "plans", "screenshots", "working");
const PASSWORD = "Git-push-path-1!";
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const MODEL = "claude-haiku-4-5-20251001";
const SERVICE = "projects/service";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

function git(...args: string[]): string {
  return execFileSync("git", ["-C", WORKSPACE, ...args], { encoding: "utf8" }).trim();
}

function branchName(): string {
  return git("rev-parse", "--abbrev-ref", "HEAD");
}

function remoteHead(): string {
  const line = git("ls-remote", "--heads", "origin", branchName());
  return line.split(/\s+/)[0] ?? "";
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
  if (!(await control.isVisible().catch(() => false))) return;
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

async function openRepositories() {
  // The panel is a toggle, so clicking it blind closes one that is already open.
  const connector = page.getByRole("region", { name: "Repositories" });
  if (!(await connector.isVisible().catch(() => false))) {
    await page.locator("button.repo-button").click();
  }
  await expect(connector).toBeVisible({ timeout: 30_000 });
  return connector;
}

async function clearPendingApprovals() {
  // A previous run that stopped mid-scenario can leave a parked approval behind,
  // and a session that resumes it never reaches the call this test is about.
  // Denying is an ordinary owner action, so the cleanup uses the same control.
  await page.goto(`${BASE}/#/approvals`);
  for (let i = 0; i < 10; i += 1) {
    const review = page.getByRole("button", { name: "Review" }).first();
    if (!(await review.isVisible().catch(() => false))) return;
    await review.click();
    const deny = page.getByRole("button", { name: "Deny", exact: true });
    if (!(await deny.isVisible().catch(() => false))) return;
    await deny.click();
    await page.goto(`${BASE}/#/approvals`);
  }
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
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
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

test("Git push is its own owner control, beside Git writes and not inside it", async () => {
  test.setTimeout(240_000);
  // BUG-67's whole argument: an owner who lets the agent commit has not thereby
  // let it publish. Two switches, and the push one says what it additionally
  // needs before it can reach anything.
  await setCapability("Approval execution relay", "Turn on", "approvals should do what they say");
  await setCapability("Git writes", "Turn on", "let an approved commit really be recorded");
  await setCapability("Git push", "Turn on", "let an approved push really be sent");

  const card = await openCapability("Git push");
  await expect(card).toContainText(/Send an approved branch to its remote with your own credential/i);
  await expect(card).toContainText(/connector egress allowlist/i);
  await expect(card).toContainText(/never forces or deletes a branch/i);
  await page.screenshot({ path: join(SHOTS, "bug67-git-push-capability.png"), fullPage: true });
});

test("the git tools read the repository connected as a sub-folder", async () => {
  test.setTimeout(300_000);
  // BUG-66 — Build's connection surface promised the agent was working in the
  // repository the owner picked, and for every git tool it was not: they all ran
  // against the workspace root.
  await page.goto(`${BASE}/#/build`);
  const connector = await openRepositories();
  if (!(await connector.getByText(SERVICE).isVisible().catch(() => false))) {
    await connector.getByLabel("Folder inside this workspace").fill(SERVICE);
    await connector.getByRole("button", { name: /^Connect/ }).click();
  }
  const row = connector.locator("li.repo").filter({ hasText: SERVICE });
  await expect(row).toBeVisible({ timeout: 30_000 });
  const use = row.getByRole("button", { name: "Use" });
  if (await use.isVisible().catch(() => false)) await use.click();
  await expect(row.getByText("Active")).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: join(SHOTS, "bug66-subfolder-repository.png"), fullPage: true });

  const composer = page.getByPlaceholder(/Describe the change in service…/);
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.fill(
    "Call git_log once with limit 3, then tell me exactly what the tool returned.",
  );
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
  // The sub-folder repository's own history, not the workspace's.
  await expect(page.getByRole("main")).toContainText(/initial service commit/i, {
    timeout: 30_000,
  });
  await page.screenshot({ path: join(SHOTS, "bug66-subfolder-git-log.png"), fullPage: true });
});

test("clearing the selection puts the tools back on the workspace repository", async () => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/build`);
  const connector = await openRepositories();
  const clear = connector.getByRole("button", { name: "Clear" });
  if (await clear.isVisible().catch(() => false)) await clear.click();
  await expect(connector.getByRole("button", { name: "Use" }).first()).toBeVisible({
    timeout: 30_000,
  });
});

test("a push approval names the remote, the branch and the commits it would send", async () => {
  test.setTimeout(420_000);
  // Something to publish, committed through the governed path B11 shipped.
  appendFileSync(join(WORKSPACE, "NOTICE"), "\nBUG-67 verification line.\n");
  await newChat();
  await ask(
    'Call git_commit once with the message "Record the push verification line" and no ' +
      "paths, then tell me exactly what the tool returned.",
  );
  await openNewestApproval(/Git commit/i);
  await page.getByRole("button", { name: "Approve and execute once" }).click();
  await expect(page.locator(".notice-ok").first()).toContainText(/Executed once/i, {
    timeout: 60_000,
  });
  expect(git("log", "-1", "--pretty=%s")).toBe("Record the push verification line");

  await newChat();
  await ask("Call git_push once with no arguments, then tell me exactly what the tool returned.");
  await openNewestApproval(/Git push/i);
  const detail = page.getByRole("main");
  await expect(detail).toContainText(/Proposed repository change/i);
  await expect(detail).toContainText(/remote\s+origin \(github\.com\)/i);
  await expect(detail).toContainText(new RegExp(`branch\\s+${branchName().replace("/", "\\/")}`));
  await expect(detail).toContainText(/sending\s+1 commit\(s\)/i);
  await expect(detail).toContainText(/Record the push verification line/);
  // The sentence a push gets is not the sentence a commit gets: this one leaves
  // the machine and git cannot take it back.
  await expect(detail).toContainText(/sends the commits above to the remote shown, once/i);
  await expect(detail).toContainText(/undo it on the remote/i);
  await expect(detail).not.toContainText(/does NOT execute the action/i);
  await page.screenshot({ path: join(SHOTS, "bug67-push-approval.png"), fullPage: true });
});

test("approving it really publishes the branch", async () => {
  test.setTimeout(300_000);
  const before = remoteHead();
  await page.getByRole("button", { name: "Approve and execute once" }).click();
  await expect(page.locator(".notice-ok").first()).toContainText(/Executed once/i, {
    timeout: 120_000,
  });
  await page.screenshot({ path: join(SHOTS, "bug67-push-executed.png"), fullPage: true });

  // The product's claim, checked against the remote rather than against the
  // product: the branch GitHub holds is now the commit this machine holds.
  const local = git("rev-parse", "HEAD");
  expect(remoteHead()).toBe(local);
  expect(remoteHead()).not.toBe(before);
});

test("with nothing left to send, the tool refuses instead of asking for a decision", async () => {
  test.setTimeout(300_000);
  // Approving a no-op is noise the owner should never be asked for, and the
  // refusal is computed from what this machine knows rather than from a
  // network call the owner has not approved.
  await clearPendingApprovals();
  await newChat();
  await ask("Call git_push once with no arguments, then tell me exactly what the tool returned.");
  await expect(page.getByRole("main")).toContainText(/nothing_to_push/i, { timeout: 60_000 });
  await page.screenshot({ path: join(SHOTS, "bug67-nothing-to-push.png"), fullPage: true });
});

test("the owner's off switch still wins, and says so before the decision", async () => {
  test.setTimeout(420_000);
  // Security posture: the capability is the owner's to hold. Turning it off must
  // return the honest record-only answer, stated before they decide.
  await setCapability("Git push", "Turn off", "checking the off switch still holds");
  appendFileSync(join(WORKSPACE, "NOTICE"), "\nA line that must not reach the remote.\n");
  git("-c", "user.name=Raiker Test", "-c", "user.email=t@example.com", "commit", "-am", "Local only");
  const head = git("rev-parse", "HEAD");

  await newChat();
  await ask("Call git_push once with no arguments, then tell me exactly what the tool returned.");
  await openNewestApproval(/Git push/i);
  await expect(page.getByRole("main")).toContainText(/does NOT execute the action/i, {
    timeout: 30_000,
  });
  await expect(page.getByRole("button", { name: "Approve (record only)" })).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "bug67-gate-off-record-only.png"), fullPage: true });

  await page.getByRole("button", { name: "Approve (record only)" }).click();
  // Nothing left the machine: the gate is the owner's, and it held.
  expect(remoteHead()).not.toBe(head);
});
