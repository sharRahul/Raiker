import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { capture } from "./capture";
import { DESTINATIONS, WIDTHS, settled } from "./destinations";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";

/**
 * The second 2026-09-28 round, live: the items from `docs/plans/` this run
 * closed that only a browser and a real host can prove.
 *
 * * **BUG-308 (CR-05, CR-09)** — Permissions names *Code with this machine's
 *   network* and says, measured on this host, where scripts run; a real model
 *   asking to run `python` is governed under that capability rather than as an
 *   ordinary shell command; and a plugin's card says where its code would run.
 * * **GCR-13** — every JSON answer is now redacted as it is serialized. Only a
 *   browser signed in to a real host proves the product still reads every page
 *   through it, and that a stored key still never comes back.
 * * **GCR-11 / GCR-43** — the store and the dashboard service were split into
 *   domain parts. Every destination is walked at four widths, reading every
 *   page's own API, with no console error.
 *
 * Preconditions:
 *   1. `raiker-web` on 127.0.0.1:8765, on a workspace reset for the round, with
 *      `RAIKER_PLUGIN_RUNTIME_ALLOWLIST=acme-runner` in its environment
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment — entered through the UI
 *   3. `RAIKER_LIVE_WORKSPACE` naming that workspace, holding `hello.py`
 */
const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(
  import.meta.dirname,
  "..",
  "..",
  "docs",
  "screenshots",
  "2026-09-28-review-closure-round",
);
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const WORKSPACE = process.env.RAIKER_LIVE_WORKSPACE ?? "";
const PYTHON = process.env.RAIKER_LIVE_PYTHON ?? "python";
const MODEL = "claude-haiku-4-5-20251001";
const MODEL_LABEL = /Haiku 4\.5/;

test.describe.configure({ mode: "serial" });
test.setTimeout(600_000);

test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set for this round.");
test.skip(WORKSPACE === "", "RAIKER_LIVE_WORKSPACE is not set for this round.");

async function openCapability(page: Page, label: string) {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByLabel("Search capabilities");
  await expect(search).toBeVisible({ timeout: 60_000 });
  await search.fill(label);
  const card = page.locator(".cap.card").filter({ hasText: label }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  const toggle = card.getByRole("button", { name: label });
  if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();
  await expect(card.locator(".cap-detail")).toBeVisible({ timeout: 10_000 });
  return card;
}

test("the owner's provider is connected, and a model is ready to answer", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "anthropic",
    keyLabel: "API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await capture(page, join(SHOTS, "01-anthropic-connected.png"));
});

/**
 * GCR-13 — redaction happens where the value is serialized now. The saved key
 * must still never come back in any answer a page reads.
 */
test("GCR-13: a stored key never comes back through a redacted answer", async ({ page }) => {
  await signInAsOwner(page, BASE);
  const bodies = await page.evaluate(async () => {
    const out: string[] = [];
    for (const path of ["/api/models", "/api/connections", "/api/capability-gates", "/api/diagnostics"]) {
      const response = await fetch(path, { credentials: "same-origin" });
      out.push(`${path} ${response.status} ${await response.text()}`);
    }
    return out;
  });
  for (const body of bodies) {
    expect(body, body.slice(0, 80)).not.toContain(ANTHROPIC_KEY);
    expect(body).not.toContain(ANTHROPIC_KEY.slice(0, 24));
  }
  // Each one parsed: the bytes forwarded unbuffered are still whole JSON.
  for (const body of bodies) {
    const json = body.slice(body.indexOf(" ", body.indexOf(" ") + 1) + 1);
    expect(() => JSON.parse(json), body.slice(0, 80)).not.toThrow();
  }
});

/**
 * BUG-308 — Permissions names the capability, and says where code runs here.
 * This host has no native sandbox runner, so the measured answer is the host.
 */
test("BUG-308: Permissions names code with this machine's network, and says where it runs", async ({
  page,
}) => {
  await signInAsOwner(page, BASE);
  const card = await openCapability(page, "Code with this machine's network");
  await expect(card).toContainText(/Scripts run by python, node, npm or npx/);
  await expect(card.getByTestId("network-boundary")).toContainText(
    /no native sandbox: python, node, npm and npx commands run with its network/,
  );
  await capture(page, join(SHOTS, "02-permissions-code-with-this-machines-network.png"), card);

  const shell = await openCapability(page, "Shell commands");
  await expect(shell).not.toContainText(/sandboxed shell commands/i);
  await expect(shell.getByTestId("network-boundary")).toBeVisible();
  await capture(page, join(SHOTS, "03-permissions-shell-says-where-code-runs.png"), shell);
});

/**
 * BUG-308 — a real model asks to run `python`. It is governed as code with
 * this machine's network: the approval waits, and approving it runs the script.
 */
async function turnOn(page: Page, label: string, reason: string) {
  const card = await openCapability(page, label);
  const control = card.getByRole("button", { name: "Turn on" });
  if (!(await control.isVisible().catch(() => false))) return card; // already on
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
  return card;
}

/**
 * The owner's decision says nothing that worked starts refusing. Found live
 * this round: on an account an unset row reads as off, so turning shell on
 * would have left `python` refused by a switch the owner never saw. Turning
 * shell on now turns the new capability on beside it, as a row that says why.
 */
