/**
 * QUI-G06: real host and owner sign-in, with endpoint fault injection.
 * Server rows are declared fixtures; these tests do not certify a live MCP
 * transport, credential provider, sandbox or model. No real secrets are used.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { enableCapability, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SERVICES = `${BASE}/#/connections?tab=services`;
const SERVERS = `${BASE}/#/connections?tab=advanced&kind=mcp`;
const SHOTS = "../../output/playwright/2026-11-06-connection-recovery";
const failure = { status: 503, contentType: "application/json", body: '{"detail":{"reason_code":"injected_failure"}}' };
const sample = {
  server_id: "mcp_recovery", name: "Recovery example", transport: "stdio",
  command: ["python", "example.py"], template: "python-stdio-echo", status: "connected",
  created_at: "2026-11-06T00:00:00Z", last_connected_at: null,
  tools: ["echo"], tool_count: 1, unsupported_features: [], tool_declarations: [],
  endpoint_url: null, auth_ref: null, monitor_state: "active", paused_reason: null,
  paused_at: null, protocol_version: null, source: "raiker_sample", source_plugin: null,
  purpose: "Recovery fixture", purpose_from: "server", scope: null,
  pending_tools: [{ name: "echo", change: "changed", description: "Return text", fingerprint: "fixture" }],
  vault_env: ["DEMO_KEY"],
};
test.describe.configure({ mode: "serial", timeout: 120_000 });

async function prepare(page: Page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
}

async function fixtureServer(page: Page) {
  await page.route("**/api/mcp/servers", route => route.request().method() === "GET"
    ? route.fulfill({ json: [sample] }) : route.continue());
  await page.route("**/api/mcp/servers/mcp_recovery/sessions", route => route.fulfill({ json: [] }));
  await page.route("**/api/mcp/servers/mcp_recovery/findings", route => route.fulfill({ json: [] }));
}

test("RT-CONNECTION-RECOVERY-01: failed read stops loading and refresh recovers", async ({ page }) => {
  await prepare(page);
  await page.route("**/api/connector-store", route => route.fulfill(failure));
  await page.goto(SERVICES);
  const alert = page.getByRole("alert").filter({ hasText: "Could not load connections" });
  await expect(alert).toContainText("Refresh connections");
  await expect(page.getByText("Loading connections…", { exact: true })).toHaveCount(0);
  await capture(page, `${SHOTS}/01-services-read.png`, alert);
  await page.unroute("**/api/connector-store");
  await page.getByRole("button", { name: "Refresh connections", exact: true }).click();
  await expect(alert).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add connection", exact: true })).toBeVisible();
});

