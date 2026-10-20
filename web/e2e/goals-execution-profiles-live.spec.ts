/**
 * PA-D01 / PA-D02 / PA-D06, against a running host: an execution profile made
 * in Settings, a goal drafted, accepted, refused by Private local and run under
 * Balanced on a real hosted model, its outcome assessed from evidence, Home's
 * Goals board, and Stop.
 *
 * Prerequisites:
 *   1. A fresh workspace served by
 *      `python -m raiker.api.serve --workspace <ws> --port 8765 --no-browser`.
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` (and, for an identity-linked key,
 *      `RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID`) in this run's environment only.
 *      The key is typed into the product's own dialog; none is written here.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Goals and execution
 * profiles"): RT-GOAL-01 … RT-GOAL-07.
 */
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { settled } from "./destinations";
import { chooseModelForTurn, hostedProviderCard, keepModelAvailable, signInAsOwner } from "./hosted-provider";
import { ANTHROPIC_KEY as KEY, ANTHROPIC_MODEL as MODEL, LIVE_BASE as BASE, sendTurn } from "./live";

test.describe.configure({ mode: "serial" });

const WORKSPACE_ID = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID ?? "";
const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-20-goals-execution-profiles";
const GOAL = "Pack for a day hike";

async function openGoals(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/work?tab=goals`);
  await settled(page);
}

async function openProfiles(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/settings?tab=execution-profiles`);
  await settled(page);
  await expect(page.getByRole("heading", { name: "Execution profiles" })).toBeVisible();
}

async function openGoal(page: Page, title: string): Promise<void> {
  await openGoals(page);
  await page.getByRole("button", { name: new RegExp(title) }).first().click();
  await expect(page.getByTestId("goal-detail")).toBeVisible();
}

async function draftGoal(page: Page, title: string): Promise<void> {
  await openGoals(page);
  await page.getByRole("button", { name: "New goal" }).first().click();
  await page.getByLabel("Outcome").fill(title);
  await chooseModelForTurn(page, /Haiku|claude/i, "Goal model");
  await page.getByLabel("Criterion 1 text").fill("A packing list exists");
  await page.getByRole("button", { name: "Add criterion" }).click();
  await page.getByLabel("Criterion 2 text").fill("I am happy with it");
  await page.getByLabel("How criterion 2 is met").selectOption({ label: "You confirm it" });
  await page.getByLabel("Step 1 title").fill("List");
  await page.getByLabel("Step 1 instruction").fill(
    "Reply with a packing list of exactly three items for a day hike, one per line. Use no tools.",
  );
  await page.getByRole("button", { name: "Save as draft" }).click();
  const detail = page.getByTestId("goal-detail");
  await expect(detail.getByRole("heading", { name: title })).toBeVisible();
  await expect(detail.getByText(/Steps run on claude-haiku/)).toBeVisible();
}

test("RT-GOAL-01 — Anthropic connects through the UI and a turn chooses its model", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(KEY);
    if (WORKSPACE_ID) {
      await page.getByRole("button", { name: "Advanced" }).click();
      await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE_ID);
    }
    await page.locator(".signin-connect").click();
  }
  await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  await keepModelAvailable(page, card, MODEL);
  // A goal step runs on the owner's selected model, so one turn selects it.
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku|claude/i);
  await sendTurn(page, "Say ready.");
  await expect(page.getByRole("button", { name: "Send this message again" }).last()).toBeVisible({ timeout: 180_000 });
});

test("RT-GOAL-02 — without a profile a goal is a draft that cannot be accepted", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await openGoals(page);
  await expect(page.getByTestId("goal-profile-line")).toContainText("No execution profile yet");
  await draftGoal(page, GOAL);
  const detail = page.getByTestId("goal-detail");
  await expect(detail.getByRole("button", { name: "Start" })).toHaveCount(0);
  await detail.getByRole("button", { name: "Accept plan" }).click();
  await expect(detail.getByRole("alert")).toContainText("Choose an execution profile in Settings");
  await capture(page, `${SHOTS}/01-draft-needs-profile.png`, detail);
});

test("RT-GOAL-03 — Private local is made in Settings and refuses the hosted model by name", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await openProfiles(page);
  await page.getByRole("button", { name: "Create Private local" }).click();
  await expect(page.getByText("Created Private local.")).toBeVisible();
  await expect(page.getByText("Active", { exact: true })).toBeVisible();
  await capture(page, `${SHOTS}/02-settings-private-local.png`);
  await openGoal(page, GOAL);
  const detail = page.getByTestId("goal-detail");
  await detail.getByRole("button", { name: "Accept plan" }).click();
  await expect(detail.getByText("Ready to start")).toBeVisible();
  await detail.getByRole("button", { name: "Start" }).click();
  await expect(detail.getByRole("alert")).toContainText("anthropic (hosted)");
  await capture(page, `${SHOTS}/03-private-local-refuses-hosted.png`, detail);
});

