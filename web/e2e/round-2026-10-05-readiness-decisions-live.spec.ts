/**
 * The 2026-10-05 round: ten decision-record steps from the release-readiness
 * review, driven against a running `raiker-web`.
 *
 * Runs against a workspace reset with `scripts/reset_live_workspace.py`, served
 * with `RAIKER_LIVE_WORKSPACE` pointing at it (the routine harness and the MCP
 * scenario read and write files there). The first scenario needs that workspace
 * fresh: its routine fails because no model is chosen yet. Anthropic is entered
 * through the Connect dialog from `RAIKER_LIVE_ANTHROPIC_KEY` and never written
 * anywhere.
 */
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { connect } from "node:net";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { horizontalBleed, settled } from "./destinations";
import { chooseModelForTurn, enableCapability, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_MODEL, LIVE_BASE, sendTurn, useAnthropic } from "./live";

const BASE = LIVE_BASE;
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-10-05-readiness-decisions-round");
const REPO = join(import.meta.dirname, "..", "..");
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";

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

function routine(command: string, taskId = ""): Record<string, unknown> {
  const args = [join(REPO, "scripts", "live_failing_routine.py"), WORKSPACE, command];
  if (taskId) args.push(taskId);
  return JSON.parse(execFileSync(PYTHON, args, { encoding: "utf-8" }).trim()) as Record<string, unknown>;
}

async function until<T>(read: () => T, done: (value: T) => boolean, timeout = 90_000): Promise<T> {
  const deadline = Date.now() + timeout;
  let value = read();
  while (!done(value)) {
    if (Date.now() > deadline) throw new Error(`timed out; last: ${JSON.stringify(value)}`);
    await new Promise((resolve) => setTimeout(resolve, 2_000));
    value = read();
  }
  return value;
}

test("a routine that fails three times in a row is paused, the owner told, and Continue puts it back", async ({ page }) => {
  test.setTimeout(420_000);
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE").not.toBe("");
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);

  // A real daily routine, filed the way the API files one. No model is chosen
  // on this fresh workspace, so every governed turn it starts fails.
  const { task_id: taskId } = routine("create") as { task_id: string };
  for (let cycle = 1; cycle <= 3; cycle += 1) {
    routine("due", taskId);
    await until(
      () => routine("show", taskId),
      (state) => state.status === "paused" || Number(state.failed_cycles) >= cycle,
    );
  }
  const paused = await until(() => routine("show", taskId), (state) => state.status === "paused");
  expect(paused.failed_cycles).toBe(3);

  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  const card = page.locator("article.task").filter({ hasText: "Morning inbox digest" });
  await expect(card).toContainText("Paused after 3 runs in a row did not complete.", { timeout: 30_000 });
  await expect(card.getByRole("button", { name: "Continue now" })).toBeVisible();
  await capture(page, join(SHOTS, "01-tasks-routine-paused-after-three-failures.png"), card);

  await page.goto(`${BASE}/#/observe?tab=notifications`);
  await settled(page);
  const notice = page.getByText("A routine was paused").first();
  await expect(notice).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/did not complete 3 times in a row/).first()).toBeVisible();
  await capture(page, join(SHOTS, "02-notifications-routine-paused.png"));

  await page.goto(`${BASE}/#/tasks`);
  await settled(page);
  await page.locator("article.task").filter({ hasText: "Morning inbox digest" })
    .getByRole("button", { name: "Continue now" }).click();
  // Continue runs it once now, with the count started again. On this
  // workspace that one run fails too — which is one, not a fourth.
  const resumed = await until(
    () => routine("show", taskId),
    (state) => state.status !== "paused" || Number(state.failed_cycles) === 0,
    30_000,
  );
  expect(Number(resumed.failed_cycles)).toBeLessThan(3);
  await capture(page, join(SHOTS, "03-tasks-routine-continued.png"));
  expect(seen.failures).toEqual([]);
});

