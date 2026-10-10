/**
 * The 2026-10-10 round, first phase: a stale page cannot overwrite newer
 * configuration (§13.2 item 6 for MCP, channels and projects), an MCP tool is
 * accepted as the owner read it, a channel can be paused without losing what
 * arrives (DEC-14 step 10), appearance previews before it is kept (DEC-21
 * Personalisation), a backup carries the files its rows point at (DEC-24
 * step 5), Updates says which recovery point can open this data (DEC-21
 * Updates), the Git credential says when it was last lent (DEC-21 Git
 * credential) and Diagnostics says how each kind of work recovers (DEC-24
 * step 3). The second phase, after a restart, is
 * `round-2026-10-10-restart-live.spec.ts`.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, served
 * with `RAIKER_CHANNEL_INBOUND_SECRET=round-inbound-secret-1010` and
 * `RAIKER_LIVE_WORKSPACE` pointing at it. Harness:
 * `scripts/live_revisions_harness.py`. Anthropic is entered through the Connect
 * dialog from `RAIKER_LIVE_ANTHROPIC_KEY` and never written anywhere.
 */
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { horizontalBleed, settled } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-10-revisions-round");
const REPO = join(import.meta.dirname, "..", "..");
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const INBOUND_SECRET = "round-inbound-secret-1010";

test.describe.configure({ mode: "serial" });
test.use({ timezoneId: "UTC" });

function watchFailures(page: Page): { failures: string[] } {
  const failures: string[] = [];
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 500) {
      failures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  return { failures };
}

function harness(...args: string[]): Record<string, unknown> {
  const out = execFileSync(PYTHON, [join(REPO, "scripts", "live_revisions_harness.py"), WORKSPACE, ...args], {
    encoding: "utf-8",
  });
  return JSON.parse(out.trim()) as Record<string, unknown>;
}

/** A same-origin API call made the way the page makes one. */
async function api(page: Page, method: string, path: string, body?: unknown, headers: Record<string, string> = {}) {
  return page.evaluate(
    async ({ method, path, body, headers }) => {
      const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/)?.[1] ?? "";
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: {
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
          ...(method === "GET" ? {} : { "X-Raiker-CSRF": decodeURIComponent(csrf) }),
          ...headers,
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const json: unknown = await response.json().catch(() => null);
      return { status: response.status, json };
    },
    { method, path, body, headers },
  );
}

async function open(page: Page, hash: string): Promise<void> {
  // Navigating to the hash the page is already on is no navigation at all, so
  // nothing would be read again; reload instead.
  if (page.url() === `${BASE}/${hash}`) await page.reload();
  else await page.goto(`${BASE}/${hash}`);
  await settled(page);
  await page.waitForTimeout(800);
}

/**
 * The round was given an identity-linked Anthropic key (`sk-ant-usr-`), which
 * acts only inside one Anthropic workspace and is refused without that
 * workspace's ID — which the key alone cannot look up. Entered through Connect
 * the way an owner does, the evidence is that Raiker says so, names the remedy
 * and does not call the key bad. A real turn waits on the workspace ID.
 */
