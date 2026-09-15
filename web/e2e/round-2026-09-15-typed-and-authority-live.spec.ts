/**
 * The 2026-09-15 round, driven against a running host with a real Anthropic key.
 *
 * Five things landed in this round that a document can assert and a product can
 * fail to deliver, so each is driven here rather than reasoned about:
 *
 * 1. **BUG-293** — Permissions answers *what would this cost if it ran without
 *    me*, and *what stands in the way*, per capability, from the same runtime
 *    table the negative bypass test is asserted against.
 * 2. **BUG-239** — a fresh account starts with the local, reversible baseline
 *    available, and Build is one deliberate decision rather than four switches
 *    to find in a list of sixty-seven.
 * 3. **BUG-288** — a turn answers with a table Raiker *knows* is a table:
 *    sortable, announced as one, and with a chart beside it that carries its own
 *    numbers. Driven by a real model, because "the model used the channel" is a
 *    claim only a real turn can support.
 * 4. **REM-SET-GENERAL / REM-SET-APPEARANCE / REM-ACTIVITY / REM-HOME-03** — the
 *    four presentation rows, each verified where an owner meets it.
 * 5. **BUG-298** — `policy_mutation` is gone from the product, not hidden in it.
 *
 * The key is entered through the product's own Connect dialog, because the
 * screen an owner sees is the only screen worth testing.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = process.env.RAIKER_LIVE_ANTHROPIC_MODEL ?? "claude-haiku-4-5-20251001";
const SHOTS = "../../docs/screenshots";

test.describe.configure({ mode: "serial" });

/** Console errors are a budget, and a round that spends it silently is not evidence. */
function watchConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(String(error)));
  return errors;
}

async function openPermission(page: Page, label: RegExp): Promise<void> {
  await page.goto(`${BASE}/#/capabilities`);
  const search = page.getByLabel("Search capabilities");
  await expect(search).toBeVisible({ timeout: 60_000 });
  await search.fill(label.source.replace(/[\\^$]/g, ""));
  const row = page.getByRole("button", { name: label }).first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  if ((await row.getAttribute("aria-expanded")) !== "true") await row.click();
}

test("Permissions says what a capability would cost, and what stands in the way", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);

  await openPermission(page, /^Shell command/);
  // The two columns DEC-16 step 8 asked for and nothing had a home for. They
  // come from `CAPABILITY_AUTHORITY`, which CI asserts is complete against the
  // set of capabilities that have a real executor — so a switch on this page
  // either answers both questions or governs something that cannot run.
  await expect(page.getByText("If it ran without you")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("What stands in the way")).toBeVisible();
  await expect(page.getByText(/operating-system privileges/)).toBeVisible();

  // Reach, on the closed row, because it is what tells an owner which of
  // sixty-seven rows to read first and it does not change when the switch does.
  await expect(page.getByText("Cannot be undone").first()).toBeVisible();

  await capture(page, `${SHOTS}/permissions-capability-authority.png`);
  expect(errors, errors.join("\n")).toEqual([]);
});

test("a capability that leaves this machine says so before it is turned on", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await openPermission(page, /^Web fetch/);
  await expect(page.getByText("Leaves this machine").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/tells that host something about the owner/)).toBeVisible();
});

test("policy mutations are gone from the product, not hidden in it", async ({ page }) => {
  // BUG-298 — a routed gate nothing proposes was a switch over nothing. Policy
  // is process configuration the runtime reads, and the honest answer was the
  // boundary rather than the row.
  await signInAsOwner(page, BASE);
  const gates = await page.evaluate(async () => {
    const response = await fetch("/api/capability-gates", { credentials: "same-origin" });
    return response.ok ? await response.json() : { error: response.status };
  });
  const names = (gates.gates ?? gates).map((gate: { capability: string }) => gate.capability);
  expect(names).not.toContain("policy_mutation");
  expect(names).toContain("admin_mutation");
  expect(names).toContain("role_mutation");
});

