import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner, useHostedModel } from "./hosted-provider";

/**
 * The 2026-09-20 P2 round, live: the eleven §18.3 rows that were still open.
 *
 * Every one of these is a reading-order change, and a reading order is the one
 * property a unit test is least able to prove — a component rendered on its own
 * has no shell around it, no other sections competing for the column, and no
 * owner scrolling past four lists to reach the fifth. So each scenario here
 * drives the real page in the real shell and captures what an owner sees.
 *
 * Preconditions:
 *   1. `raiker-web` on 127.0.0.1:8765
 *   2. `RAIKER_LIVE_ANTHROPIC_KEY` in the environment (entered through the UI)
 */
const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";
const SHOTS = join(import.meta.dirname, "..", "..", "docs", "screenshots", "2026-09-20-p2-rows");
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const MODEL = "claude-haiku-4-5-20251001";
const MODEL_LABEL = /Haiku 4\.5/;

test.describe.configure({ mode: "serial" });

// Connecting a provider, pinning a model and taking a readiness check against a
// real API is minutes of work, not the default thirty seconds; so is a turn.
test.setTimeout(420_000);

test.skip(ANTHROPIC_KEY === "", "RAIKER_LIVE_ANTHROPIC_KEY is not set for this round.");

test("the owner's provider is connected, and a model is ready to answer", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await useHostedModel(page, BASE, {
    provider: "anthropic",
    keyLabel: "API key",
    key: ANTHROPIC_KEY,
    model: MODEL,
  });
  await capture(page, join(SHOTS, "00-anthropic-connected.png"));
});

/**
 * REM-CHAT-01 — the turn's own evidence, under the turn.
 *
 * The properties only a real turn can show: the inspector is *closed* while the
 * answer is being read, it carries the coordinate the runtime actually issued,
 * and opening it reads that turn's governed events rather than a fixture's.
 */
test("REM-CHAT-01: a settled turn carries its own evidence, closed until asked for", async ({
  page,
}) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, MODEL_LABEL);

  const prompt = page.getByPlaceholder("How can I help you today?");
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await prompt.fill("In one short sentence, what is a governed action?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".message-bubble-raiker").last()).toBeVisible({ timeout: 240_000 });

  const evidence = page.locator("details.turn-evidence").last();
  await expect(evidence).toBeVisible({ timeout: 60_000 });
  // Closed: the answer keeps the primary reading order.
  expect(await evidence.evaluate((node: HTMLDetailsElement) => node.open)).toBe(false);
  await capture(page, join(SHOTS, "01-chat-evidence-closed.png"), evidence);

  await evidence.locator("summary").click();
  // The coordinate the runtime issued, not one the browser made up.
  const coordinate = evidence.locator(".coordinate code");
  await expect(coordinate).toBeVisible({ timeout: 30_000 });
  expect((await coordinate.innerText()).trim()).not.toBe("");
  // And the record behind it, read on open.
  await expect(evidence.getByText("What the runtime recorded")).toBeVisible();
  await expect(evidence.locator(".events li").first()).toBeVisible({ timeout: 60_000 });
  const record = evidence.getByRole("link", { name: "Open the full record" });
  await expect(record).toHaveAttribute("href", /#\/sessions\?session=.+&turn=.+/);
  await capture(page, join(SHOTS, "02-chat-evidence-open.png"), evidence);
});

/**
 * REM-SET-GIT — what the credential is for, before the field that asks for it.
 */
test("REM-SET-GIT: the scope is stated above the secret", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=git-credential`);

  const scope = page.getByRole("heading", { name: /Where it may be used/ });
  await expect(scope).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("github.com", { exact: true })).toBeVisible();
  await expect(page.getByText("Push a branch you approved")).toBeVisible();

  // The ordering is the row. Measured from the rendered page rather than
  // asserted from the source, because that is what an owner reads.
  const scopeBox = await scope.boundingBox();
  const fieldBox = await page.getByLabel("GitHub token").boundingBox();
  expect(scopeBox).not.toBeNull();
  expect(fieldBox).not.toBeNull();
  expect(fieldBox!.y).toBeGreaterThan(scopeBox!.y);

  await expect(page.getByText(/Not this machine's credential manager/)).toBeVisible();
  await capture(page, join(SHOTS, "03-git-credential-scope-first.png"));
});

/**
 * REM-SET-WEB — deployment configuration as read-only detail that names its remedy.
 */
test("REM-SET-WEB: what this page cannot change says who can", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=web-access`);

  await expect(page.getByText(/rules in force/)).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByText(/No setting on this page and no approval lifts it/),
  ).toBeVisible();

  const fixed = page.locator("details.fixed-card");
  await expect(fixed).toBeVisible();
  expect(await fixed.evaluate((node: HTMLDetailsElement) => node.open)).toBe(false);
  await fixed.locator("summary").click();
  // Both sources say who can change them, and each says something different:
  // the environment list is set before launch, the built-in list ships with the
  // build. This host is started with one environment rule so the card has both.
  await expect(page.getByText(/whoever starts Raiker on this machine/)).toBeVisible();
  // A regex, and one that does not straddle a line break: Playwright matches a
  // regular expression against the text as rendered, newlines and all.
  await expect(page.getByText(/Part of this build\./)).toBeVisible();
  await capture(page, join(SHOTS, "04-web-access-read-only-detail.png"));
});