test("an identity-linked Anthropic key entered through Models is explained, not called bad", async ({ page }) => {
  test.setTimeout(300_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await useAnthropic(page).catch(() => undefined);
  await expect(page.getByText(/identity-linked, so it acts inside one workspace/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/The key you pasted is fine/)).toBeVisible();
  await capture(page, join(SHOTS, "01-anthropic-key-needs-workspace.png"));
  await page.keyboard.press("Escape");
  expect(seen.failures).toEqual([]);
});

test("appearance previews before it is kept and Discard puts it back", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await open(page, "#/settings?tab=personalisation");
  await expect(page.getByText(/never its instructions, its personality or what it may do/)).toBeVisible();
  await page.getByText("Layout & type").click();
  await page.getByRole("radio", { name: /Compact/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-spacing", "compact");
  await page.getByRole("radio", { name: /Dark/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByText(/you have unsaved changes/i)).toBeVisible();
  await capture(page, join(SHOTS, "02-appearance-previewed.png"));
  await page.getByRole("button", { name: /discard/i }).click();
  await expect(page.locator("html")).not.toHaveAttribute("data-spacing", "compact");
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", "dark");
  const stored = await page.evaluate(() => window.localStorage.getItem("raiker.theme"));
  expect(stored).toBeNull();
  await capture(page, join(SHOTS, "03-appearance-discarded.png"));
  expect(seen.failures).toEqual([]);
});

test("a stale Messaging tab cannot undo a sender removed in another, and Pause keeps what arrives", async ({
  page,
  context,
}) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  const paired = await api(page, "POST", "/api/channels/pairings", {
    connector_id: "channel.webhooks",
    display_name: "Ops desk",
    senders: ["ops", "oncall"],
  });
  expect(paired.status).toBe(200);
  const pairingId = (paired.json as { pairing_id: string }).pairing_id;
  expect((await api(page, "PUT", `/api/channels/pairings/${pairingId}/enabled`, { enabled: true })).status).toBe(200);

  await open(page, "#/messaging");
  const other = await context.newPage();
  await other.goto(`${BASE}/#/messaging`);
  await settled(other);
  await other.waitForTimeout(800);
  // The other tab removes a sender.
  await other.getByRole("button", { name: "Senders" }).click();
  await other.getByLabel("Allowed senders").fill("ops");
  await other.getByRole("button", { name: "Save senders" }).click();
  await expect(other.getByText(/accepts 1 sender/)).toBeVisible({ timeout: 15_000 });

  // This tab still shows two senders and saves the old list back.
  await page.getByRole("button", { name: "Senders" }).click();
  await expect(page.getByLabel("Allowed senders")).toHaveValue("oncall, ops");
  await page.getByRole("button", { name: "Save senders" }).click();
  await expect(page.getByText(/changed somewhere else since this page loaded, so nothing was changed/)).toBeVisible({
    timeout: 15_000,
  });
  await capture(page, join(SHOTS, "04-channel-stale-tab-refused.png"));
  const view = await api(page, "GET", "/api/channels");
  const profile = (view.json as { profiles: { connector_id: string; senders: string[] }[] }).profiles.find(
    (row) => row.connector_id === "channel.webhooks",
  );
  expect(profile?.senders).toEqual(["ops"]);
  await other.close();

  // Pause: an allowlisted message is kept and starts nothing.
  await open(page, "#/messaging");
  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByText(/is paused\. Messages are kept; nothing starts and nothing is sent/)).toBeVisible({
    timeout: 15_000,
  });
  const inbound = await page.request.post(`${BASE}/api/channels/channel.webhooks/inbound`, {
    data: { sender_id: "ops", text: "Please deploy the release now." },
    headers: { "X-Raiker-Channel-Secret": INBOUND_SECRET },
  });
  expect(inbound.status()).toBe(200);
  const held = (await inbound.json()) as { routed: boolean; reason_code: string };
  expect(held.routed).toBe(false);
  expect(held.reason_code).toBe("channel_paused");
  // Same route, so a reload rather than a hash navigation the page would not refetch on.
  await page.reload();
  await settled(page);
  await expect(page.getByText("Paused", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Kept while paused — nothing started").first()).toBeVisible();
  await capture(page, join(SHOTS, "05-channel-paused-kept.png"), page.getByTestId("channel-profiles"));
  expect(seen.failures).toEqual([]);
});

test("a stale project editor keeps its text and saves nothing over newer instructions", async ({ page, context }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  const created = await api(page, "POST", "/api/projects", { name: "Harbour report" });
  expect(created.status).toBe(200);
  await open(page, "#/projects");
  await page.getByRole("button", { name: /open project harbour report/i }).click();
  const instructions = page.getByLabel("Project instructions");
  await expect(instructions).toBeVisible();

  const other = await context.newPage();
  await other.goto(`${BASE}/#/projects`);
  await settled(other);
  await other.getByRole("button", { name: /open project harbour report/i }).click();
  await other.getByLabel("Project instructions").fill("Cite the tide tables for every claim.");
  await other.getByRole("button", { name: "Save context" }).click();
  await expect(other.getByRole("button", { name: "Save context" })).toBeEnabled();
  await other.waitForTimeout(800);
  await other.close();

  await instructions.fill("Keep it short.");
  await page.getByRole("button", { name: "Save context" }).click();
  await expect(page.getByText(/changed somewhere else since this page opened it/)).toBeVisible({ timeout: 15_000 });
  await expect(instructions).toHaveValue("Keep it short.");
  await capture(page, join(SHOTS, "06-project-stale-editor-refused.png"));
  const projectId = (created.json as { project_id: string }).project_id;
  const detail = await api(page, "GET", `/api/projects/${projectId}`);
  expect((detail.json as { context: { instructions: string } }).context.instructions).toBe(
    "Cite the tide tables for every claim.",
  );
  expect(seen.failures).toEqual([]);
});

test("an MCP tool is accepted only as the owner read it, and a stale rename is refused", async ({ page, context }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  // A profile as the builder stores one; what is under test is accepting and renaming it.
  const serverId = String(harness("mcp-create", "notes").server_id);
  harness("mcp-enumerate", serverId, "first");
  harness("mcp-enumerate", serverId, "grown");
  await open(page, "#/extensions?tab=mcp");
  await expect(page.getByText("The server says: “Delete one draft.”")).toBeVisible({ timeout: 15_000 });

  // The server rewords the tool after the card was drawn.
  harness("mcp-enumerate", serverId, "reworded");
  await page.getByRole("button", { name: "Accept purge" }).click();
  await expect(page.getByText(/changed how it describes that tool since this page showed it, so nothing was accepted/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText("The server says: “Delete every note you have.”")).toBeVisible();
  await capture(page, join(SHOTS, "07-mcp-tool-changed-not-accepted.png"));

  // A rename from a tab that still shows the old name.
  const other = await context.newPage();
  await other.goto(`${BASE}/#/extensions?tab=mcp`);
  await settled(other);
  await other.getByRole("button", { name: "Rename" }).click();
  await other.getByLabel("New server name").fill("notebook");
  await other.getByRole("button", { name: "Save", exact: true }).click();
  await expect(other.getByText("notebook").first()).toBeVisible({ timeout: 15_000 });
  await other.close();
  await page.getByRole("button", { name: "Rename" }).click();
  await page.getByLabel("New server name").fill("scratch");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText(/was renamed somewhere else since this page loaded, so nothing was changed/)).toBeVisible({
    timeout: 15_000,
  });
  await capture(page, join(SHOTS, "08-mcp-stale-rename-refused.png"));
  expect(seen.failures).toEqual([]);
});

test("a backup carries the checkpoint files and uploads its rows point at", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  harness("seed-files");
  await open(page, "#/settings?tab=account");
  await page.getByRole("button", { name: "Back up now" }).click();
  await expect(page.getByText(/Backed up and verified/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/1 checkpoint file · 1 upload/)).toBeVisible();
  await expect(page.getByText("Not included: the audit log, folders you attached to projects", { exact: false })).toBeVisible();
  await capture(page, join(SHOTS, "09-backup-carries-files.png"), page.getByTestId("backups-card"));
  expect(seen.failures).toEqual([]);
});

test("Updates says which recovery point can open this workspace's data", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  harness("recovery-points");
  await open(page, "#/settings?tab=updates");
  const points = page.getByTestId("recovery-points");
  await expect(points).toContainText("0.9.2 — can open this workspace's data");
  await expect(points).toContainText("0.8.0 — would refuse this workspace's data");
  await capture(page, join(SHOTS, "10-updates-recovery-compatibility.png"));
  expect(seen.failures).toEqual([]);
});

test("the Git credential says when it was last lent and for what", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await open(page, "#/settings?tab=git-credential");
  // A fresh workspace reads "Never lent" (the first run of this round, and the
  // unit test); a resumed round has already lent it once.
  await expect(page.getByTestId("git-last-use")).toHaveText(/Never lent to a git command yet\.|Last lent/);
  const field = page.getByLabel("GitHub token");
  if (await field.isVisible().catch(() => false)) {
    await field.fill("round-1010-placeholder-not-a-real-token");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await page.waitForTimeout(1_000);
  }
  harness("git-lend");
  await open(page, "#/settings?tab=git-credential");
  await expect(page.getByTestId("git-last-use")).toContainText(/Last lent[\s\S]*to push a branch,\s+under a one-command approval/);
  await capture(page, join(SHOTS, "11-git-credential-last-lent.png"));
  expect(seen.failures).toEqual([]);
});

test("Diagnostics says what each kind of work does after a restart; a run is left interrupted", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await open(page, "#/observe");
  await page.getByText("Runtime health, in detail").click();
  const card = page.getByTestId("recovery-matrix");
  await expect(card).toContainText("Tasks and routines");
  await card.getByText("Tasks and routines").click();
  await expect(card).toContainText("Never run again on its own");
  await capture(page, join(SHOTS, "12-diagnostics-recovery-matrix.png"), card);
  // Phase two restarts the host over this: a routine claimed and never finished.
  const interrupted = harness("interrupt-task") as { task_id: string; status: string };
  expect(interrupted.status).toBe("running");
  execFileSync("sh", ["-c", `echo ${interrupted.task_id} > ${join(WORKSPACE, "..", "interrupted-task.txt")}`]);
  expect(seen.failures).toEqual([]);
});

test("Messaging at phone width in dark reads Paused without bleeding sideways", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark" });
  await signInAsOwner(page, BASE);
  await open(page, "#/messaging");
  await expect(page.getByText("Paused", { exact: true }).first()).toBeVisible();
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "13-messaging-390-dark.png"));
});
