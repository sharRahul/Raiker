/** 03 Composer execution states (2026-11-07) against a running host.
 *
 * Real turns answered by the hosted model connected beforehand through Models
 * (run `models-provider-validation-live.spec.ts` first with a private
 * `RAIKER_LIVE_CREDENTIALS_FILE`). Stop and follow-ups go through the governed
 * `POST /api/interrupts`; a pill turns Read only on the runtime's own
 * `turn_steered` event. Nothing is seeded or mocked.
 */
import { expect as baseExpect, test, type Page } from "@playwright/test";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";
import { capture } from "./capture";

const expect = baseExpect.configure({ timeout: 30_000 });
const SHOTS = "../../output/playwright/2026-11-07-composer-execution-states";
test.describe.configure({ mode: "serial", timeout: 300_000 });

// Several sequential, read-only tool calls: long enough to queue into, and
// each step settles into the drawer.
const LONG_TURN =
  "Use the weather tool five separate times, one call after another and never in parallel: " +
  "first for Paris, then Tokyo, then Reykjavik, then Lima, then Nairobi. Before each call, write one " +
  "sentence saying which city is next. After all five, give one line per city.";

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
});

async function newChat(page: Page) {
  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByRole("group", { name: "Message composer", exact: true });
  await expect(composer).toBeVisible({ timeout: 60_000 });
  return composer;
}

test("RT-EXEC-01: while a turn runs, Send is Stop safely, the prompt queues a follow-up and the runtime marks it read", async ({ page }) => {
  const composer = await newChat(page);
  const prompt = composer.getByLabel("Prompt", { exact: true });
  await prompt.fill(LONG_TURN);
  await composer.getByRole("button", { name: "Send", exact: true }).click();

  // Send morphs in place; there is no second Stop button.
  const stop = composer.getByRole("button", { name: "Stop safely", exact: true });
  await expect(stop).toBeVisible();
  await expect(composer.getByRole("button", { name: /^Send$/ })).toHaveCount(0);
  await expect(prompt).toBeEnabled();
  await expect(prompt).toHaveAttribute("placeholder", /Add an instruction/);

  // Queue at once, while the turn is surely still running.
  await prompt.fill("Also say which city is coldest.");
  const queue = composer.getByRole("button", { name: "Queue", exact: true });
  await expect(queue).toBeVisible();
  await expect(stop).toHaveCount(0);
  const steered = page.waitForResponse((r) => r.url().endsWith("/api/interrupts") && r.request().method() === "POST", { timeout: 15_000 });
  await prompt.press("Enter");
  expect((await steered).status()).toBe(200);
  await expect(prompt).toHaveValue("");
  // The working line counts from Send.
  const line = composer.getByTestId("turn-control").getByRole("status");
  await expect(line).toContainText(/\d+:\d\d/);
  const pills = composer.getByRole("list", { name: "Follow-ups for the running turn" });
  await expect(pills).toContainText("Also say which city is coldest.");
  await expect(pills).toContainText(/Queued|Read/);
  await capture(page, `${SHOTS}/01-running-queued.png`);

  // The step drawer, once the turn has made a call.
  const steps = composer.getByRole("button", { name: /\d+ steps?/ });
  await expect(steps).toBeVisible({ timeout: 90_000 });
  await steps.click();
  await expect(steps).toHaveAttribute("aria-expanded", "true");
  const drawer = composer.getByRole("list", { name: "Steps in this turn" });
  await expect(drawer).toContainText(/Weather|weather/);
  await expect(drawer).toContainText(/Done|Running/);
  await capture(page, `${SHOTS}/02-step-drawer.png`);

  // Read only when the runtime said so; the turn then ends and Send returns.
  await expect(pills).toContainText("Read", { timeout: 120_000 });
  await capture(page, `${SHOTS}/03-follow-up-read.png`);
  await expect(composer.getByRole("button", { name: "Send", exact: true })).toBeVisible({ timeout: 120_000 });
  await expect(drawer).toHaveCount(0);
  await expect(pills).toHaveCount(0);
  const answer = page.locator(".message-bubble-raiker").last();
  await expect(answer).toContainText(/coldest/i, { timeout: 60_000 });
  await capture(page, `${SHOTS}/04-answered.png`);
});