test("RT-GOAL-04 — under Balanced the step runs on the real model and the goal waits for the owner", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(420_000);
  await signInAsOwner(page, BASE);
  await openProfiles(page);
  await page.getByRole("button", { name: "Create Balanced" }).click();
  await expect(page.getByText("Created Balanced.")).toBeVisible();
  const balanced = page.getByRole("listitem").filter({ hasText: "Local and hosted models" }).first();
  await balanced.getByRole("button", { name: "Make active" }).click();
  await expect(page.getByText("Balanced is now active for new goals.")).toBeVisible();
  await openGoal(page, GOAL);
  const detail = page.getByTestId("goal-detail");
  await detail.getByRole("button", { name: "Start" }).click();
  await expect(detail.getByText(/Working|Partly done/).first()).toBeVisible({ timeout: 30_000 });
  // The step is an ordinary scheduled task: the host's tick claims and runs it.
  await expect(async () => {
    await openGoal(page, GOAL);
    await expect(page.getByTestId("goal-detail").getByText("Partly done")).toBeVisible({ timeout: 5_000 });
  }).toPass({ timeout: 300_000, intervals: [5_000] });
  await expect(detail.getByText("Its steps finished")).toBeVisible();
  await expect(detail.getByText(/Balanced \(version 1\)/)).toBeVisible();
  await expect(detail.getByText(/Answered by: anthropic — all within the profile/)).toBeVisible();
  await capture(page, `${SHOTS}/04-partly-done-steps-finished.png`, detail);
  // PA-D02: Balanced keeps personal memory off a hosted model, and the step
  // recorded that it was withheld.
  const goals = await page.evaluate(async () => (await fetch("/api/goals", { credentials: "include" })).json());
  const goal = goals.goals.find((g: { title: string }) => g.title === "Pack for a day hike");
  const started = goal.events.find((e: { kind: string }) => e.kind === "goal_step_started");
  expect(started.detail.memory_withheld).toBe(true);
});

test("RT-GOAL-05 — Home lists it under Needs you, and confirming completes it", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/home`);
  await settled(page);
  const board = page.getByTestId("home-goals");
  await expect(board.getByText("Needs you")).toBeVisible({ timeout: 30_000 });
  await expect(board.getByRole("link", { name: GOAL })).toBeVisible();
  await capture(page, `${SHOTS}/05-home-needs-you.png`, board);
  await board.getByRole("link", { name: GOAL }).click();
  const detail = page.getByTestId("goal-detail");
  await expect(detail).toBeVisible();
  await detail.getByLabel("Note for I am happy with it").fill("Checked the list");
  await detail.getByRole("button", { name: "Confirm met" }).click();
  await expect(detail.getByText("Completed", { exact: true })).toBeVisible();
  await expect(detail.getByText(/Confirmed by you: Checked the list/)).toBeVisible();
  await capture(page, `${SHOTS}/06-completed.png`, detail);
});

test("RT-GOAL-06 — a profile change pauses a running goal, and Stop stops every step", async ({ page }) => {
  test.skip(KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is unset");
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  const second = "Stop me";
  await draftGoal(page, second);
  const detail = page.getByTestId("goal-detail");
  await detail.getByRole("button", { name: "Accept plan" }).click();
  await detail.getByRole("button", { name: "Start" }).click();
  await expect(detail.getByText(/Working|Waiting|Partly done/).first()).toBeVisible({ timeout: 30_000 });
  // Stop at once, before the host's tick finishes the step.
  await detail.getByRole("button", { name: "Stop goal" }).click();
  await detail.getByRole("button", { name: "Stop every step now" }).click();
  await expect(detail.getByText("Stopped", { exact: true })).toBeVisible();
  await expect(detail.getByRole("alert")).toContainText(/Stopped\. \d+ steps? had finished/);
  await capture(page, `${SHOTS}/07-stopped.png`, detail);
});

test("RT-GOAL-07 — editing the active profile writes a new version and says what it paused", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await openProfiles(page);
  const balanced = page.getByRole("listitem").filter({ hasText: "Local and hosted models" }).first();
  await balanced.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Step runs per goal").fill("5");
  await page.getByRole("button", { name: "Save as version 2" }).click();
  await expect(page.getByText(/Saved version 2\./)).toBeVisible();
  await expect(balanced.getByText("version 2")).toBeVisible();
  await capture(page, `${SHOTS}/08-profile-version-2.png`);
});
