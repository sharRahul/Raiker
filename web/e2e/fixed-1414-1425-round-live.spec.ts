/**
 * FIXED-1414 to FIXED-1425 — the second 2026-11-14 round, against a real host.
 *
 * RT-1114B-01  Choosing a model in one surface makes it the default everywhere
 *              else when none was chosen: Models names it in its header, and
 *              Build and Tasks no longer say "No model is chosen".
 * RT-1114B-02  Tasks: the list reads top-down and the composer is docked below
 *              it, with the templates directly above the composer.
 * RT-1114B-03  Goals carries the shared toolbar, no second title, and one
 *              New goal while empty. Approvals keeps its filters, Refresh and
 *              guide on one row.
 * RT-1114B-04  Threads rows draw Evidence and Organise as quiet buttons at the
 *              row's right edge.
 * RT-1114B-05  A Chat answer is the page, not a grey bubble; one quiet line
 *              under it names the model and cost; "nothing recalled" is gone;
 *              the context meter counts the request's whole prompt.
 * RT-1114B-06  The content area draws no focus frame after a reload, and the
 *              Build Terminal panel lists its facts one per line.
 * RT-1114B-07  Settings › Voice: Preview speaks with the installed Kokoro and
 *              Test reports that it spoke.
 *
 * Needs a host with Anthropic connected (RT-1114-01 in
 * `fixed-1389-1393-tasks-chatgpt-live.spec.ts`). RT-1114B-07 needs the
 * Balanced voice profile installed through Settings › Voice.
 */
import { expect, test } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const OUT = "../../output/playwright/2026-11-14b-round";

test.describe.configure({ mode: "serial" });

test("RT-1114B-01 the first model chosen anywhere is the default everywhere", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/build`);
  await chooseModelForTurn(page, /Haiku/, "Build composer");
  await page.goto(`${BASE}/#/models`);
  const header = page.locator("#profile-card-title");
  await expect(header).toBeVisible({ timeout: 30_000 });
  await expect(header).not.toHaveText("No default model is chosen");
  await expect(header).toContainText("Haiku");
  await capture(page, `${OUT}/01-models-header.png`);
  await page.goto(`${BASE}/#/tasks`);
  await expect(page.getByRole("group", { name: "Plan work" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("No model is chosen.")).toHaveCount(0);
});

test("RT-1114B-02 Tasks lists the work above a docked composer", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/tasks`);
  const composer = page.getByRole("group", { name: "Plan work" });
  await expect(composer).toBeVisible({ timeout: 30_000 });
  const summary = page.locator(".tasks div.summary").first();
  await expect(summary).toBeVisible();
  const list = await summary.boundingBox();
  const dock = await composer.boundingBox();
  expect(list && dock && dock.y > list.y).toBe(true);
  const templates = page.getByRole("group", { name: "Start from a template" });
  if (await templates.isVisible()) {
    const strip = await templates.boundingBox();
    expect(strip && dock && strip.y < dock.y).toBe(true);
  }
  await capture(page, `${OUT}/02-tasks-docked-composer.png`);
});

test("RT-1114B-03 Goals and Approvals use one toolbar row", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=goals`);
  await expect(page.locator(".goals .page-toolbar")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".goals h2", { hasText: /^Goals$/ })).toHaveCount(0);
  if (await page.getByText("No goals yet").isVisible()) {
    await expect(page.getByRole("button", { name: /New goal/ })).toHaveCount(1);
  }
  await capture(page, `${OUT}/03-goals.png`);

  await page.goto(`${BASE}/#/approvals`);
  const filters = page.getByRole("tablist", { name: "Approvals" });
  const refresh = page.getByRole("button", { name: "Refresh approvals" });
  await expect(filters).toBeVisible({ timeout: 30_000 });
  const a = await filters.boundingBox();
  const b = await refresh.boundingBox();
  expect(a && b && Math.abs(a.y + a.height / 2 - (b.y + b.height / 2)) < 8).toBe(true);
  await capture(page, `${OUT}/03-approvals.png`);
});

test("RT-1114B-04 Threads row actions read as actions", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=threads`);
  const evidence = page.locator(".row-links .row-link", { hasText: "Evidence" }).first();
  await expect(evidence).toBeVisible({ timeout: 30_000 });
  const padding = await evidence.evaluate((node) => getComputedStyle(node).paddingLeft);
  expect(Number.parseFloat(padding)).toBeGreaterThan(4);
  const row = page.locator("li:has(> .row-links)").first();
  const rowBox = await row.boundingBox();
  const linkBox = await evidence.boundingBox();
  expect(rowBox && linkBox && linkBox.x > rowBox.x + rowBox.width / 2).toBe(true);
  await capture(page, `${OUT}/04-threads.png`);
});

test("RT-1114B-05 a Chat answer reads cleanly and its context is whole", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  const composer = page.getByRole("group", { name: "Message composer" });
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.getByRole("textbox").first().fill("Name two primary colours, one per line.");
  const send = composer.getByRole("button", { name: /^Send/ });
  await expect(send).toBeEnabled({ timeout: 60_000 });
  await send.click();
  const meta = page.locator(".turn-meta").last();
  await expect(meta).toBeVisible({ timeout: 120_000 });
  await expect(meta).toContainText("Haiku");
  const bubble = page.locator(".message-bubble-raiker").last();
  const background = await bubble.evaluate((node) => getComputedStyle(node).backgroundColor);
  expect(["rgba(0, 0, 0, 0)", "transparent"]).toContain(background);
  await expect(page.getByText(/nothing recalled/)).toHaveCount(0);
  await expect(page.getByText(/nothing else left this computer/)).toHaveCount(0);
  // The composer's context figure counts the cached prompt, so a turn with
  // Raiker's own instructions is several thousand tokens, not a few hundred.
  const context = composer.getByText(/% context/).first();
  await expect(context).toBeVisible();
  await expect(context).not.toHaveText("0% context", { timeout: 30_000 });
  await capture(page, `${OUT}/05-chat-answer.png`);
});

test("RT-1114B-06 no focus frame after reload, and Terminal facts stack", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/models`);
  await page.reload();
  const main = page.locator("main#main");
  await expect(main).toBeVisible({ timeout: 30_000 });
  const outline = await main.evaluate((node) => getComputedStyle(node).outlineStyle);
  expect(outline).toBe("none");

  await page.goto(`${BASE}/#/build`);
  await page.getByRole("button", { name: "Show the governed terminal" }).click();
  const posture = page.locator("#artifact-panel-terminal div.posture").first();
  await expect(posture).toBeVisible({ timeout: 30_000 });
  expect(await posture.evaluate((node) => getComputedStyle(node).display)).toBe("grid");
  await capture(page, `${OUT}/06-build-terminal.png`);
});

test("RT-1114B-07 Voice Preview speaks and Test reports it", async ({ page }) => {
  test.setTimeout(240_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=voice`);
  const preview = page.getByRole("button", { name: "Preview this voice" });
  const installed = await preview
    .waitFor({ timeout: 20_000 })
    .then(() => true)
    .catch(() => false);
  test.skip(!installed, "No voice profile is installed.");
  const spoken = page.waitForResponse((r) => r.url().endsWith("/api/voice/speak") && r.request().method() === "POST");
  await preview.click();
  const answer = await spoken;
  expect(answer.status()).toBe(200);
  expect(answer.headers()["content-type"]).toContain("audio/wav");
  await page.getByRole("button", { name: "Test", exact: true }).click();
  await expect(page.getByTestId("voice-test-result")).toContainText("Spoke a test phrase", { timeout: 120_000 });
  await capture(page, `${OUT}/07-voice.png`);
});