/**
 * REM-SET-RUNTIME — the execution target above the tuning.
 */
test("REM-SET-RUNTIME: ports and windows sit below what they tune", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=runtime`);

  const targets = page.getByText("Local, remote, and cloud environments");
  await expect(targets).toBeVisible({ timeout: 30_000 });
  const advanced = page.locator("section.advanced details");
  await expect(advanced).toBeVisible();
  expect(await advanced.evaluate((node: HTMLDetailsElement) => node.open)).toBe(false);

  const targetBox = await targets.boundingBox();
  const advancedBox = await advanced.boundingBox();
  expect(advancedBox!.y).toBeGreaterThan(targetBox!.y);

  await advanced.locator("summary").click();
  await expect(page.getByLabel(/Re-confirm a model check after/)).toBeVisible();
  await capture(page, join(SHOTS, "05-runtime-advanced.png"));
});

/**
 * REM-MEM-03 — the engine's controls out of the personal review.
 */
test("REM-MEM-03: Memory keeps the health, Settings keeps the engine", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/memory?tab=recall`);

  const repair = page.getByRole("link", { name: /Change the recall backend/ });
  await expect(repair).toBeVisible({ timeout: 30_000 });
  // The controls themselves are not on the review page any more.
  await expect(page.getByLabel("Recall backend")).toHaveCount(0);
  await capture(page, join(SHOTS, "06-memory-recall-health.png"));

  await repair.click();
  await expect(page.getByRole("heading", { name: "Memory engine" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByLabel("Recall backend")).toBeVisible();
  await capture(page, join(SHOTS, "07-settings-memory-engine.png"));
});

/**
 * REM-TASK-01 — when it runs, and how it runs, asked as two questions.
 */
test("REM-TASK-01: timing and run mode are two controls, and a schedule previews", async ({
  page,
}) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/tasks`);

  const when = page.getByRole("group", { name: "When to run" });
  await expect(when).toBeVisible({ timeout: 30_000 });
  await expect(when.getByRole("button", { name: "Now" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  // The run-mode question is asked where the runtime has an answer for it.
  await expect(page.getByRole("group", { name: "How it runs" })).toBeVisible();
  await capture(page, join(SHOTS, "08-tasks-two-questions.png"));

  await when.getByRole("button", { name: "Repeating" }).click();
  // A background agent starts now, so that question is no longer asked.
  await expect(page.getByRole("group", { name: "How it runs" })).toHaveCount(0);
  await page.getByRole("button", { expanded: false, name: /Runs|Once|Daily|Hourly|Weekly|Every/ }).click();

  const first = page.getByLabel("First run");
  await expect(first).toBeVisible();
  await first.fill("2027-01-04T09:00");
  const preview = page.getByRole("status", { name: "Next runs" });
  await expect(preview).toBeVisible({ timeout: 30_000 });
  await expect(preview.locator("li")).toHaveCount(3);
  await expect(page.getByText(/Times are /)).toBeVisible();
  await capture(page, join(SHOTS, "09-tasks-schedule-preview.png"));
});

/**
 * REM-PROJ-02 — the project's sections, and an unsaved edit that says so.
 */
test("REM-PROJ-02: a project is five sections, and it opens on Overview", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/projects`);

  const name = `P2 round ${Date.now()}`;
  const field = page.getByLabel(/Project name|New project/i).first();
  await expect(field).toBeVisible({ timeout: 30_000 });
  await field.fill(name);
  await page.getByRole("button", { name: /^Create/ }).first().click();

  const open = page.getByRole("button", { name: new RegExp(`open project ${name}`, "i") });
  await expect(open).toBeVisible({ timeout: 30_000 });
  await open.click();

  const sections = page.getByRole("tablist", { name: "Project sections" });
  await expect(sections).toBeVisible({ timeout: 30_000 });
  await expect(sections.getByRole("tab", { name: "Overview" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await capture(page, join(SHOTS, "10-project-overview.png"));

  // An unsaved edit is kept, and the page says where it is.
  await page.getByLabel("Project instructions").fill("Prefer short answers.");
  await sections.getByRole("tab", { name: "Evidence" }).click();
  await expect(page.getByText(/Project context has unsaved changes/)).toBeVisible();
  await capture(page, join(SHOTS, "11-project-unsaved-context.png"));

  await sections.getByRole("tab", { name: "Overview" }).click();
  await expect(page.getByLabel("Project instructions")).toHaveValue("Prefer short answers.");
});

/**
 * REM-BUILD-01 — the workbench comes back where it was left.
 *
 * Only a real reload shows this: the state is written to this browser's own
 * storage, and a component test has no reload to survive.
 */
test("REM-BUILD-01: the workbench is where the owner left it after a reload", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/build`);

  const terminal = page.getByRole("button", { name: /terminal/i }).first();
  await expect(terminal).toBeVisible({ timeout: 60_000 });
  await terminal.click();
  const tab = page.getByRole("tab", { name: /Terminal/ });
  await expect(tab).toHaveAttribute("aria-selected", "true", { timeout: 30_000 });
  await capture(page, join(SHOTS, "12-build-workbench-terminal.png"));

  await page.reload();
  await expect(page.getByRole("tab", { name: /Terminal/ })).toHaveAttribute(
    "aria-selected",
    "true",
    { timeout: 60_000 },
  );
  await capture(page, join(SHOTS, "13-build-workbench-after-reload.png"));
});