test("RT-CONNECTION-RECOVERY-02: failed Add stays inside its dialog", async ({ page }) => {
  await prepare(page);
  await page.route("**/api/connector-store/gmail/install", route => route.fulfill(failure));
  await page.goto(SERVICES);
  await page.getByRole("button", { name: "Add connection", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Add connection" });
  await dialog.getByRole("button", { name: /Gmail/ }).click();
  await dialog.getByRole("button", { name: "Add Gmail", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("check whether it was added");
  await expect(page.getByRole("alert")).toHaveCount(1);
  await expect(dialog.getByRole("button", { name: "Refresh connections", exact: true })).toBeEnabled();
  await capture(page, `${SHOTS}/02-add-service.png`, dialog.getByRole("alert"));
});

test("RT-CONNECTION-RECOVERY-03: Advanced read recovers in dark theme", async ({ page }) => {
  await prepare(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.route("**/api/mcp/servers", route => route.fulfill(failure));
  await page.goto(SERVERS);
  const alert = page.getByRole("alert").filter({ hasText: "Could not refresh Advanced servers" });
  await expect(alert).toContainText("Refresh servers");
  await expect(page.getByText("Loading MCP servers…", { exact: true })).toHaveCount(0);
  await capture(page, `${SHOTS}/03-servers-read-dark.png`, alert);
  await page.unroute("**/api/mcp/servers");
  await page.getByRole("button", { name: "Refresh servers", exact: true }).click();
  await expect(alert).toHaveCount(0);
});

test("RT-CONNECTION-RECOVERY-04: enable test permissions through owner UI", async ({ page }) => {
  await prepare(page);
  await enableCapability(page, BASE, "MCP builder", "Generate a disposable recovery test example");
  await enableCapability(page, BASE, "MCP connector", "Exercise recovery feedback with injected failures");
});

for (const [id, action, endpoint, prefix] of [
  ["05", "Test", "connect", "Could not test"],
  ["06", "Stop", "pause", "Could not stop"],
  ["07", "Accept echo", "tools/approve", "Could not accept tools"],
  ["08", "Delete", "", "Could not delete"],
  ["09", "Remove DEMO_KEY from Recovery example", "secrets/DEMO_KEY", "Could not remove the secret"],
]) {
  test(`RT-CONNECTION-RECOVERY-${id}: ${action} failure retains row and next step`, async ({ page }) => {
    await prepare(page);
    await fixtureServer(page);
    await page.route(`**/api/mcp/servers/mcp_recovery${endpoint ? `/${endpoint}` : "?*"}`, route => route.fulfill(failure));
    await page.goto(SERVERS);
    await page.getByRole("button", { name: action, exact: true }).click();
    const confirm = page.getByRole("dialog");
    if (action === "Delete" || action.startsWith("Remove")) {
      await expect(confirm).toBeVisible();
      await confirm.getByRole("button", { name: action === "Delete" ? "Delete" : "Remove", exact: true }).click();
    }
    const alert = page.getByRole("alert").filter({ hasText: prefix });
    await expect(alert).toContainText("Refresh servers");
    await expect(alert).toContainText("HTTP 503");
    await expect(page.getByText("Recovery example", { exact: true })).toBeVisible();
    if (action === "Test") {
      // Keep a failed action visible across the production ten-second poll.
      let reads = 0;
      page.on("response", response => { if (response.url().endsWith("/api/mcp/servers")) reads += 1; });
      await expect.poll(() => reads, { timeout: 20_000, intervals: [1000] }).toBeGreaterThan(0);
      await expect(alert).toBeVisible();
    }
    await capture(page, `${SHOTS}/${id}-server-action.png`, alert);
  });
}

test("RT-CONNECTION-RECOVERY-10: rename draft survives a lost response at 200% zoom", async ({ page }) => {
  await prepare(page);
  await fixtureServer(page);
  await page.route("**/api/mcp/servers/mcp_recovery", route => route.fulfill(failure));
  await page.goto(SERVERS);
  await page.getByRole("button", { name: "Rename", exact: true }).click();
  await page.getByRole("textbox", { name: "New server name" }).fill("Retained name");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  const alert = page.getByRole("alert").filter({ hasText: "Could not rename" });
  await expect(alert).toContainText("your draft is kept here");
  await expect(page.getByRole("textbox", { name: "New server name" })).toHaveValue("Retained name");
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.evaluate(() => { document.documentElement.style.zoom = "2"; });
  const cancel = page.getByRole("button", { name: "Cancel", exact: true });
  await cancel.scrollIntoViewIfNeeded();
  await expect(cancel).toBeInViewport();
  expect(await cancel.evaluate(button => {
    const bounds = button.getBoundingClientRect();
    const card = button.closest(".card")!.getBoundingClientRect();
    return bounds.right <= Math.min(card.right, innerWidth) && bounds.left >= card.left;
  })).toBe(true);
  await capture(page, `${SHOTS}/10-rename-zoom.png`, alert);
});

test("RT-CONNECTION-RECOVERY-11: create failure preserves the name", async ({ page }) => {
  await prepare(page);
  await page.route("**/api/mcp/servers", route => route.request().method() === "POST"
    ? route.fulfill(failure) : route.continue());
  await page.goto(SERVERS);
  await page.getByText("Developer example — generate a local sample server", { exact: true }).click();
  await page.getByLabel("Server name", { exact: true }).fill("Kept-example");
  await page.getByRole("button", { name: "Generate example server", exact: true }).click();
  const alert = page.getByRole("alert").filter({ hasText: "Could not create" });
  await expect(alert).toContainText("check for an existing profile");
  await expect(page.getByLabel("Server name", { exact: true })).toHaveValue("Kept-example");
  await capture(page, `${SHOTS}/11-create.png`, alert);
});

test("RT-CONNECTION-RECOVERY-12: plugin offer failure asks for read-back", async ({ page }) => {
  await prepare(page);
  await page.route("**/api/mcp/offers", route => route.fulfill({ json: [{
    plugin_id: "recovery-fixture", name: "Offered example", description: "Recovery fixture",
    transport: "stdio", template: "python-stdio-echo", already_added: false,
  }] }));
  await page.route("**/api/mcp/servers", route => route.request().method() === "POST"
    ? route.fulfill(failure) : route.continue());
  await page.goto(SERVERS);
  await page.getByRole("button", { name: "Add server", exact: true }).click();
  const alert = page.getByRole("alert").filter({ hasText: "Could not add" });
  await expect(alert).toContainText("check whether it was added");
  await capture(page, `${SHOTS}/12-offer.png`, alert);
});

test("RT-CONNECTION-RECOVERY-13: a failed secret write keeps the private entry", async ({ page }) => {
  await prepare(page);
  await fixtureServer(page);
  await page.route("**/api/mcp/servers/mcp_recovery/secrets/NEW_KEY", route => route.fulfill(failure));
  await page.goto(SERVERS);
  const input = page.getByLabel("Value", { exact: true });
  await expect(input).toBeVisible();
  await page.getByLabel("Variable name", { exact: true }).fill("NEW_KEY");
  await input.fill("disposable-fixture-value");
  await page.getByRole("button", { name: "Give to this server", exact: true }).click();
  const alert = page.getByRole("alert").filter({ hasText: "Could not save the secret" });
  await expect(alert).toContainText("saved secret is unconfirmed");
  await expect(input).toHaveValue("disposable-fixture-value");
  await expect(input).toHaveAttribute("type", "password");
  await expect(alert).not.toContainText("disposable-fixture-value");
  await capture(page, `${SHOTS}/13-secret.png`, alert);
});

test("RT-CONNECTION-RECOVERY-14: install keeps sign-in and a failed credential entry", async ({ page }) => {
  await prepare(page);
  await page.route("**/api/connector-store/gmail/credentials", route => route.fulfill(failure));
  await page.goto(SERVICES);
  await page.getByRole("button", { name: "Add connection", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Add connection" });
  await dialog.getByRole("button", { name: /Gmail/ }).click();
  await dialog.getByRole("button", { name: "Add Gmail", exact: true }).click();
  const entry = dialog.getByLabel("OAuth access token", { exact: true });
  await expect(entry).toBeVisible();
  await entry.fill("disposable-fixture-value");
  await dialog.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("saved sign-in is unconfirmed");
  await expect(entry).toHaveValue("disposable-fixture-value");
  await capture(page, `${SHOTS}/14-credential.png`, dialog.getByRole("alert"));
});

for (const [id, action, endpoint, message] of [
  ["15", "Turn on for this session", "enabled*", "Session access is unconfirmed"],
  ["16", "Disconnect and remove its credential", "", "Credential removal is unconfirmed"],
]) {
  test(`RT-CONNECTION-RECOVERY-${id}: ${action} retains the service`, async ({ page }) => {
    await prepare(page);
    // Only the read model is changed to expose the owner action; credentials
    // are never stored and all writes to the target service fail explicitly.
    await page.route("**/api/connector-store", async route => {
      const response = await route.fetch();
      const body = await response.json();
      body.connectors = body.connectors.map((row: { connector_id: string }) => row.connector_id === "gmail"
        ? { ...row, installed: true, auth_status: "connected", enabled: false } : row);
      await route.fulfill({ response, json: body });
    });
    await page.route(`**/api/connector-store/gmail${endpoint ? `/${endpoint}` : ""}`, route => route.fulfill(failure));
    await page.goto(SERVICES);
    await page.getByRole("option", { name: /Gmail/ }).click();
    await page.getByRole("button", { name: action, exact: true }).click();
    const alert = page.getByRole("alert").filter({ hasText: message });
    await expect(alert).toContainText("Refresh connections");
    await expect(page.getByRole("option", { name: /Gmail/ })).toBeVisible();
    await capture(page, `${SHOTS}/${id}-service-action.png`, alert);
  });
}