test("a fresh account starts with the local baseline, and Build is one decision", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);

  // BUG-239, half one: the two repository reads answer on a new account instead
  // of waiting for the owner to find two switches. Read through the API rather
  // than through a chip, because the claim is about the gate and not the label.
  const gates = await page.evaluate(async () => {
    const response = await fetch("/api/capability-gates", { credentials: "same-origin" });
    return response.ok ? await response.json() : { gates: [] };
  });
  const byName = new Map(
    (gates.gates ?? gates).map((gate: { capability: string; state: string }) => [
      gate.capability,
      gate.state,
    ]),
  );
  for (const capability of [
    "language_intelligence",
    "code_map_indexing",
    "task_management_runtime",
    "project_assignment_runtime",
    "audit_export",
  ]) {
    expect(byName.get(capability), `${capability} should be in the account baseline`).toMatch(
      /^enabled/,
    );
  }
  // And nothing else moved: the baseline is local and reversible work only.
  expect(byName.get("shell_execution")).not.toMatch(/^enabled/);
  expect(byName.get("git_push_execution")).not.toMatch(/^enabled/);

  // Half two: the preset. It shows what it turns on before it turns it on — a
  // preset an owner cannot read before pressing is a permission change they did
  // not make.
  await page.goto(`${BASE}/#/capabilities`);
  const preset = page.getByRole("region", { name: "Set up for Build" });
  await expect(preset).toBeVisible({ timeout: 60_000 });
  await preset.getByRole("button", { name: /What this turns on/ }).click();
  await expect(preset.getByText("Write and edit files in the workspace")).toBeVisible();
  await expect(preset.getByText("Rewind the workspace to a checkpoint")).toBeVisible();
  await capture(page, `${SHOTS}/permissions-build-preset.png`, preset);

  await preset.getByRole("button", { name: /^Turn on \d/ }).click();
  // Gone once every row in it is on, because at that point it is a button that
  // would do nothing.
  await expect(preset).toBeHidden({ timeout: 60_000 });

  // And the four are on, with their decision modes untouched: enabled means
  // available through governance, not unattended.
  const after = await page.evaluate(async () => {
    const response = await fetch("/api/capability-gates", { credentials: "same-origin" });
    return response.ok ? await response.json() : { gates: [] };
  });
  const modes = new Map(
    (after.gates ?? after).map((gate: { capability: string; state: string; decision_mode: string }) => [
      gate.capability,
      gate,
    ]),
  );
  for (const capability of [
    "file_write_execution",
    "patch_apply_execution",
    "git_write_execution",
    "checkpoint_restore_execution",
  ]) {
    const gate = modes.get(capability) as { state: string; decision_mode: string };
    expect(gate.state, capability).toMatch(/^enabled/);
    expect(gate.decision_mode, capability).toBe("ask");
  }
  expect(errors, errors.join("\n")).toEqual([]);
});

test("Settings says what it decides, once, and keeps the tuning one fold away", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);

  // REM-SET-GENERAL — the distinction that changes the answer, said once.
  await page.goto(`${BASE}/#/settings?tab=general`);
  await expect(
    page.getByText("Interface text and formatting only. These do not change what Raiker tells a model."),
  ).toBeVisible({ timeout: 60_000 });
  await expect(page.getByLabel("Default weather location")).toHaveCount(0);
  await capture(page, `${SHOTS}/settings-general-trimmed.png`);

  // REM-SET-APPEARANCE — Theme is why anyone opens this page; density and font
  // are still here, reversible and previewed, one fold away.
  await page.goto(`${BASE}/#/settings?tab=personalisation`);
  const fold = page.getByRole("group").filter({ hasText: "Layout & type" }).first();
  await expect(page.getByRole("radiogroup", { name: "Theme" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("radiogroup", { name: "Density" })).toBeHidden();
  await page.getByText("Layout & type").click();
  await expect(page.getByRole("radiogroup", { name: "Density" })).toBeVisible();
  await expect(fold).toBeVisible();

  // And the weather location arrived here from General.
  const place = page.getByLabel("Default weather location");
  await expect(place).toBeVisible();
  await place.fill("Edinburgh, United Kingdom");
  // The field commits on `change`, which needs a blur — and the save bar only
  // exists once something is dirty, so pressing Save before the blur is asking
  // for a control that has not been rendered yet.
  await place.press("Tab");
  await page.getByRole("button", { name: /^Save/ }).click();
  await expect(page.getByText(/Saved/i).first()).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/settings-personalisation-folded.png`);
  expect(errors, errors.join("\n")).toEqual([]);
});

test("Activity opens on the record, and never hides that it is filtered", async ({ page }) => {
  test.setTimeout(180_000);
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/activity`);

  // REM-ACTIVITY — the raw forms are one press away, not in front of the answer.
  await expect(page.getByLabel("Session id")).toHaveCount(0);
  const toolbar = page.getByRole("button", { name: /Filters and export/ });
  await expect(toolbar).toBeVisible({ timeout: 60_000 });
  await toolbar.click();
  await expect(page.getByLabel("Session id")).toBeVisible();

  // The one thing that is never folded: that this is part of the record.
  await page.getByLabel("Event type").fill("action_proposed");
  await page.getByRole("button", { name: "Apply" }).click();
  const scope = page.getByTestId("activity-scope");
  await expect(scope).toContainText("Showing part of the record");
  await capture(page, `${SHOTS}/activity-advanced-toolbar.png`);

  await scope.getByRole("button", { name: "Show everything" }).click();
  await expect(page.getByTestId("activity-scope")).toHaveCount(0);
  expect(errors, errors.join("\n")).toEqual([]);
});

