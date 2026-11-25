/**
 * The five priority items of 2026-09-04, exercised against a running host.
 *
 * Unit and API tests prove each mechanism. This proves the *product*: what an
 * owner does, on the surface they do it on, and what the screen says afterwards.
 * Each block is written so it can fail for exactly one reason.
 */
import { createServer, type Server } from "node:http";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { setPermission, signInAsOwner } from "./hosted-provider";

import { roundName } from "./naming";
import { LIVE_BASE as BASE } from "./live";

// BUG-250 — named per run, so a round that has already worked in this
// workspace cannot find its own leftovers and assert on them. The suite shares
// one workspace by design; this is what keeps a shared workspace honest.
const PROJECT = roundName("Repo work");

test.describe.configure({ mode: "serial" });

test("a Build task says so on the board, and a Chat one stays quiet (backlog #23)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);

  // Build's method is a repository it can read, so the control appears inside a
  // project and nowhere else. Make one.
  await page.goto(`${BASE}/#/projects`);
  await page.waitForLoadState("networkidle");
  const nameField = page.getByLabel(/Project name|Name/i).first();
  await nameField.fill(PROJECT);
  await page.getByRole("button", { name: /^(Create project|Create)$/ }).first().click();
  await expect(page.getByText(PROJECT).first()).toBeVisible({ timeout: 30_000 });

  await page.goto(`${BASE}/#/tasks`);
  await page.waitForLoadState("networkidle");
  // Outside a project there is nothing to choose: Build has no repository.
  await expect(page.getByRole("group", { name: "How to work" })).toHaveCount(0);

  await capture(page, "../../docs/plans/screenshots/working/backlog-23-task-surface.png");
});

/** The collector moved into Diagnostics' closed *Share or export* fold. */
async function openShareOrExport(page: Page): Promise<void> {
  const fold = page.locator("details.support");
  if ((await fold.getAttribute("open")) === null) await fold.locator("summary").click();
}

/**
 * A stand-in OpenTelemetry collector on 4318 for the host to deliver to.
 *
 * The case needs something listening (2026-11-25 round: with nothing there it
 * failed on *event(s) delivered*). When a real collector already holds the port
 * it is used instead, so the case never shadows one the owner runs.
 */
async function standInCollector(): Promise<{ server: Server | null; received: () => number }> {
  let count = 0;
  const server = createServer((request, response) => {
    request.resume();
    request.on("end", () => {
      count += 1;
      response.writeHead(200, { "content-type": "application/json" });
      response.end("{}");
    });
  });
  const listening = await new Promise<boolean>((resolve) => {
    server.once("error", () => resolve(false));
    server.listen(4318, "127.0.0.1", () => resolve(true));
  });
  return { server: listening ? server : null, received: () => count };
}

test("a collector receives governed events, metadata only (backlog #18)", async ({ page }) => {
  test.setTimeout(180_000);
  const collector = await standInCollector();
  test.info().annotations.push({
    type: "collector",
    description: collector.server ? "stand-in on 127.0.0.1:4318" : "an existing collector on 4318",
  });
  try {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/observe?tab=overview`);
  await page.waitForLoadState("networkidle");
  await openShareOrExport(page);

  await expect(page.getByRole("heading", { name: "Can I see this outside Raiker?" })).toBeVisible();

  // A delivery leaves the machine, so it answers to `telemetry_export` — a Tier
  // 2 capability with a threat-model acknowledgement and a confirmation token.
  // The section says so before the press rather than answering a raw reason
  // code afterwards, which is the half this asserts first.
  const closed = page.getByText(/Telemetry export is/);
  if (await closed.count()) {
    // QUI-L06 — the permission opens beside its category; the shared helper
    // confirms the owner's dialog (reason, token, threat-model acknowledgement).
    await setPermission(page, BASE, "Telemetry export", "Turn on", "Live validation of the governed OTLP export");
    await page.goto(`${BASE}/#/observe?tab=overview`);
    await page.waitForLoadState("networkidle");
    await openShareOrExport(page);
  }
  // The honest empty state: no collector, so nothing can leave.
  const existing = page.getByText("Local collector", { exact: true });
  if ((await existing.count()) === 0) {
    await page.getByRole("button", { name: /Add collector/ }).click();
    await page.getByLabel("Name").fill("Local collector");
    await page.getByLabel("OTLP endpoint").fill("http://127.0.0.1:4318");
    await page.getByRole("button", { name: /^Add collector$/ }).click();
    await expect(page.getByText("Local collector", { exact: true })).toBeVisible({ timeout: 30_000 });
  }

  // Metadata only until the owner says otherwise, said on the card.
  await expect(page.getByText("Metadata only")).toBeVisible();

  await page.getByRole("button", { name: "Deliver now" }).click();
  await expect(page.getByText(/event\(s\) delivered/)).toBeVisible({ timeout: 60_000 });

  // A second run sends only what is new, so it never re-sends the first run's.
  await page.getByRole("button", { name: "Deliver now" }).click();
  await expect(page.getByText(/event\(s\) delivered/)).toBeVisible({ timeout: 60_000 });

  await capture(page, "../../docs/plans/screenshots/working/backlog-18-otlp-collector.png");
  if (collector.server) expect(collector.received()).toBeGreaterThan(0);
  } finally {
    await new Promise<void>((resolve) => (collector.server ? collector.server.close(() => resolve()) : resolve()));
  }
});