test("BUG-308: turning shell on turns code with this machine's network on beside it", async ({
  page,
}) => {
  await signInAsOwner(page, BASE);
  await turnOn(page, "Approval execution relay", "approvals should do what they say");
  await turnOn(page, "Shell commands", "let an approved command run");
  const card = await openCapability(page, "Code with this machine's network");
  await expect(card.getByRole("button", { name: "Turn off" })).toBeVisible({ timeout: 30_000 });
  await capture(page, join(SHOTS, "04-code-capability-on-beside-shell.png"), card);
});

test("BUG-308: a real turn asking to run python is governed as code with the host's network", async ({
  page,
}) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);
  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill(
    `Call the shell tool once with the command "${PYTHON} hello.py", then tell me exactly what it returned.`,
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
  await expect(page.getByRole("main")).toContainText(/approval/i, { timeout: 60_000 });
  await capture(page, join(SHOTS, "05-turn-waits-for-approval.png"));

  // The broker parks an approval-required shell action before it is routed.
  // The tool is still the shell, but the approval the owner reads names the
  // capability it will run under — the same placement rule the router asks.
  await page.goto(`${BASE}/#/approvals`);
  await page.getByLabel("Sort approvals").selectOption({ label: "Newest first" });
  const row = page.getByRole("row", { name: /shell/i }).first();
  await expect(row).toBeVisible({ timeout: 60_000 });
  await expect(row).toContainText("Code with this machine's network");
  await row.getByRole("button", { name: "Review" }).click();
  const detail = page.getByRole("main");
  await expect(detail).toContainText(/hello\.py/);
  await expect(detail).toContainText("Code with this machine's network");
  // Found by this round: the approval promised a file checkpoint a command
  // cannot have, and the docked approval card stayed over this very page.
  await expect(detail).toContainText("cannot be rewound");
  await expect(detail).not.toContainText("checkpointed first");
  await expect(page.getByRole("region", { name: "Approval needed" })).toBeHidden();
  await capture(page, join(SHOTS, "06-approval-names-the-script.png"));
  await page.getByRole("button", { name: "Approve and execute once" }).click();
  await expect(page.locator(".notice-ok").first()).toContainText(/Executed once/i, {
    timeout: 120_000,
  });
  await capture(page, join(SHOTS, "07-approved-script-ran-on-this-machine.png"));

  // The router's record of it, read from the workspace's own append-only log:
  // this action ran as code with this machine's network, and said so.
  const events = join(WORKSPACE, ".raiker", "events");
  const classified = readdirSync(events)
    .filter((name) => name.endsWith(".jsonl"))
    .map((name) => readFileSync(join(events, name), "utf-8"))
    .join("\n")
    .split("\n")
    .filter((line) => line.includes('"code_placement_classified"'));
  expect(classified.length, "no code_placement_classified event was recorded").toBeGreaterThan(0);
  expect(classified.at(-1)).toContain("host_network_code_execution");
});

/**
 * BUG-308 — the plugin card says where the plugin's own code would run. With
 * the plugin allowlisted and no container set up, the honest answer is the host.
 */
test("BUG-308: a plugin card says its code would run with this machine's network", async ({
  page,
}) => {
  execFileSync(
    process.env.RAIKER_LIVE_PYTHON_FOR_SEED ?? "python",
    [
      "-c",
      [
        "import sys",
        "from raiker.storage.sqlite import SQLiteStore",
        "from raiker.plugins.registry import record_plugin_install",
        "store = SQLiteStore(sys.argv[1])",
        "if not any(r.get('plugin_id') == 'acme-runner' for r in store.list_plugin_install_records()):",
        "    record_plugin_install(store, plugin_id='acme-runner', version='1.0.0', trust_level='local_dev', permissions_json='[]')",
      ].join("\n"),
      WORKSPACE,
    ],
    { stdio: "inherit" },
  );
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/extensions?tab=plugins`);
  const line = page.getByTestId("plugin-code-runtime").first();
  await expect(line).toContainText(/with this machine's network/, { timeout: 60_000 });
  await capture(page, join(SHOTS, "08-plugin-card-says-where-its-code-runs.png"), line);
});

/**
 * GCR-11 / GCR-43 — every destination, at every width, reads its own API
 * through the split store and service, with no console error.
 */
test("GCR-11/43: every destination reads through the split store and service", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`${page.url()} — ${message.text()}`);
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 500) {
      errors.push(`${response.status()} ${response.url()}`);
    }
  });
  await signInAsOwner(page, BASE);
  for (const { width, height } of WIDTHS) {
    await page.setViewportSize({ width, height });
    for (const destination of DESTINATIONS) {
      await page.goto(`${BASE}/#/${destination.route}`);
      await expect(page.locator("main#main")).toBeVisible({ timeout: 60_000 });
      await settled(page).catch(() => undefined);
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.locator("main#main")).toBeVisible({ timeout: 60_000 });
  await capture(page, join(SHOTS, "09-home-after-the-sweep.png"));
  // A provider this host cannot reach may log its refusal; nothing else may.
  const unexpected = errors.filter((line) => !/huggingface\.co|openrouter\.ai|ollama/i.test(line));
  expect(unexpected, unexpected.join("\n")).toEqual([]);
});
