/**
 * FIXED-1446 to FIXED-1468 — the first 2026-11-15 round, against a real host.
 *
 * RT-1115-01  Settings › Security: every card's values share one column, and
 *             the workspace key sits under Encryption with its fingerprint.
 * RT-1115-02  Rotating the workspace key from Settings (password step-up)
 *             re-keys the store: the fingerprint changes, the backup taken
 *             first is listed as made with a retired key, and Raiker keeps
 *             answering on the new key.
 * RT-1115-03  An execution profile bounds Chat: with Private local active, a
 *             turn on hosted Anthropic is not sent and names the profile; with
 *             Cloud-first active the same turn answers.
 * RT-1115-04  A finished Build turn offers Make this a goal, which opens the
 *             Goals form filled with the request.
 * RT-1115-05  Attaching a folder to a project asks in Raiker's own dialog, not
 *             the browser's prompt.
 * RT-1115-06  Diagnostics lists background indexing (a waiting issue, or a
 *             row under What is working).
 * RT-1115-07  Tasks' counts share the toolbar; Notifications fits its budget
 *             at 1280×800 with the categories in columns.
 *
 * Needs a host with Anthropic connected (RT-1114-01 in
 * `fixed-1389-1393-tasks-chatgpt-live.spec.ts`). No key, token or workspace ID
 * is written here; the owner password is the harness's own test owner.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, OWNER_CREDENTIALS, signInAsOwner, useHostedModel } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const OUT = "../../output/playwright/2026-11-15-round";

test.describe.configure({ mode: "serial" });

async function valueLefts(page: Page): Promise<number[]> {
  return page.locator(".setting-row .setting-value").evaluateAll((nodes) =>
    nodes.filter((node) => (node as HTMLElement).offsetParent !== null).map((node) => Math.round(node.getBoundingClientRect().left)),
  );
}

test("RT-1115-01 Security's values share one column and the key sits under Encryption", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=security`);
  const key = page.getByTestId("workspace-key-fingerprint");
  await expect(key).toHaveText(/^[0-9a-f]{16}$/, { timeout: 30_000 });
  const vault = page.getByRole("region", { name: "Encryption and the vault" }).or(page.locator('section[aria-labelledby="security-vault-h"]'));
  await expect(vault.getByTestId("workspace-key-card")).toBeVisible();
  const lefts = await valueLefts(page);
  expect(lefts.length).toBeGreaterThan(6);
  expect(Math.max(...lefts) - Math.min(...lefts)).toBeLessThanOrEqual(1);
  await capture(page, `${OUT}/01-security-aligned.png`);
});

test("RT-1115-02 the workspace key rotates in place from Settings", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=security`);
  const key = page.getByTestId("workspace-key-fingerprint");
  await expect(key).toHaveText(/^[0-9a-f]{16}$/, { timeout: 30_000 });
  const before = (await key.textContent())?.trim();
  await page.getByTestId("workspace-key-card").getByRole("button", { name: "Rotate" }).click();
  const dialog = page.getByRole("dialog", { name: "Rotate the workspace key" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Password").fill(OWNER_CREDENTIALS.password);
  const code = dialog.getByLabel("Authenticator code");
  expect(await code.count(), "this round's owner has no two-step sign-in").toBe(0);
  await dialog.getByRole("button", { name: "Back up and rotate" }).click();
  const done = page.getByTestId("workspace-key-rotated");
  await expect(done).toBeVisible({ timeout: 90_000 });
  await expect(done).toContainText("Rotated and verified");
  const after = (await key.textContent())?.trim();
  expect(after).toMatch(/^[0-9a-f]{16}$/);
  expect(after).not.toBe(before);
  await expect(page.getByText(`${before} · kept for 1 backup`)).toBeVisible();
  await capture(page, `${OUT}/02-key-rotated.png`);

  // The backup taken first now needs the retired key, which Raiker keeps.
  await page.goto(`${BASE}/#/settings?tab=backups`);
  await expect(page.getByTestId("backup-retired-key").first()).toBeVisible({ timeout: 30_000 });
  await capture(page, `${OUT}/02b-backup-retired-key.png`);

  // And the workspace still reads on the new key: a fresh page load lists threads.
  await page.goto(`${BASE}/#/work?tab=threads`);
  await expect(page.getByRole("heading", { name: /Work/ }).or(page.locator("main#main")).first()).toBeVisible({ timeout: 30_000 });
});

async function createProfile(page: Page, template: string): Promise<void> {
  await page.goto(`${BASE}/#/settings?tab=execution-profiles`);
  const templates = page.getByRole("list", { name: "Templates" });
  await templates.getByRole("button", { name: `Create ${template}` }).click();
  const profiles = page.getByRole("list", { name: "Profiles" });
  const row = profiles.getByRole("listitem").filter({ hasText: template }).last();
  await expect(row).toBeVisible({ timeout: 30_000 });
  const activate = row.getByRole("button", { name: "Make active" });
  if (await activate.isVisible().catch(() => false)) await activate.click();
  await expect(row.getByText("Active", { exact: true })).toBeVisible({ timeout: 30_000 });
}

test("RT-1115-03 the active execution profile bounds a Chat turn", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await createProfile(page, "Private local");
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  const composer = page.getByRole("group", { name: "Message composer" });
  await composer.getByRole("textbox").first().fill("Say hello in three words.");
  await composer.getByRole("button", { name: /^Send/ }).click();
  await expect(page.getByText(/Not sent: your active execution profile, Private local, does not allow anthropic \(hosted\)/)).toBeVisible({ timeout: 60_000 });
  await capture(page, `${OUT}/03-profile-refused.png`);

  await createProfile(page, "Cloud-first");
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  await composer.getByRole("textbox").first().fill("Reply with exactly the word: ready");
  await composer.getByRole("button", { name: /^Send/ }).click();
  await expect(page.locator(".message-bubble-raiker, .answer").last()).toContainText(/ready/i, { timeout: 120_000 });
  await capture(page, `${OUT}/03b-cloud-first-answers.png`);
});

test("RT-1115-04 a Build answer offers Make this a goal", async ({ page }) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=projects`);
  const list = page.locator(".project-list");
  if ((await list.locator("article.project").count()) === 0) {
    const name = page.getByPlaceholder(/project name/i).first();
    await name.fill(`Round 1115 ${Date.now()}`);
    await name.press("Enter");
  }
  await list.locator("article.project").first().getByRole("button", { name: "Start in Build" }).click();
  await chooseModelForTurn(page, /Haiku/, "Build composer");
  await page.getByLabel("Describe the change").fill("Answer in one short sentence and use no tools: what is a changelog?");
  const run = page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first();
  await expect(run).toBeEnabled({ timeout: 60_000 });
  await run.click();
  const goal = page.getByRole("button", { name: "Make this a goal" }).last();
  await expect(goal).toBeVisible({ timeout: 180_000 });
  await capture(page, `${OUT}/04-build-goal-action.png`);
  await goal.click();
  await expect(page).toHaveURL(/#\/work\?tab=goals/);
  await expect(page.getByText(/Filled in from “Build/)).toBeVisible({ timeout: 30_000 });
  await capture(page, `${OUT}/04b-goal-form.png`);
});

test("RT-1115-05 attaching a folder asks in Raiker's own dialog", async ({ page }) => {
  await signInAsOwner(page, BASE);
  let nativeAsked = false;
  page.on("dialog", (dialog) => {
    nativeAsked = true;
    void dialog.dismiss();
  });
  await page.goto(`${BASE}/#/work?tab=projects`);
  await page.getByRole("button", { name: /^Open project / }).first().click();
  await page.getByRole("button", { name: "Attach a folder", exact: true }).click();
  const ask = page.getByRole("dialog", { name: "Attach a folder" });
  await expect(ask).toBeVisible();
  await expect(ask.getByRole("button", { name: "Attach", exact: true })).toBeDisabled();
  await capture(page, `${OUT}/05-attach-dialog.png`);
  await ask.getByRole("button", { name: "Cancel" }).click();
  await expect(ask).toHaveCount(0);
  expect(nativeAsked).toBe(false);
});

test("RT-1115-06 Diagnostics says what background indexing is doing", async ({ page }) => {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/observe?tab=overview`);
  const issue = page.locator(".issue").filter({ hasText: "Recall is matching words only" });
  const row = page.locator(".healthy-rows").getByText("Background indexing");
  await expect(issue.or(row).first()).toBeAttached({ timeout: 30_000 });
  await capture(page, `${OUT}/06-diagnostics-indexing.png`);
});

test("RT-1115-07 Tasks and Notifications fit their budgets", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=tasks`);
  const toolbar = page.locator(".tasks header.page-toolbar");
  await expect(toolbar.locator(".summary")).toContainText("open", { timeout: 30_000 });
  await capture(page, `${OUT}/07-tasks-toolbar.png`);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`${BASE}/#/settings?tab=notification`);
  await expect(page.locator(".categories")).toBeVisible({ timeout: 30_000 });
  const height = await page.evaluate(() => (document.querySelector("main#main") as HTMLElement).scrollHeight);
  expect(height).toBeLessThanOrEqual(1200);
  await capture(page, `${OUT}/07b-notifications.png`);
});

test("RT-1115-08 OpenAI and OpenRouter connect through Add model and are ready", async ({ page }) => {
  test.setTimeout(600_000);
  const providers = [
    { provider: "OpenAI", keyLabel: "OpenAI API key", key: process.env.RAIKER_LIVE_OPENAI_KEY ?? "", model: process.env.RAIKER_LIVE_OPENAI_MODEL ?? "gpt-4o-mini" },
    { provider: "OpenRouter", keyLabel: "OpenRouter API key", key: process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "", model: process.env.RAIKER_LIVE_OPENROUTER_MODEL ?? "openai/gpt-4o-mini" },
  ];
  test.skip(providers.some((p) => p.key === ""), "set RAIKER_LIVE_OPENAI_KEY and RAIKER_LIVE_OPENROUTER_KEY");
  await signInAsOwner(page, BASE);
  for (const options of providers) {
    const card = await useHostedModel(page, BASE, options);
    await expect(card).toBeVisible();
    await capture(page, `${OUT}/08-${options.provider.toLowerCase()}-ready.png`, card);
  }
});

test("RT-1115-09 Build's composer keeps the model on the bar's one row with a long project name", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/work?tab=projects`);
  const list = page.locator(".project-list");
  if ((await list.locator("article.project").count()) === 0) {
    const name = page.getByPlaceholder(/project name/i).first();
    await name.fill(`Round 1115 ${Date.now()}`);
    await name.press("Enter");
  }
  await list.locator("article.project").first().getByRole("button", { name: "Start in Build" }).click();
  // The long summary (project · workspace · sandbox · context) appears once a
  // turn has run, which is the state the owner's screenshot showed.
  await chooseModelForTurn(page, /Haiku/, "Build composer");
  await page.getByLabel("Describe the change").fill("Answer in one short sentence and use no tools: what is a README?");
  const run = page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first();
  await expect(run).toBeEnabled({ timeout: 60_000 });
  await run.click();
  await expect(page.getByRole("button", { name: "Make this a goal" }).last()).toBeVisible({ timeout: 180_000 });
  await expect(page.locator(".bar-left").last().locator(".context-summary")).toContainText("·", { timeout: 30_000 });
  const bar = page.locator(".bar-left").last();
  await expect(bar.locator(".context-summary")).toBeVisible({ timeout: 30_000 });
  const tops = await bar.evaluate((node) =>
    Array.from(node.children)
      .filter((child) => (child as HTMLElement).offsetParent !== null)
      .map((child) => Math.round(child.getBoundingClientRect().top + child.getBoundingClientRect().height / 2)),
  );
  // Every control on the left of the bar shares one row, and so does Send.
  expect(Math.max(...tops) - Math.min(...tops)).toBeLessThanOrEqual(4);
  const send = await page.locator(".bar-right").last().boundingBox();
  const left = await bar.boundingBox();
  expect(send && left && Math.abs(send.y + send.height / 2 - (left.y + left.height / 2))).toBeLessThanOrEqual(6);
  await capture(page, `${OUT}/09-build-composer-one-row.png`, page.locator(".composer").last());
});