test("RT-EXEC-02: Stop safely ends the turn at a boundary, and Continue from last step sends a visible continuation", async ({ page }) => {
  const composer = await newChat(page);
  const prompt = composer.getByLabel("Prompt", { exact: true });
  await prompt.fill(LONG_TURN);
  await composer.getByRole("button", { name: "Send", exact: true }).click();
  // Stop once the first call is under way, so there is a step to continue from.
  await expect(composer.getByRole("button", { name: /\d+ steps?/ })).toBeVisible({ timeout: 90_000 });
  const stopped = page.waitForResponse((r) => r.url().endsWith("/api/interrupts") && r.request().method() === "POST");
  await composer.getByRole("button", { name: "Stop safely", exact: true }).click();
  const body = (await stopped).request().postDataJSON() as Record<string, unknown>;
  expect(body.action_type).toBe("cancel");
  await expect(composer.getByText(/Stop requested/)).toBeVisible();
  await capture(page, `${SHOTS}/05-stopping.png`);

  await expect(page.getByText(/Stopped at your request/)).toBeVisible({ timeout: 120_000 });
  const resume = page.getByRole("button", { name: "Continue from last step", exact: true });
  await expect(resume).toBeEnabled();
  await capture(page, `${SHOTS}/06-stopped-continue.png`);
  await resume.click();
  await expect(page.getByText(/^Continue from where you stopped/).first()).toBeVisible();
  await expect(composer.getByRole("button", { name: "Send", exact: true })).toBeVisible({ timeout: 180_000 });
  await expect(page.locator(".message-bubble-raiker").last()).toContainText(/Reykjavik|Tokyo|Paris/i, { timeout: 60_000 });
  await capture(page, `${SHOTS}/07-continued.png`);
});

test("RT-EXEC-03: an unread follow-up says so after the turn and can become the next message", async ({ page }) => {
  const composer = await newChat(page);
  const prompt = composer.getByLabel("Prompt", { exact: true });
  // A plain answer: no tool boundary, so a follow-up cannot be read by this turn.
  await prompt.fill("Write four short sentences about rivers. Use no tools.");
  await composer.getByRole("button", { name: "Send", exact: true }).click();
  await expect(composer.getByRole("button", { name: "Stop safely", exact: true })).toBeVisible();
  await prompt.fill("Now one about lakes.");
  await prompt.press("Enter");
  const pills = composer.getByRole("list", { name: "Follow-ups for the running turn" });
  await expect(pills).toContainText("Now one about lakes.");
  await expect(composer.getByRole("button", { name: "Send", exact: true })).toBeVisible({ timeout: 120_000 });
  await expect(pills).toContainText("Not read");
  await capture(page, `${SHOTS}/08-not-read.png`);
  await pills.getByRole("button", { name: "Use as next message", exact: true }).click();
  await expect(prompt).toHaveValue("Now one about lakes.");
  await expect(pills).toHaveCount(0);
});

test("RT-EXEC-04: the running bar in dark, and the shortcut hint while running", async ({ page }) => {
  const composer = await newChat(page);
  await page.evaluate(() => { document.documentElement.dataset.theme = "dark"; });
  const prompt = composer.getByLabel("Prompt", { exact: true });
  await prompt.fill("Write three short sentences about mountains. Use no tools.");
  await composer.getByRole("button", { name: "Send", exact: true }).click();
  await expect(composer.getByRole("button", { name: "Stop safely", exact: true })).toBeVisible();
  await expect(prompt).toHaveAttribute("title", /queues a follow-up for the running turn/);
  await capture(page, `${SHOTS}/09-running-dark.png`);
  await expect(composer.getByRole("button", { name: "Send", exact: true })).toBeVisible({ timeout: 120_000 });
});

test("RT-EXEC-05: Build's Run becomes Stop safely and Queue, with the same running bar", async ({ page }) => {
  const name = "Execution states build";
  await page.goto(`${BASE}/#/work?tab=projects`);
  await expect(page.getByRole("tab", { name: /^Active/ }).or(page.getByText("No projects yet", { exact: true }))).toBeVisible();
  if (await page.getByRole("button", { name: `Open project ${name}`, exact: true }).count() === 0) {
    await page.getByRole("textbox", { name: "New project name", exact: true }).fill(name);
    await page.getByRole("button", { name: "Create project", exact: true }).click();
    await expect(page.getByRole("button", { name: `Open project ${name}`, exact: true })).toBeVisible();
  }
  await page.goto(`${BASE}/#/build`);
  const composer = page.getByRole("group", { name: "Build composer", exact: true });
  await expect(composer).toBeVisible({ timeout: 60_000 });
  await composer.getByRole("button", { name: "Add to this turn", exact: true }).click();
  await page.getByRole("menuitem", { name: /^Work in a project/ }).click();
  await page.getByLabel("Project for this build").selectOption({ label: name });
  await chooseModelForTurn(page, /haiku/i, "Build composer");
  const prompt = composer.getByLabel("Describe the change", { exact: true });
  await prompt.fill("Explain in five short paragraphs how you would plan a small refactor. Do not use tools and change nothing.");
  await composer.locator('button[data-mode="send"]').click();
  const stop = composer.getByRole("button", { name: "Stop safely", exact: true });
  await expect(stop).toBeVisible();
  await expect(composer.getByTestId("turn-control")).toBeVisible();
  await prompt.fill("Keep it under 100 words.");
  await expect(composer.getByRole("button", { name: "Queue", exact: true })).toBeVisible();
  await expect(stop).toHaveCount(0);
  await capture(page, `${SHOTS}/10-build-queue.png`);
  await prompt.fill("");
  await expect(stop).toBeVisible();
  await capture(page, `${SHOTS}/11-build-running.png`);
  await expect(composer.locator('button[data-mode="send"]')).toBeVisible({ timeout: 120_000 });
});
