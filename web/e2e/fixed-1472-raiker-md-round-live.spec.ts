/**
 * FIXED-1472 to FIXED-1486 — the 2026-11-16 round, against a real host.
 *
 * RT-1116-01  A project's RAIKER.md: turning file instructions on approves
 *             nothing; *Review and use* approves the exact revision; a real
 *             Build turn follows it; a changed file stops the next Build turn
 *             as *Not sent* with *Review RAIKER.md*, and Build's context
 *             inspector names the file that needs review.
 * RT-1116-02  The account's global RAIKER.md in Settings › Personalisation:
 *             *Create starter file*, then *Review and use*.
 * RT-1116-03  An execution-profile refusal in Chat reads *Not sent* with
 *             *Open Settings*, names the provider *Anthropic*, and is not drawn
 *             as *Not done — The turn failed before it finished*.
 * RT-1116-04  Leaving Settings with an unsaved edit asks in Raiker's own
 *             dialog; Cancel stays, *Leave without saving* goes; no native
 *             dialog fires.
 * RT-1116-05  A project's overview counts settle: no *Loading … count…* left.
 *
 * Needs a host with Anthropic connected (RT-1114-01 in
 * `fixed-1389-1393-tasks-chatgpt-live.spec.ts`) and running on this machine,
 * because RT-1116-01 writes the project's folder itself. No key, token or
 * workspace ID is written here.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { chooseModelForTurn, signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const OUT = "../../output/playwright/2026-11-16-round";
const FOLDER = join(process.env.RAIKER_LIVE_ATTACH_ROOT ?? tmpdir(), `raiker-md-site-${Date.now()}`);
const PROJECT = `RAIKER.md round ${Date.now()}`;
const MARKER = "KIWI-7";

test.describe.configure({ mode: "serial" });

async function openProject(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/work?tab=projects`);
  await page.getByRole("button", { name: `Open project ${PROJECT}` }).click();
  await expect(page.getByRole("heading", { name: PROJECT }).first()).toBeVisible({ timeout: 30_000 });
}

async function buildTurn(page: Page, text: string): Promise<void> {
  await chooseModelForTurn(page, /Haiku/, "Build composer");
  await page.getByLabel("Describe the change").fill(text);
  const run = page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first();
  await expect(run).toBeVisible({ timeout: 60_000 });
  if (await run.isDisabled()) {
    // A host whose command sandbox cannot be confirmed disables Run; Plan
    // still sends the turn, which is all these checks need.
    await page.getByRole("button", { name: /^How much Raiker may do this turn/ }).click();
    await page.getByRole("menuitemradio", { name: /^Plan/ }).click();
  }
  const send = page.getByRole("button", { name: /^(Run|Plan|Propose)$/ }).first();
  await expect(send).toBeEnabled({ timeout: 60_000 });
  await send.click();
}

test("RT-1116-01 a project's RAIKER.md is reviewed, followed, and asked for again when it changes", async ({ page }) => {
  test.setTimeout(420_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  mkdirSync(FOLDER, { recursive: true });
  writeFileSync(join(FOLDER, "README.md"), "# Site\n");
  writeFileSync(join(FOLDER, "RAIKER.md"), `End every answer with the exact word ${MARKER} on its own line.\n`);
  mkdirSync(join(FOLDER, "docs"));
  writeFileSync(join(FOLDER, "docs", "RAIKER.md"), "A nested file is never read.\n");
  await signInAsOwner(page, BASE);

  await page.goto(`${BASE}/#/work?tab=projects`);
  const name = page.getByPlaceholder(/project name/i).first();
  await name.fill(PROJECT);
  await name.press("Enter");
  await openProject(page);
  await page.getByRole("button", { name: "Attach a folder", exact: true }).click();
  const ask = page.getByRole("dialog", { name: "Attach a folder" });
  await ask.getByRole("textbox").fill(FOLDER);
  await ask.getByRole("button", { name: "Attach", exact: true }).click();
  await expect(ask).toHaveCount(0, { timeout: 30_000 });

  const card = page.locator("section.files");
  const projectFile = card.getByTestId("instruction-file-project");
  await expect(projectFile.getByTestId("instruction-file-project-state")).toHaveText("Needs review", { timeout: 30_000 });
  await expect(card).not.toContainText("never read");
  await card.getByTestId("instruction-files-toggle").check();
  await expect(card.getByTestId("instruction-files-needs-review")).toBeVisible();
  await expect(projectFile.getByTestId("instruction-file-project-preview")).toContainText(MARKER);
  await capture(page, `${OUT}/01-raiker-md-needs-review.png`, card);
  await projectFile.getByRole("button", { name: "Review and use" }).click();
  await expect(projectFile.getByTestId("instruction-file-project-state")).toHaveText("In use", { timeout: 30_000 });
  await expect(card.getByTestId("instruction-files-needs-review")).toHaveCount(0);
  await capture(page, `${OUT}/01b-raiker-md-in-use.png`, card);

  // A real Build turn follows the reviewed file.
  await page.getByRole("button", { name: "Start in Build" }).first().click();
  await buildTurn(page, "Use no tools. In one short sentence, what is a changelog?");
  await expect(page.locator(".answer").last()).toContainText(MARKER, { timeout: 180_000 });
  await capture(page, `${OUT}/01c-build-followed-raiker-md.png`);

  // The file changes on disk: the next Build turn waits for a review.
  writeFileSync(join(FOLDER, "RAIKER.md"), `End every answer with the exact word ${MARKER}-2 on its own line.\n`);
  await buildTurn(page, "Use no tools. In one short sentence, what is a README?");
  const refusal = page.getByTestId("turn-refusal").last();
  await expect(refusal).toBeVisible({ timeout: 60_000 });
  await expect(refusal).toContainText("Not sent");
  await expect(refusal).toContainText("needs your review");
  await expect(refusal).not.toContainText("Not sent · Not sent");
  await expect(refusal.getByRole("link", { name: "Review RAIKER.md" })).toHaveAttribute("href", /#\/projects\?project=/);
  await expect(page.getByText("The turn failed before it finished")).toHaveCount(0);
  await page.locator(".context-summary").last().click();
  const inspector = page.getByRole("dialog", { name: "Context for this turn" });
  await expect(inspector).toContainText("Instruction files");
  await expect(inspector).toContainText("Changed since you reviewed it");
  await capture(page, `${OUT}/01d-changed-file-not-sent.png`);
  await page.keyboard.press("Escape");

  await refusal.getByRole("link", { name: "Review RAIKER.md" }).click();
  const again = page.locator("section.files").getByTestId("instruction-file-project");
  await expect(again.getByTestId("instruction-file-project-state")).toHaveText("Changed — needs review", { timeout: 30_000 });
  await again.getByRole("button", { name: "Approve this revision" }).click();
  await expect(again.getByTestId("instruction-file-project-state")).toHaveText("In use", { timeout: 30_000 });
});

test("RT-1116-02 the account's global RAIKER.md is created and reviewed in Settings", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/settings?tab=personalisation`);
  const card = page.getByTestId("global-instruction-file");
  await expect(card.getByTestId("global-instruction-file-state")).not.toHaveText("Reading…", { timeout: 30_000 });
  if ((await card.getByTestId("global-instruction-file-state").textContent())?.includes("No file yet")) {
    await card.locator("summary").click();
    await card.getByRole("button", { name: "Create starter file" }).click();
  }
  await expect(card.getByTestId("global-instruction-file-state")).toHaveText(/Needs review|In use/, { timeout: 30_000 });
  await expect(card).toContainText("user-instructions");
  await capture(page, `${OUT}/02-global-raiker-md-starter.png`, card);
  const review = card.getByRole("button", { name: "Review and use" });
  if (await review.isVisible().catch(() => false)) await review.click();
  await expect(card.getByTestId("global-instruction-file-state")).toHaveText("In use", { timeout: 30_000 });
  await capture(page, `${OUT}/02b-global-raiker-md-in-use.png`, card);
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
  // A rerun leaves earlier profiles of the same name; one of them is active.
  await expect(
    profiles
      .getByRole("listitem")
      .filter({ hasText: template })
      .filter({ hasNot: page.getByRole("button", { name: "Make active" }) })
      .first(),
  ).toBeVisible({ timeout: 30_000 });
}

test("RT-1116-03 a profile refusal in Chat reads Not sent with Open Settings", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await signInAsOwner(page, BASE);
  await createProfile(page, "Private local");
  await page.goto(`${BASE}/#/new-chat`);
  await chooseModelForTurn(page, /Haiku/);
  const composer = page.getByRole("group", { name: "Message composer" });
  await composer.getByRole("textbox").first().fill("Say hello in three words.");
  await composer.getByRole("button", { name: /^Send/ }).click();
  const refusal = page.getByTestId("turn-refusal").last();
  await expect(refusal).toBeVisible({ timeout: 60_000 });
  await expect(refusal).toContainText("does not allow Anthropic (hosted)");
  await expect(refusal.getByRole("link", { name: "Open Settings" })).toHaveAttribute("href", "#/settings?tab=execution-profiles");
  await expect(page.getByText("The turn failed before it finished")).toHaveCount(0);
  await capture(page, `${OUT}/03-chat-refusal-not-sent.png`);
  // Leave the workspace able to answer for the rounds after this one.
  await createProfile(page, "Cloud-first");
});

test("RT-1116-04 leaving Settings with an unsaved edit asks in Raiker's dialog", async ({ page }) => {
  await signInAsOwner(page, BASE);
  const native: string[] = [];
  page.on("dialog", (dialog) => {
    native.push(dialog.message());
    void dialog.dismiss();
  });
  await page.goto(`${BASE}/#/settings?tab=notification`);
  await page.getByLabel(/unread notices inside Raiker/i).click();
  await expect(page.getByText(/you have unsaved changes/i)).toBeVisible({ timeout: 30_000 });
  await page.evaluate(() => {
    window.location.hash = "#/work?tab=tasks";
  });
  const leave = page.getByRole("dialog", { name: "Leave Settings without saving?" });
  await expect(leave).toBeVisible();
  await capture(page, `${OUT}/04-leave-settings-dialog.png`);
  await leave.getByRole("button", { name: "Cancel" }).click();
  await expect(page).toHaveURL(/#\/settings/);
  await page.evaluate(() => {
    window.location.hash = "#/work?tab=tasks";
  });
  await leave.getByRole("button", { name: "Leave without saving" }).click();
  await expect(page).toHaveURL(/#\/work\?tab=tasks/);
  expect(native).toEqual([]);
});

test("RT-1116-05 a project's overview counts settle", async ({ page }) => {
  await signInAsOwner(page, BASE);
  // Any project: run on its own, this spec has no project of this run's name.
  await page.goto(`${BASE}/#/work?tab=projects`);
  await page.getByRole("button", { name: /^Open project / }).first().click();
  const counts = page.locator(".section-counts");
  await expect(counts).toBeVisible({ timeout: 30_000 });
  await expect(counts).not.toContainText("Loading", { timeout: 20_000 });
  await capture(page, `${OUT}/05-project-counts-settled.png`, counts);
});
