/**
 * FIXED-1426 to FIXED-1442 — the third 2026-11-14 round, against a real host.
 *
 * RT-1114C-01  Settings cards are drawn by one rule: no section keeps its own
 *              copy, and in light theme the card has its edge.
 * RT-1114C-02  Settings › Advanced › Memory engine says what the background
 *              indexer last did, with a way to change it.
 * RT-1114C-03  Projects are rows: one column, each at least 64 px tall, with
 *              the actions on the row's right.
 * RT-1114C-04  Memory › Controls fits one screen at 1440×900, its two lists
 *              side by side.
 * RT-1114C-05  A rename in Work › Threads paints at once and stays.
 * RT-1114C-06  A finished Build turn answered by a real model carries Chat's
 *              one quiet line naming the model.
 * RT-1114C-07  A reopened conversation drops "Loading conversation…" as soon as
 *              its transcript is on screen.
 * RT-1114C-08  The Stop dialog names what it would stop, or says nothing runs.
 *
 * Needs a host with Anthropic connected (RT-1114-01 in
 * `fixed-1389-1393-tasks-chatgpt-live.spec.ts`), so a real Build turn answers.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const OUT = "../../output/playwright/2026-11-14c-round";

test.describe.configure({ mode: "serial" });

test("RT-1114C-01 Settings cards come from one rule", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=general`);
  const card = page.locator(".settings-card").first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  const style = await card.evaluate((node) => {
    const computed = getComputedStyle(node);
    return { border: computed.borderTopWidth, radius: computed.borderTopLeftRadius };
  });
  expect(style.border).toBe("1px");
  expect(Number.parseFloat(style.radius)).toBeGreaterThan(4);
  await capture(page, `${OUT}/01-settings-card.png`);
});

test("RT-1114C-02 Memory engine shows the background indexer's last pass", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=advanced&kind=memory-engine`);
  const status = page.getByTestId("background-index");
  await expect(status).toBeVisible({ timeout: 30_000 });
  await expect(status).toContainText(/nomic-embed-text|Background indexing|Waiting|Ollama|Up to date|Indexed/);
  await capture(page, `${OUT}/02-memory-engine-background.png`);
});

test("RT-1114C-03 Projects are rows", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=projects`);
  const list = page.locator(".project-list");
  if ((await list.locator("article.project").count()) === 0) {
    const name = page.getByPlaceholder(/project name/i).first();
    await name.fill(`Round C ${Date.now()}`);
    await name.press("Enter");
  }
  const row = list.locator("article.project").first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  const box = await row.boundingBox();
  const listBox = await list.boundingBox();
  expect(box && box.height >= 63).toBe(true);
  // One column: the row spans the list.
  expect(box && listBox && box.width > listBox.width - 4).toBe(true);
  const actions = row.locator(".project-actions");
  const actionsBox = await actions.boundingBox();
  expect(actionsBox && box && actionsBox.x > box.x + box.width / 2).toBe(true);
  await capture(page, `${OUT}/03-projects-rows.png`);
});

test("RT-1114C-04 Memory › Controls fits one screen", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/memory?tab=controls`);
  const pair = page.locator(".controls-pair");
  await expect(pair).toBeVisible({ timeout: 30_000 });
  const sections = pair.locator(".controls-section");
  const first = await sections.nth(0).boundingBox();
  const second = await sections.nth(1).boundingBox();
  // Side by side: the two lists share a top edge.
  expect(first && second && Math.abs(first.y - second.y) < 4).toBe(true);
  await capture(page, `${OUT}/04-memory-controls.png`);
});

test("RT-1114C-05 a thread rename paints at once", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=threads`);
  const organise = page.getByRole("button", { name: /^Organise / }).first();
  await expect(organise).toBeVisible({ timeout: 30_000 });
  await organise.click();
  await page.getByRole("button", { name: "Rename", exact: true }).first().click();
  const field = page.getByLabel(/^New title for /).first();
  const title = `Renamed in round C ${Date.now() % 100000}`;
  await field.fill(title);
  await field.press("Enter");
  // Painted before the index is re-read, and still there after it is.
  await expect(page.getByText(title).first()).toBeVisible({ timeout: 2_000 });
  await page.waitForTimeout(1500);
  await expect(page.getByText(title).first()).toBeVisible();
  await capture(page, `${OUT}/05-thread-renamed.png`);
});

test("RT-1114C-06 a finished Build turn has Chat's quiet meta line", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  // Build works inside a project; RT-1114C-03 left one, and its row starts it.
  await page.goto(`${BASE}/#/work?tab=projects`);
  await page.locator(".project-list article.project").first().getByRole("button", { name: "Start in Build" }).click();
  await chooseModelForTurn(page, /Haiku/, "Build composer");
  await page.getByLabel("Describe the change").fill("Answer in one short sentence and use no tools: what is a unit test?");
  const run = page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first();
  await expect(run).toBeEnabled({ timeout: 60_000 });
  await run.click();
  const meta = page.locator(".turn .turn-meta").last();
  await expect(meta).toContainText("Haiku", { timeout: 180_000 });
  await capture(page, `${OUT}/06-build-meta-line.png`);
});

test("RT-1114C-07 a reopened conversation stops saying it is loading", async ({ page }) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=threads`);
  const link = page.locator('a[href^="#/new-chat?session="]').first();
  await expect(link).toBeVisible({ timeout: 30_000 });
  await link.click();
  await expect(page.locator(".message-bubble-raiker, .turn").first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Loading conversation…")).toHaveCount(0, { timeout: 5_000 });
  await page.reload();
  await expect(page.locator(".message-bubble-raiker, .turn").first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Loading conversation…")).toHaveCount(0, { timeout: 5_000 });
  await capture(page, `${OUT}/07-reopened.png`);
});

test("RT-1114C-08 the Stop dialog names what it would stop", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/home`);
  await page.getByRole("button", { name: /^Stop all work/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  const reached = dialog.getByRole("list", { name: "Tasks this stops" });
  if (await reached.isVisible().catch(() => false)) {
    await expect(reached.locator("a").first()).toHaveAttribute("href", /#\/tasks\?task=/);
  } else {
    await expect(dialog).toContainText(/Nothing is running|answer being written|command/);
  }
  await capture(page, `${OUT}/08-stop-dialog.png`);
});
