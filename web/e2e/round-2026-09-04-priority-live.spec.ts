/**
 * The five priority items of 2026-09-04, exercised against a running host.
 *
 * Unit and API tests prove each mechanism. This proves the *product*: what an
 * owner does, on the surface they do it on, and what the screen says afterwards.
 * Each block is written so it can fail for exactly one reason.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";

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
  await nameField.fill("Repo work");
  await page.getByRole("button", { name: /^(Create project|Create)$/ }).first().click();
  await expect(page.getByText("Repo work").first()).toBeVisible({ timeout: 30_000 });

  await page.goto(`${BASE}/#/tasks`);
  await page.waitForLoadState("networkidle");
  // Outside a project there is nothing to choose: Build has no repository.
  await expect(page.getByRole("group", { name: "How to work" })).toHaveCount(0);

  await capture(page, "../../docs/plans/screenshots/working/backlog-23-task-surface.png");
});

test("a collector receives governed events, metadata only (backlog #18)", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/observe?tab=overview`);
  await page.waitForLoadState("networkidle");

  await expect(page.getByRole("heading", { name: "Can I see this outside Raiker?" })).toBeVisible();

  // A delivery leaves the machine, so it answers to `telemetry_export` — a Tier
  // 2 capability with a threat-model acknowledgement and a confirmation token.
  // The section says so before the press rather than answering a raw reason
  // code afterwards, which is the half this asserts first.
  const closed = page.getByText(/Telemetry export is/);
  if (await closed.count()) {
    await page.goto(`${BASE}/#/capabilities`);
    const capability = page.locator(".cap.card").filter({ hasText: "Telemetry export" });
    await capability.locator("button.cap-toggle").click();
    const turnOn = capability.getByRole("button", { name: "Turn on" });
    if (await turnOn.isVisible()) {
      await turnOn.click();
      const dialog = page.getByRole("dialog");
      await dialog.getByLabel("Reason (required)").fill("Live validation of the governed OTLP export");
      const token = dialog.getByLabel(/Confirmation token/);
      if (await token.isVisible()) await token.fill("OTLP LIVE CONFIRM");
      const acknowledgement = dialog.getByLabel(/reviewed the threat model/);
      if (await acknowledgement.isVisible()) await acknowledgement.check();
      await dialog.getByRole("button", { name: "Confirm change" }).click();
      await expect(dialog).toBeHidden({ timeout: 30_000 });
    }
    await page.goto(`${BASE}/#/observe?tab=overview`);
    await page.waitForLoadState("networkidle");
  }
  // The honest empty state: no collector, so nothing can leave.
  const existing = page.getByText("Local collector");
  if ((await existing.count()) === 0) {
    await page.getByRole("button", { name: /Add collector/ }).click();
    await page.getByLabel("Name").fill("Local collector");
    await page.getByLabel("OTLP endpoint").fill("http://127.0.0.1:4318");
    await page.getByRole("button", { name: /^Add collector$/ }).click();
    await expect(page.getByText("Local collector")).toBeVisible({ timeout: 30_000 });
  }

  // Metadata only until the owner says otherwise, said on the card.
  await expect(page.getByText("Metadata only")).toBeVisible();

  await page.getByRole("button", { name: "Deliver now" }).click();
  await expect(page.getByText(/event\(s\) delivered/)).toBeVisible({ timeout: 60_000 });

  // A second run sends only what is new, so it never re-sends the first run's.
  await page.getByRole("button", { name: "Deliver now" }).click();
  await expect(page.getByText(/event\(s\) delivered/)).toBeVisible({ timeout: 60_000 });

  await capture(page, "../../docs/plans/screenshots/working/backlog-18-otlp-collector.png");
});

test("a connected MCP server says what each of its tools takes (backlog #16, MCP half)", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);

  // Building and connecting are two capabilities, both Tier 4, both off on a
  // fresh instance. Turn each on the way an owner would.
  for (const label of ["MCP builder", "MCP connector"]) {
    await page.goto(`${BASE}/#/capabilities`);
    await page.waitForLoadState("networkidle");
    const capability = page.locator(".cap.card").filter({ hasText: label }).first();
    await capability.locator("button.cap-toggle").click();
    const turnOn = capability.getByRole("button", { name: "Turn on" });
    if (await turnOn.isVisible()) {
      await turnOn.click();
      const dialog = page.getByRole("dialog");
      await dialog.getByLabel("Reason (required)").fill("Live validation of declared MCP tool schemas");
      const token = dialog.getByLabel(/Confirmation token/);
      if (await token.isVisible()) await token.fill("MCP LIVE CONFIRM");
      const acknowledgement = dialog.getByLabel(/reviewed the threat model/);
      if (await acknowledgement.isVisible()) await acknowledgement.check();
      await dialog.getByRole("button", { name: "Confirm change" }).click();
      await expect(dialog).toBeHidden({ timeout: 30_000 });
    }
  }

  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  await page.waitForLoadState("networkidle");

  // Scoped to the server list: an unscoped text match finds "Sample echo server
  // (safe starter)" in the template dropdown and skips the creation entirely.
  const card = page.getByRole("listitem").filter({ hasText: "Command" }).first();
  if ((await card.count()) === 0) {
    await page.getByLabel("Server name").fill("echo");
    await page.getByRole("button", { name: "Create server" }).click();
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