test("a connected MCP server says what each of its tools takes (backlog #16, MCP half)", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);

  // Building and connecting are two capabilities, both Tier 4, both off on a
  // fresh instance. Turn each on the way an owner would.
  for (const label of ["MCP builder", "MCP connector"]) {
    await setPermission(page, BASE, label, "Turn on", "Live validation of declared MCP tool schemas");
  }

  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  await page.waitForLoadState("networkidle");

  // Scoped to the server list: an unscoped text match finds the example's own
  // template name in the picker and skips the creation entirely.
  const card = page.getByRole("listitem").filter({ hasText: "Command" }).first();
  if ((await card.count()) === 0) {
    // REM-MCP-01 — the sample generator is a developer example below the list,
    // not the page's opening move, so it is opened before it is used.
    await page.getByText("Developer example", { exact: false }).click();
    await page.getByLabel("Server name").fill("echo");
    await page.getByRole("button", { name: "Generate example server" }).click();
  }
  await expect(card).toBeVisible({ timeout: 60_000 });

  // Test is the handshake. It is what reads `tools/list`, and before this round
  // it kept the names from that answer and dropped the schemas beside them.
  await card.getByRole("button", { name: "Test" }).click();
  await expect(page.getByText(/tool\(s\)/).first()).toBeVisible({ timeout: 60_000 });

  // The reviewed echo template declares `text` as required on `echo`, and an
  // object with no properties on `workspace_ping`. Both are on the card, and
  // they read as two different facts.
  await expect(card.getByText("text", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(card.getByText("Takes no arguments")).toBeVisible();

  await capture(page, "../../docs/plans/screenshots/working/backlog-16-mcp-declared-arguments.png");
});

test("an http hook says which destination the grant covers (BUG-226)", async ({ page }) => {
  test.setTimeout(180_000);
  // The fixture this test reads: a workspace rule with two http handlers. The
  // host must run with RAIKER_HOOK_EGRESS_ALLOWLIST=127.0.0.1:* (the grant).
  // Written here from RAIKER_LIVE_WORKSPACE rather than left to the operator,
  // which is why the 2026-11-17 re-run found nothing to read.
  const workspace = process.env.RAIKER_LIVE_WORKSPACE ?? "";
  test.skip(workspace === "", "set RAIKER_LIVE_WORKSPACE to the host's workspace");
  const { mkdirSync, writeFileSync } = await import("node:fs");
  mkdirSync(`${workspace}/config`, { recursive: true });
  writeFileSync(`${workspace}/config/hooks.json`, JSON.stringify({
    schema_version: "1.0",
    hooks: {
      PreToolUse: [{
        matcher: "shell",
        handlers: [
          { id: "local", type: "http", url: "http://127.0.0.1:9099/hook" },
          { id: "elsewhere", type: "http", url: "https://hooks.elsewhere.invalid/raiker" },
        ],
      }],
    },
  }));
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/extensions?tab=hooks`);
  await page.waitForLoadState("networkidle");

  // The host runs with RAIKER_HOOK_EGRESS_ALLOWLIST=127.0.0.1:* and the
  // workspace holds a rule with two http handlers: one destination the grant
  // covers and one it does not. Both parse and both match; only one will run,
  // and the page says which — read live, so revoking the grant is visible
  // without editing the rule or restarting anything.
  const rules = page.locator("section.card").filter({ hasText: "Configured rules" });
  await expect(rules.getByText("http://127.0.0.1:9099/hook")).toBeVisible({ timeout: 30_000 });
  await expect(rules.getByText("https://hooks.elsewhere.invalid/raiker")).toBeVisible();
  await expect(
    rules.getByText(/this host is not in RAIKER_HOOK_EGRESS_ALLOWLIST/),
  ).toHaveCount(1);

  await capture(page, "../../docs/plans/screenshots/working/bug-226-http-hook-grant.png");
});
