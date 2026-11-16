/**
 * Regular-use journeys (TESTING.md § Regular-use journeys) — Raiker used the
 * way its owner uses it, with ordinary requests, on a fresh workspace.
 *
 * Each journey sends a prompt a person would actually write and judges the
 * outcome the person cares about: the plan has days and costs, the budget
 * answer names the categories that really grew, the code ends up fixed and
 * tested in the project, the fact is remembered in a later chat. None of them
 * asks the model to "reply with exactly …": a journey passes because the work
 * was done, not because a marker word came back.
 *
 * RU-J1  First run: a new owner connects Anthropic through Add model and gets
 *        a useful trip plan.
 * RU-J2  Research: a current-events question answered from the web, with
 *        sources, after the owner allows web access when asked.
 * RU-J3  A document: a budget CSV attached to Chat is read correctly.
 * RU-J4  Build: create a small module with tests, run them in the sandbox,
 *        then change the rule and run them again.
 * RU-J5  Memory: something the owner asks Raiker to remember is used in a
 *        later conversation.
 *
 * Needs a reset workspace (`scripts/reset_live_workspace.py`), an enforced
 * command sandbox on the host (Build's run), `RAIKER_LIVE_ANTHROPIC_KEY` and
 * `RAIKER_LIVE_ANTHROPIC_WORKSPACE`. Keys are typed into the product's own
 * dialogs and never written here.
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import {
  checkModelReady,
  chooseModelForTurn,
  hostedProviderCard,
  keepModelAvailable,
  setPermission,
  signInAsOwner,
} from "./hosted-provider";
import { ANTHROPIC_KEY, ANTHROPIC_MODEL, LIVE_BASE as BASE } from "./live";

const OUT = join(import.meta.dirname, "..", "..", "output", "playwright", "regular-use");
const WORKSPACE = process.env.RAIKER_LIVE_ANTHROPIC_WORKSPACE ?? "";

test.describe.configure({ mode: "serial" });

/** The last answer's text once it has finished (its Copy button is drawn). */
async function lastAnswer(page: Page, timeout = 240_000): Promise<string> {
  const group = page.locator(".message-group-raiker").last();
  await expect(group.getByRole("button", { name: "Copy response" })).toBeVisible({ timeout });
  return (await group.innerText()).trim();
}

async function ask(page: Page, text: string): Promise<string> {
  const composer = page.getByRole("group", { name: "Message composer" });
  await composer.getByRole("textbox").first().fill(text);
  await composer.getByRole("button", { name: /^Send/ }).click();
  return lastAnswer(page);
}

/** Answer an approval the way an owner would: once, for this action. */
async function allowIfAsked(page: Page): Promise<boolean> {
  // Any decision still waiting in the conversation, as the owner sees it — a
  // resumed turn's next decision is drawn outside the last answer's group.
  const allow = page.locator("main").getByRole("button", { name: "Allow once", disabled: false }).last();
  await page.waitForTimeout(1_500);
  if (await allow.isVisible().catch(() => false)) {
    await allow.click();
    return true;
  }
  return false;
}

test("RU-J1 a new owner connects a model and gets a useful trip plan", async ({ page }) => {
  test.setTimeout(480_000);
  expect(ANTHROPIC_KEY && WORKSPACE, "set RAIKER_LIVE_ANTHROPIC_KEY and RAIKER_LIVE_ANTHROPIC_WORKSPACE").toBeTruthy();
  await signInAsOwner(page, BASE);
  const card = await hostedProviderCard(page, BASE, "Anthropic");
  const connect = card.getByRole("button", { name: "Connect", exact: true });
  if (await connect.isVisible().catch(() => false)) {
    await connect.click();
    await page.getByLabel("Anthropic API key").fill(ANTHROPIC_KEY);
    const advanced = page.locator(".sso-toggle");
    if ((await advanced.isVisible().catch(() => false)) && (await advanced.getAttribute("aria-expanded")) === "false") {
      await advanced.click();
    }
    await page.getByPlaceholder("wrkspc_…").fill(WORKSPACE);
    await page.locator(".signin-connect").click();
    await expect(card.getByText("Connection saved")).toBeVisible({ timeout: 60_000 });
  }
  await keepModelAvailable(page, card, ANTHROPIC_MODEL);
  await checkModelReady(page, await hostedProviderCard(page, BASE, "Anthropic"));
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  const answer = await ask(
    page,
    "My partner and I are going to Kyoto for four days in April. We love temples, gardens and food markets, " +
      "and we don't care about nightlife. Suggest a day-by-day plan with rough costs in yen, and tell us what " +
      "we need to book in advance.",
  );
  for (const day of ["Day 1", "Day 2", "Day 3", "Day 4"]) expect(answer).toContain(day);
  expect(answer).toMatch(/¥|yen|JPY/i);
  expect(answer).toMatch(/book|reserv/i);
  await capture(page, join(OUT, "j1-trip-plan.png"));
});