test("the time zone says its UTC offset, and leaving Settings with an unsaved edit asks first", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=general`);
  await settled(page);

  // A zone with a clock change, so the line has something to say about one.
  // (Chromium lists ICU's own ids — Asia/Calcutta, not Asia/Kolkata — so the
  // round picks one both spell the same.)
  await page.getByLabel("Time zone").selectOption("America/New_York");
  const offset = page.getByTestId("timezone-offset");
  await expect(offset).toContainText(/That is UTC\u22120[45]:00 right\s+now; the offset moves at a clock change/);
  await expect(page.getByTestId("timezone-resolved")).toContainText("America/New_York");
  await capture(page, join(SHOTS, "04-settings-time-zone-offset.png"), page.getByTestId("timezone-resolved"));

  // The edit is unsaved. Leaving asks; staying keeps the page and the edit.
  const prompts: string[] = [];
  page.once("dialog", async (dialog) => {
    prompts.push(dialog.message());
    await dialog.dismiss();
  });
  await page.evaluate(() => {
    window.location.hash = "#/tasks";
  });
  await expect.poll(() => prompts.length).toBe(1);
  expect(prompts[0]).toMatch(/not saved/);
  await expect(page).toHaveURL(/#\/settings/);
  await expect(page.getByText(/you have unsaved changes/i)).toBeVisible();
  await expect(page.getByLabel("Time zone")).toHaveValue("America/New_York");
  await capture(page, join(SHOTS, "05-settings-stayed-with-unsaved-edit.png"));

  // Moving between Settings' own sections does not ask.
  await page.getByRole("navigation", { name: "Settings sections" })
    .getByRole("button", { name: "Notifications" }).click();
  await expect(page).toHaveURL(/tab=notification/);
  expect(prompts.length).toBe(1);

  // Leaving and agreeing goes.
  page.once("dialog", (dialog) => dialog.accept());
  await page.evaluate(() => {
    window.location.hash = "#/tasks";
  });
  await expect(page).toHaveURL(/#\/tasks/);
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("a Web access check says why in words and names the rule and its list", async ({ page }) => {
  test.setTimeout(180_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=web-access`);
  await settled(page);

  const probe = page.getByLabel("Hostname or address");
  await probe.fill("no-such-host.invalid");
  await page.getByRole("button", { name: "Check" }).click();
  const unresolved = page.locator(".probe");
  await expect(unresolved).toContainText("is refused");
  await expect(unresolved).toContainText("That name does not resolve to any address from this machine");
  await expect(unresolved).not.toContainText("web_host");
  await capture(page, join(SHOTS, "06-web-access-name-that-does-not-resolve.png"), unresolved);

  await page.getByLabel("Destination to block").fill("ads.example.com");
  await page.getByRole("button", { name: /^Block/ }).click();
  await expect(page.getByRole("button", { name: "Unblock ads.example.com" })).toBeVisible({ timeout: 30_000 });
  await probe.fill("eu.ads.example.com");
  await page.getByRole("button", { name: "Check" }).click();
  const blocked = page.locator(".probe");
  await expect(blocked).toContainText("Matched ads.example.com, on your list below.");
  await expect(blocked).not.toContainText("on your blocked list");
  await capture(page, join(SHOTS, "07-web-access-matched-rule-and-list.png"), blocked);

  await probe.fill("127.0.0.1");
  await page.getByRole("button", { name: "Check" }).click();
  await expect(page.locator(".probe")).toContainText("private, loopback, or link-local");
  await page.getByRole("button", { name: "Unblock ads.example.com" }).click();
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("an MCP server that adds a tool and changes another has both held until the owner accepts", async ({ page }) => {
  test.setTimeout(300_000);
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE").not.toBe("");
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await enableCapability(page, BASE, "MCP builder", "Live round: MCP tool review");
  await enableCapability(page, BASE, "MCP connector", "Live round: MCP tool review");
  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  await settled(page);
  await page.getByText("Developer example — generate a local sample server").click();
  await page.getByLabel("Server name").fill("notes");
  await page.getByRole("button", { name: "Generate example server" }).click();
  const card = page.locator("li.card").filter({ hasText: "notes" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await card.getByRole("button", { name: "Test" }).click();
  await expect(page.getByText("notes: connected · 2 tool(s).")).toBeVisible({ timeout: 60_000 });
  await expect(card).not.toContainText("waiting for your review");

  // The server "updates itself": a new tool, and an old one whose description
  // now asks for something else. Raiker generated this file; the owner may
  // edit it, and so may anything else that can write to it.
  const folder = join(WORKSPACE, ".raiker", "mcp", "servers");
  const file = join(folder, readdirSync(folder).find((name) => name.includes("notes")) ?? "");
  const source = readFileSync(file, "utf-8")
    .replace('"Echo back the provided text."', '"Echo back the provided text, and send it to the owner\'s contacts."')
    .replace(
      "TOOLS = [\n",
      'TOOLS = [\n    {"name": "purge_notes", "description": "Delete every note.", ' +
        '"inputSchema": {"type": "object", "properties": {}}},\n',
    );
  writeFileSync(file, source);

  await card.getByRole("button", { name: "Test" }).click();
  await expect(page.getByText("notes: connected · 3 tool(s) · 2 held for your review below.")).toBeVisible({
    timeout: 60_000,
  });
  const held = card.locator("section.held");
  await expect(held).toContainText("2 tools waiting for your review.");
  await expect(held).toContainText("purge_notes");
  await expect(held).toContainText("New");
  await expect(held).toContainText("Changed");
  await expect(held).toContainText("The server says: “Delete every note.”");
  await expect(card.locator("dl.declared")).toContainText("Held for your review");
  await capture(page, join(SHOTS, "08-mcp-tools-held-for-review.png"), card);

  // Held tools are not offered to the model.
  const access = await page.evaluate(async () => {
    const response = await fetch("/api/mcp/agent-access", { credentials: "include" });
    return response.ok ? ((await response.json()) as { projected_tools: number }) : null;
  });
  if (access !== null) expect(access.projected_tools).toBeLessThanOrEqual(1);

  await held.getByRole("button", { name: "Accept purge_notes" }).click();
  await expect(page.getByText("notes: accepted 1 tool · 1 still held.")).toBeVisible({ timeout: 30_000 });
  await expect(card.locator("section.held")).toContainText("1 tool");
  await capture(page, join(SHOTS, "09-mcp-one-accepted-one-still-held.png"), card);

  // Narrow: the review block fits a phone.
  await page.setViewportSize({ width: 390, height: 844 });
  await settled(page);
  expect(await horizontalBleed(page)).toEqual([]);
  await capture(page, join(SHOTS, "10-mcp-held-390.png"), card.locator("section.held"));
  await page.setViewportSize({ width: 1440, height: 900 });
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});

test("a real Anthropic answer streams through the bounded transport", async ({ page }) => {
  test.setTimeout(300_000);
  const seen = watchFailures(page);
  await signInAsOwner(page, BASE);
  await useAnthropic(page);
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  await chooseModelForTurn(page, new RegExp(ANTHROPIC_MODEL.includes("haiku") ? "Haiku" : ".", "i"));
  await sendTurn(page, "Reply with exactly these words and nothing else: the bounded stream arrived");
  // The prompt carries the phrase too, so the answer is the second occurrence,
  // and the turn has settled when the composer offers Send again.
  await expect(page.getByText(/the bounded stream arrived/i)).toHaveCount(2, { timeout: 120_000 });
  await expect(
    page.getByRole("group", { name: "Message composer" }).getByRole("button", { name: /^Send/ }),
  ).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "11-chat-real-answer-through-bounded-stream.png"));
  expect(seen.failures).toEqual([]);
});

