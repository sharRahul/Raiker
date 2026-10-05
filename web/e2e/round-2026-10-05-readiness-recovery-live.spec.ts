/**
 * The 2026-10-05 (second) round: ten more decision-record steps from the
 * release-readiness review, driven against a running `raiker-web`.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, served
 * with `RAIKER_LIVE_WORKSPACE` pointing at it and
 * `RAIKER_CHANNEL_INBOUND_SECRET=live-round-secret`. The harness
 * (`scripts/live_readiness_harness.py`) files the starting states; every
 * outcome is the running host's. Anthropic is entered through the Connect
 * dialog from `RAIKER_LIVE_ANTHROPIC_KEY` and never written anywhere. The last
 * scenario deletes the round's account.
 */
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { horizontalBleed, settled } from "./destinations";
import { chooseModelForTurn, enableCapability, OWNER_CREDENTIALS, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_MODEL, LIVE_BASE, sendTurn, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-05-readiness-recovery-round");
const REPO = join(import.meta.dirname, "..", "..");
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const CHANNEL_SECRET = process.env.RAIKER_LIVE_CHANNEL_SECRET ?? "live-round-secret";

test.describe.configure({ mode: "serial" });

function watchFailures(page: Page): { failures: string[]; consoleErrors: string[] } {
  const failures: string[] = [];
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 500) {
      failures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  return { failures, consoleErrors };
}

function harness(...args: string[]): Record<string, unknown> {
  const out = execFileSync(PYTHON, [join(REPO, "scripts", "live_readiness_harness.py"), WORKSPACE, ...args], {
    encoding: "utf-8",
  });
  return JSON.parse(out.trim()) as Record<string, unknown>;
}

test("a real Anthropic answer, so the account has something to count", async ({ page }) => {
  test.setTimeout(300_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await useAnthropic(page);
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  await chooseModelForTurn(page, new RegExp(ANTHROPIC_MODEL.includes("haiku") ? "Haiku" : ".", "i"));
  await sendTurn(page, "Reply with exactly these words and nothing else: recovery round answered");
  await expect(page.getByText(/recovery round answered/i)).toHaveCount(2, { timeout: 120_000 });
  await expect(
    page.getByRole("group", { name: "Message composer" }).getByRole("button", { name: /^Send/ }),
  ).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "01-chat-real-answer.png"));
  expect(seen.failures).toEqual([]);
});