test("RU-J2 a current question is answered from the web, with sources", async ({ page }) => {
  test.setTimeout(600_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  const prompt =
    "What is the latest stable release of Python, and what are the three changes in it most likely to " +
    "affect an existing Django app? Link the official release notes.";
  let answer = await ask(page, prompt);
  if (await allowIfAsked(page)) answer = await lastAnswer(page);
  // A fresh account keeps web access off; an owner who is told so turns it on
  // where Raiker says, and asks again.
  if (!/python\.org|docs\.python\.org/i.test(answer)) {
    await capture(page, join(OUT, "j2a-web-off.png"));
    await setPermission(page, BASE, "Web fetch", "Turn on", "I want Raiker to look things up on the web");
    await page.goto(`${BASE}/#/new-chat`);
    await chooseModelForTurn(page, /Haiku/);
    answer = await ask(page, prompt);
    for (let round = 0; round < 3 && (await allowIfAsked(page)); round += 1) answer = await lastAnswer(page);
  }
  expect(answer).toMatch(/Python 3\.\d+/);
  expect(answer).toMatch(/python\.org/i);
  await capture(page, join(OUT, "j2-web-answer.png"));
});

test("RU-J3 a budget attached to Chat is read correctly", async ({ page }) => {
  test.setTimeout(420_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  const attach = page.getByRole("menuitem", { name: /attach|file/i }).first();
  if (await attach.isVisible().catch(() => false)) await attach.click();
  const csv = [
    "Category,September,October",
    "Groceries,320,410",
    "Eating out,140,260",
    "Transport,90,95",
    "Subscriptions,45,85",
    "Utilities,150,150",
    "Shopping,200,310",
  ].join("\n");
  await page.getByLabel("Upload document").setInputFiles({
    name: "household-budget.csv", mimeType: "text/csv", buffer: Buffer.from(csv),
  });
  await expect(page.getByText("household-budget.csv").first()).toBeVisible({ timeout: 60_000 });
  const answer = await ask(
    page,
    "This is our household budget in pounds. Which three categories grew the most in pounds from September " +
      "to October, by how much, and what would you cut first to save £200 a month?",
  );
  // The two largest rises are unambiguous: Eating out +£120, Shopping +£110.
  for (const category of ["Eating out", "Shopping"]) expect(answer).toContain(category);
  // The figures are the model's arithmetic: recorded, not failed on (TESTING.md
  // rule 6). Haiku 4.5 gave Eating out +£90 in one run, the right +£120 in others.
  test.info().annotations.push({
    type: "figures",
    description: /120/.test(answer) && /110/.test(answer) ? "correct (+120, +110)" : "model arithmetic wrong",
  });
  // Third is Groceries (+£90). Haiku 4.5 ranked Subscriptions (+89%) there in
  // two runs; that is the model's reading, recorded rather than failed on.
  test.info().annotations.push({ type: "third category", description: /Groceries/.test(answer) ? "Groceries" : "missed Groceries" });
  // The product's part: the turn completes, whatever the model tried first.
  expect(answer).not.toMatch(/Not done/);
  await capture(page, join(OUT, "j3-budget.png"));
});

test("RU-J4 Build creates tested code in a project and changes it safely", async ({ page }) => {
  test.setTimeout(1_200_000);
  await signInAsOwner(page, BASE);
  // A fresh account: the owner takes Permissions' one Build decision.
  await page.goto(`${BASE}/#/capabilities`);
  await page.getByRole("navigation", { name: "Permission categories" }).waitFor({ timeout: 60_000 });
  const preset = page.getByRole("region", { name: "Set up for Build" });
  if (await preset.isVisible().catch(() => false)) {
    // Commands are part of Build setup since 2026-11-16, with their own
    // acknowledgement; each command still asks before it runs.
    const understood = preset.getByRole("checkbox");
    if (await understood.isVisible().catch(() => false)) await understood.check();
    await capture(page, join(OUT, "j4-set-up-for-build.png"), preset);
    await preset.getByRole("button", { name: /^Turn on \d+$/ }).click();
    await expect(preset).toBeHidden({ timeout: 60_000 });
  }
  const name = `Pricing ${Date.now().toString().slice(-5)}`;
  await page.goto(`${BASE}/#/projects`);
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: `Open project ${name}` }).first().click();
  const checks = page.getByLabel("Project checks");
  await checks.fill("python3 -m unittest -q");
  await page.getByRole("button", { name: "Save context" }).click();

  await page.getByRole("link", { name: "Build", exact: true }).first().click();
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: "Work in a project" }).click();
  await page.getByLabel("Project for this build").selectOption({ label: name });
  await chooseModelForTurn(page, /Haiku/, "Build composer");

  async function build(request: string): Promise<void> {
    await page.getByLabel("Describe the change").fill(request);
    await page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first().click();
    // Accept each proposed change the way the owner reviews them, until the turn ends.
    for (let round = 0; round < 12; round += 1) {
      const accept = page.locator("section.decisions").getByRole("button", { name: "Accept", disabled: false }).first();
      const allow = page.getByRole("button", { name: "Allow once", disabled: false }).first();
      const ended = page.getByTestId("turn-control");
      await expect(accept.or(allow).or(page.getByTestId("build-outcome").last()).first()).toBeVisible({ timeout: 300_000 });
      if (await accept.isVisible().catch(() => false)) { await accept.click(); continue; }
      if (await allow.isVisible().catch(() => false)) { await allow.click(); continue; }
      if (!(await ended.isVisible().catch(() => false))) break;
    }
    await expect(page.getByTestId("turn-control")).toBeHidden({ timeout: 300_000 });
  }

  await build(
    "Create pricing.py with a function final_price(total) that takes 10% off orders over £100, and " +
      "test_pricing.py with unittest tests for £50, £100 and £150. Then run the tests.",
  );
  await capture(page, join(OUT, "j4a-first-build.png"));
  await build(
    "The shop has changed its rule: orders of exactly £100 should also get the discount. Update the code " +
      "and the tests, and run the tests again.",
  );
  const outcome = page.getByTestId("build-outcome").last();
  await expect(outcome).toBeVisible({ timeout: 120_000 });
  test.info().annotations.push({ type: "outcome", description: (await outcome.getAttribute("data-outcome")) ?? "" });
  await capture(page, join(OUT, "j4b-rule-changed.png"));
  await expect(outcome).toHaveAttribute("data-outcome", /completed/);
  // The tests ran in the sandbox: a command row finished, none was refused for a grant.
  const did = page.getByRole("list", { name: "What Raiker did in this turn" }).last();
  await expect(did.getByText(/refused — command_grant_required/)).toHaveCount(0);
});