test("Home opens on the next action, with the commentary under it", async ({ page }) => {
  test.setTimeout(120_000);
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/workbench`);

  const greeting = page.getByRole("heading", { name: /Welcome/ });
  await expect(greeting).toBeVisible({ timeout: 60_000 });
  const start = page.getByRole("navigation", { name: "Start work" });
  const freshness = page.getByText(/^Updated |^Updating…$/).first();
  await expect(start).toBeVisible();
  await expect(freshness).toBeVisible();

  // REM-HOME-03 — the primary action is above the platform-state strip, not
  // below two rows of Raiker describing itself.
  const startBox = await start.boundingBox();
  const freshnessBox = await freshness.boundingBox();
  expect(startBox!.y).toBeLessThan(freshnessBox!.y);
  await capture(page, `${SHOTS}/home-action-first.png`);
  expect(errors, errors.join("\n")).toEqual([]);
});

test("a real turn answers with a table Raiker knows is a table", async ({ page }) => {
  test.setTimeout(420_000);
  test.skip(KEY === "", "needs RAIKER_LIVE_ANTHROPIC_KEY");
  const errors = watchConsole(page);
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "Anthropic",
    keyLabel: "Anthropic API key",
    key: KEY,
    model: MODEL,
  });

  await page.goto(`${BASE}/#/new-chat`);
  // Where an owner chooses the model: the picker beside Send. A workspace that
  // has never chosen one says so rather than guessing (BUG-292), so the choice
  // has to be made before a turn can go.
  await chooseModelForTurn(page, /Haiku 4\.5/i);
  const composer = page.getByPlaceholder("How can I help you today?");
  await expect(composer).toBeVisible({ timeout: 60_000 });
  // The prompt names the data and the destination, not the format. The point is
  // that the model reaches for the declared channel because it was told the
  // channel exists — not that it can copy a JSON blob back.
  //
  // **Found live on 2026-09-15.** Asked for "this as a table and a bar chart",
  // the model called `create_document` and wrote a file. That is the right tool
  // for a file and the wrong one for an answer, and nothing had told it which
  // question it was being asked; the system prompt now says so, and the prompt
  // here says where the answer goes, because that is what a person would say.
  await composer.fill(
    "Three cities and their approximate populations in millions: Tokyo 37, Delhi 33, " +
      "Shanghai 29. Show me that here in this conversation as a table, and then the same " +
      "three as a bar chart. Do not create a file.",
  );
  const send = page.getByRole("button", { name: "Send", exact: true });
  await expect(send).toBeEnabled({ timeout: 120_000 });
  await send.click();

  // BUG-288's interface outcome: a real `<table>`, sortable, announced as one.
  const table = page.getByRole("table").first();
  await expect(table).toBeVisible({ timeout: 300_000 });
  const header = table.getByRole("columnheader").first();
  await expect(header).toHaveAttribute("aria-sort", "none");
  await header.getByRole("button").click();
  await expect(header).toHaveAttribute("aria-sort", "ascending");

  // And the chart, with its own numbers under it — colour and geometry are not
  // a channel everyone has.
  const chart = page.locator("figure.data-chart").first();
  await expect(chart).toBeVisible({ timeout: 60_000 });
  await chart.getByText("The numbers behind this chart").click();
  await expect(chart.getByRole("table")).toBeVisible();

  await capture(page, `${SHOTS}/chat-typed-table-and-chart.png`);
  expect(errors, errors.join("\n")).toEqual([]);
});