test("Account shows the internal account ID folded away, and the deletion's real counts", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=account`);
  await settled(page);

  const support = page.getByTestId("account-support-details");
  await support.locator("summary").click();
  await expect(page.getByTestId("account-principal-id")).toContainText(/^principal_/);
  await expect(support).toContainText("It is not your name");
  await capture(page, join(SHOTS, "02-account-support-details.png"), support);

  await page.getByRole("button", { name: "Delete my account" }).click();
  const impact = page.getByTestId("account-deletion-impact");
  await expect(impact).toContainText("This removes");
  await expect(impact.locator("li").first()).toHaveText(/^\d+ conversations?$/);
  await expect(impact).toContainText("Folders you attached to a project stay on disk");
  await page.getByLabel("Confirm your password").fill(OWNER_CREDENTIALS.password);
  await page.getByLabel(/Type your username/).fill(OWNER_CREDENTIALS.user.toLowerCase() + "x");
  await expect(page.getByRole("button", { name: "Permanently delete" })).toBeDisabled();
  await capture(page, join(SHOTS, "03-account-deletion-impact.png"), page.locator("section.danger-zone"));
  await page.getByRole("button", { name: "Cancel" }).click();
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("stopping a parent stops every task it delegated, and resuming nothing it did not", async ({ page }) => {
  test.setTimeout(180_000);
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE").not.toBe("");
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  const tree = harness("delegation") as { parent: string; child: string; grandchild: string };

  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  const parent = page.locator("article.task").filter({ hasText: "Release notes review" }).first();
  await expect(parent).toBeVisible({ timeout: 30_000 });
  await parent.getByRole("button", { name: /^Stop/ }).click();
  await expect.poll(() => harness("show", tree.grandchild).status, { timeout: 30_000 }).toBe("cancelled");
  expect(harness("show", tree.child).status).toBe("cancelled");
  expect(harness("show", tree.parent).status).toBe("cancelled");
  expect(String(harness("show", tree.grandchild).summary)).toContain("Delegated by a task the owner stopped");
  await page.reload();
  await settled(page);
  await capture(page, join(SHOTS, "04-tasks-parent-and-delegated-work-stopped.png"));
  expect(seen.failures).toEqual([]);
});

test("a finished background task whose notice failed stays completed and says Delivery failed", async ({ page }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  const done = harness("undelivered");
  expect(done.status).toBe("completed");
  expect(done.delivery_state).toBe("failed");

  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  const row = page.locator(".history-row").filter({ hasText: "Weekly dependency digest" });
  await expect(row).toBeVisible({ timeout: 30_000 });
  await expect(row.getByTestId("task-delivery-failed")).toContainText("Delivery failed.");
  await expect(row.getByTestId("task-delivery-failed")).toContainText("desktop notification command failed");
  await capture(page, join(SHOTS, "05-tasks-delivery-failed.png"), row);
  expect(seen.failures).toEqual([]);
});

test("a damaged search index is named, the data said to be safe, and a rebuild repairs it", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  expect(harness("damage-index").damaged).toEqual(["conversation_fts"]);

  await page.goto(`${BASE}/#/observe?tab=overview`);
  await settled(page);
  // Diagnostics is the fold under the overview, closed on a healthy install.
  await page.locator("details.specialist summary").filter({ hasText: "Runtime health, in detail" }).click();
  const notice = page.getByTestId("damaged-text-indexes");
  await expect(notice).toContainText("Conversation search index is damaged", { timeout: 30_000 });
  await expect(notice).toContainText("not affected");
  const card = page.locator("section.card").filter({ hasText: "Memory integrity" });
  await capture(page, join(SHOTS, "06-diagnostics-damaged-index.png"), card);

  await card.getByRole("button", { name: "Rebuild search indexes" }).click();
  await expect(card.getByText(/every search index passes its check/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("damaged-text-indexes")).toHaveCount(0);
  await capture(page, join(SHOTS, "07-diagnostics-index-rebuilt.png"), card);
  expect(seen.failures).toEqual([]);
});

test("Resume re-runs an MCP server's test: one that passes is active, one that fails stays paused", async ({ page }) => {
  test.setTimeout(300_000);
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE").not.toBe("");
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await enableCapability(page, BASE, "MCP builder", "Live round: MCP resume check");
  await enableCapability(page, BASE, "MCP connector", "Live round: MCP resume check");
  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  await settled(page);
  await page.getByText("Developer example — generate a local sample server").click();
  await page.getByLabel("Server name").fill("ledger");
  await page.getByRole("button", { name: "Generate example server" }).click();
  const card = page.locator("li.card").filter({ hasText: "ledger" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await card.getByRole("button", { name: "Test" }).click();
  await expect(page.getByText(/ledger: connected/)).toBeVisible({ timeout: 60_000 });

  await card.getByRole("button", { name: "Stop" }).click();
  await expect(card).toContainText("Paused", { timeout: 30_000 });
  await card.getByRole("button", { name: "Resume" }).click();
  await expect(page.getByText("ledger: resumed after a passing connection test.")).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "08-mcp-resume-passed.png"), card);

  // The server breaks while paused: its program now exits before the handshake.
  const folder = join(WORKSPACE, ".raiker", "mcp", "servers");
  const file = join(folder, readdirSync(folder).find((name) => name.includes("ledger")) ?? "");
  writeFileSync(file, "import sys\nsys.exit(3)\n" + readFileSync(file, "utf-8"));
  await card.getByRole("button", { name: "Stop" }).click();
  await expect(card).toContainText("Paused", { timeout: 30_000 });
  await card.getByRole("button", { name: "Resume" }).click();
  await expect(page.getByText(/ledger did not pass its connection test, so it stays paused/)).toBeVisible({
    timeout: 60_000,
  });
  await expect(card).toContainText("Resume check did not pass");
  await expect(card.getByRole("button", { name: "Resume" })).toBeVisible();
  await capture(page, join(SHOTS, "09-mcp-resume-failed-stays-paused.png"));

  await page.setViewportSize({ width: 390, height: 844 });
  await settled(page);
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "10-mcp-resume-failed-390.png"), card);
  await page.setViewportSize({ width: 1440, height: 900 });
  expect(seen.failures).toEqual([]);
});