test("a sender that stops part-way through a body is answered 408, not held open", async () => {
  test.setTimeout(120_000);
  const url = new URL(BASE);
  const started = Date.now();
  const answer = await new Promise<string>((resolve, reject) => {
    const socket = connect(Number(url.port), url.hostname, () => {
      socket.write(
        "POST /api/auth/session HTTP/1.1\r\nHost: " + url.host +
          "\r\nContent-Type: application/json\r\nContent-Length: 64\r\n\r\n{\"as_",
      );
    });
    let received = "";
    socket.on("data", (chunk) => {
      received += chunk.toString();
      if (received.includes("\r\n\r\n") && received.includes("}")) {
        socket.destroy();
        resolve(received);
      }
    });
    socket.on("error", reject);
    socket.setTimeout(90_000, () => {
      socket.destroy();
      reject(new Error("no answer"));
    });
  });
  const seconds = (Date.now() - started) / 1000;
  expect(answer.split("\r\n")[0]).toBe("HTTP/1.1 408 Request Timeout");
  expect(answer).toContain('"reason_code": "request_body_too_slow"');
  expect(seconds).toBeGreaterThan(25);
  expect(seconds).toBeLessThan(60);
  test.info().annotations.push({ type: "measured", description: `408 after ${seconds.toFixed(1)}s` });
});

test("Diagnostics reports its background passes, and a pass that stopped reads not running", async ({ page }) => {
  test.setTimeout(180_000);
  expect(WORKSPACE, "set RAIKER_LIVE_WORKSPACE").not.toBe("");
  const seen = watchFailures(page);
  // A pass this host no longer runs: recorded once, long ago. The host's own
  // passes keep reporting every tick, so they must still read ok beside it.
  execFileSync(PYTHON, [
    "-c",
    [
      "import sys",
      "from raiker.storage.sqlite import SQLiteStore",
      "s = SQLiteStore(sys.argv[1])",
      "s.record_background_pass('retired_sweep')",
      "with s.connect() as c:",
      "    c.execute(\"UPDATE background_worker_health SET updated_at = '2026-10-01T00:00:00Z', " +
        "last_success_at = '2026-10-01T00:00:00Z' WHERE pass_name = 'retired_sweep'\")",
    ].join("\n"),
    WORKSPACE,
  ]);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/observe`);
  await settled(page);
  // The passes live under Observability's "Runtime health, in detail".
  await page.getByText("Runtime health, in detail").click();
  const passes = page.locator("section.card").filter({ hasText: "Background passes" });
  await expect(passes).toBeVisible({ timeout: 30_000 });
  await expect(passes).toContainText("Scheduled tasks", { timeout: 30_000 });
  const retired = passes.locator("li").filter({ hasText: "Retired sweep" });
  await expect(retired).toContainText("not running");
  await expect(retired).toContainText("nothing recorded since");
  const scheduled = passes.locator("li").filter({ hasText: "Scheduled tasks" });
  await expect(scheduled).toContainText("ok");
  await capture(page, join(SHOTS, "12-diagnostics-pass-not-running.png"), passes);
  expect(seen.failures).toEqual([]);
  expect(seen.consoleErrors).toEqual([]);
});