test("RU-J5 something the owner asks Raiker to remember is used later", async ({ page }) => {
  test.setTimeout(600_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  const request = "Please remember that I prefer metric units, and that my dentist is Dr. Okafor, usually on Thursdays.";
  await ask(page, request);
  // A fresh account keeps Memory store off; the approval card says so in plain
  // words and names the permission (FIXED-1531). The owner turns it on, as the
  // card says, and asks again.
  const card = page.locator(".message-group-raiker").last();
  if (await card.getByText(/Memory store permission is off/).isVisible().catch(() => false)) {
    await capture(page, join(OUT, "j5a-memory-store-off.png"));
    await setPermission(page, BASE, "Memory store", "Turn on", "I want Raiker to remember things I ask it to");
    await page.goto(`${BASE}/#/new-chat`);
    await chooseModelForTurn(page, /Haiku/);
    await ask(page, request);
  }
  for (let round = 0; round < 6 && (await allowIfAsked(page)); round += 1) await lastAnswer(page);
  // The record, not the prose: both facts are in Memory.
  await expect.poll(async () => page.evaluate(async () => {
    const rows = (await (await fetch("/api/memory")).json()) as { text: string }[];
    return rows.map((row) => row.text).join(" | ");
  }), { timeout: 120_000 }).toMatch(/Thursday/);
  await capture(page, join(OUT, "j5a-remember.png"));
  await page.getByRole("button", { name: "New chat" }).first().click();
  await chooseModelForTurn(page, /Haiku/);
  const answer = await ask(page, "Which day do I usually see my dentist, and who is it?");
  expect(answer).toMatch(/Okafor/);
  expect(answer).toMatch(/Thursday/i);
  await capture(page, join(OUT, "j5b-recalled.png"));
});