test("a webhook sender repeating itself a third time is refused as a loop, and the receipt says so", async ({ page, request }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  try {
    harness("pair-webhook");
  } catch {
    // Paired by an earlier attempt of this scenario on the same workspace.
  }
  const send = (text: string) =>
    request.post(`${BASE}/api/channels/channel.webhooks/inbound`, {
      data: { sender_id: "ops", text },
      headers: { "X-Raiker-Channel-Secret": CHANNEL_SECRET },
    });
  // Unique per attempt: the guard remembers a message for ten minutes, and a
  // retried attempt of this scenario is exactly the repeat it refuses.
  const asked = `deploy status? (${Date.now()})`;
  expect((await send(asked)).status()).toBe(200);
  expect((await send(asked)).status()).toBe(200);
  const third = await send(asked);
  expect(third.status()).toBe(409);
  expect(((await third.json()) as { detail: { reason_code: string } }).detail.reason_code).toBe("loop_repeated");
  expect((await send(`anything new since lunch? (${Date.now()})`)).status()).toBe(200);

  await page.goto(`${BASE}/#/messaging`);
  await settled(page);
  const receipts = page.locator("section.receipts").first();
  await expect(receipts.getByText(/Failed: the same message arrived a third time in ten minutes/).first()).toBeVisible({
    timeout: 30_000,
  });
  await capture(page, join(SHOTS, "11-messaging-loop-refused-receipt.png"), receipts);
  expect(seen.failures).toEqual([]);
});

test("the support bundle passes its own secret check, and an encoded body is refused 415", async ({ page, request }) => {
  test.setTimeout(120_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/observe?tab=overview`);
  await settled(page);
  await page.getByRole("button", { name: /build support bundle/i }).click();
  const bundle = page.getByLabel(/redacted support bundle/i);
  await expect(bundle).toContainText("local single-user runtime", { timeout: 30_000 });
  await expect(bundle).not.toContainText("sk-ant");
  await capture(page, join(SHOTS, "12-support-bundle-checked.png"), bundle);

  const encoded = await request.post(`${BASE}/api/auth/login`, {
    data: gzipSync(Buffer.from(JSON.stringify({ username: "x", password: "y" }))),
    headers: { "Content-Type": "application/json", "Content-Encoding": "gzip" },
  });
  expect(encoded.status()).toBe(415);
  expect(((await encoded.json()) as { reason_code: string }).reason_code).toBe("request_body_encoding_unsupported");
  expect(seen.failures).toEqual([]);
});

test("the time-zone list offers Asia/Kolkata, not the engine's Asia/Calcutta", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=general`);
  await settled(page);
  const select = page.getByLabel("Time zone");
  const values = await select.locator("option").evaluateAll((options) =>
    options.map((option) => (option as HTMLOptionElement).value),
  );
  expect(values).toContain("Asia/Kolkata");
  expect(values).toContain("Europe/Kyiv");
  expect(values).not.toContain("Asia/Calcutta");
  await select.selectOption("Asia/Kolkata");
  await expect(page.getByTestId("timezone-resolved")).toContainText("Asia/Kolkata");
  await expect(page.getByTestId("timezone-offset")).toContainText("UTC+05:30");
  await capture(page, join(SHOTS, "13-settings-time-zone-kolkata.png"), page.getByTestId("timezone-resolved"));
  await page.getByRole("button", { name: /^Discard/ }).click().catch(() => undefined);
});

test("deleting the account needs the username typed and returns to a fresh lock screen", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=account`);
  await settled(page);
  await page.getByRole("button", { name: "Delete my account" }).click();
  await expect(page.getByTestId("account-deletion-impact")).toContainText("This removes");
  await page.getByLabel("Confirm your password").fill(OWNER_CREDENTIALS.password);
  const name = (await page.locator("label", { hasText: "Type your username" }).locator("strong").textContent()) ?? "";
  await page.getByLabel(/Type your username/).fill(name);
  await page.getByRole("button", { name: "Permanently delete" }).click();
  await expect(page.getByLabel("Confirm password")).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "14-account-deleted-fresh-lock-screen.png"));
  expect(seen.failures).toEqual([]);
});
