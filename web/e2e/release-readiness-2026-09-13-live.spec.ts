/*
 * The release-readiness round of 2026-09-13, against a running server.
 *
 * Six entries close here and every one of them is a *presentation* defect —
 * the page said something the runtime did not — so a unit test can show the
 * rule and only a live round can show the page. What is asserted:
 *
 *   NEW-PERM-01   Overview's sentences reach the control (QUI-L06 layout).
 *   NEW-PERM-02   Every summary moves together when one mode is confirmed.
 *   NEW-PERM-03   An unavailable automatic gate is not described as running.
 *   RR-PROJECT-01 "New chat" on a project card starts the chat in that project.
 *   NEW-SET-01    A save acknowledges the revision it submitted.
 *   RR-IDENTITY-01 The owner is addressed by name, never by their principal id.
 *
 * Real server, real account, real governed mutations through the product's own
 * controls. Nothing here is stubbed.
 */
import { expect, test } from "@playwright/test";
import { capture, captureElement } from "./capture";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = "../../output/playwright/2026-09-13-release-readiness";
const PROJECT = "Release readiness";

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  await signInAsOwner(page, BASE);
});

// QUI-L06 (2026-10-21) replaced *Common permissions* and the inline registry
// with Overview's *What Raiker can do for you*, a category rail and one detail
// pane. The three checks below assert the same three defects on that layout.

const WEB_SENTENCE = /^Change: Can(not)? read web pages/;

test("Permissions offers a way to change what it puts at the top", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/capabilities`);
  await page.getByRole("navigation", { name: "Permission categories" }).waitFor({ timeout: 60_000 });

  const overview = page.getByRole("region", { name: "What Raiker can do for you" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await capture(page, `${SHOTS}/permissions-top-sections.png`, overview);

  // NEW-PERM-01 — the owner-reported symptom. Every sentence offers an action,
  // and the action reaches the one control that decides it.
  const sentences = overview.getByRole("listitem");
  const count = await sentences.count();
  expect(count).toBeGreaterThan(0);
  for (let index = 0; index < count; index += 1) {
    await expect(sentences.nth(index).getByRole("button", { name: /^Change: / })).toBeVisible();
  }
  await overview.getByRole("button", { name: WEB_SENTENCE }).click();
  const detail = page.getByRole("region", { name: "Selected item" });
  await expect(detail.getByRole("article")).toBeVisible({ timeout: 30_000 });
  await expect(detail.getByRole("group", { name: /^When Raiker wants to use / })).toBeVisible();
  await capture(page, `${SHOTS}/permissions-shortcut-opened-the-row.png`, detail);
});

test("every Permissions summary moves when one decision is confirmed", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/capabilities`);
  const rail = page.getByRole("navigation", { name: "Permission categories" });
  await rail.waitFor({ timeout: 60_000 });

  await rail.getByRole("button", { name: /^Web and research/ }).click();
  const row = page.getByRole("option", { name: /^Web fetch / }).first();
  await row.click();
  const card = page.getByRole("article", { name: "Web fetch" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  // A governed mutation through the product's own control, not through the API.
  await card.getByRole("button", { name: "Never", exact: true }).click();

  // NEW-PERM-02 — every summary of the same decision moves with it, rather
  // than saying the old mode until a refresh nobody was told to make.
  await expect(row).toContainText("Never", { timeout: 60_000 });
  await expect(card.getByRole("button", { name: "Never", exact: true })).toHaveAttribute("aria-pressed", "true");
  await capture(page, `${SHOTS}/permissions-summary-agrees.png`, card);

  // And it survives the read, rather than being an optimistic label the next
  // refresh replaces with what the server held a moment ago.
  await page.getByRole("button", { name: /Refresh capabilities/i }).click();
  await expect(page.getByRole("option", { name: /^Web fetch / }).first()).toContainText("Never", { timeout: 60_000 });

  // Put it back, so the round leaves the workspace as it found it.
  await page.getByRole("article", { name: "Web fetch" }).getByRole("button", { name: "Ask me", exact: true }).click();
  await expect(page.getByRole("option", { name: /^Web fetch / }).first()).toContainText("Ask me", { timeout: 60_000 });
});

test("the authority summary says what it is a summary of", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto(`${BASE}/#/capabilities`);
  const rail = page.getByRole("navigation", { name: "Permission categories" });
  await rail.waitFor({ timeout: 60_000 });
  await rail.getByRole("button", { name: /^Advanced/ }).click();

  await page.getByText("How your permissions apply", { exact: true }).click();
  const table = page.locator(".authority-matrix");
  await expect(table).toBeVisible({ timeout: 30_000 });
  // NEW-PERM-03 — it reads account configuration, and says so, rather than
  // claiming the authority a turn currently carries.
  await expect(table).toContainText(/read-only/i);
  await expect(table).toContainText(/can narrow it further/i);
  // Nothing in it may read "Direct": that word was one verdict for Allow,
  // Automatic, and any mode this build does not recognise.
  await expect(table.getByText("Direct", { exact: true })).toHaveCount(0);
  // The element, not the page (BUG-241: two captures of one picture).
  await captureElement(table, `${SHOTS}/authority-summary-read-only.png`);
});

test("a new chat started from a project is filed in that project", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/projects`);

  const open = page.getByRole("button", { name: `Open project ${PROJECT}` });
  if ((await open.count()) === 0) {
    await page.getByLabel(/project name/i).fill(PROJECT);
    await page.getByRole("button", { name: /^create( project)?$/i }).click();
  }
  await expect(open.first()).toBeVisible({ timeout: 60_000 });

  const projectId = await page.evaluate(async (name) => {
    const response = await fetch("/api/projects", { credentials: "same-origin" });
    const body = (await response.json()) as { projects?: { project_id: string; name: string }[] };
    return (body.projects ?? []).find((entry) => entry.name === name)?.project_id ?? "";
  }, PROJECT);
  expect(projectId).not.toBe("");

  // RR-PROJECT-01 — this navigated and established nothing, while "Start in
  // Build" beside it established the project.
  const card = page.locator(".project-card, .project").filter({ hasText: PROJECT }).first();
  const newChat = (await card.count())
    ? card.getByRole("button", { name: /^New chat$/ })
    : page.getByRole("button", { name: /^New chat$/ }).first();
  await newChat.click();

  await expect(page).toHaveURL(/#\/new-chat/, { timeout: 30_000 });
  await page.getByRole("button", { name: "Add to this turn" }).first().click();
  await page.getByRole("menuitem", { name: /project/i }).click();
  const picker = page.getByLabel("Project for this chat");
  await expect(picker).toHaveValue(projectId, { timeout: 30_000 });
  await capture(page, `${SHOTS}/new-chat-opens-in-the-project.png`, picker);
});

test("Settings acknowledges the revision it saved", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/settings?tab=personalisation`);
  // Density moved into the *Layout & type* disclosure (QUI-L03).
  await page.getByText("Layout & type", { exact: true }).click({ timeout: 60_000 });

  const density = page.getByRole("radiogroup", { name: "Density" });
  await expect(density).toBeVisible({ timeout: 60_000 });
  await density.getByRole("radio", { name: /Compact/ }).click();
  await expect(page.getByText(/you have unsaved changes/i)).toBeVisible();

  await page.getByRole("button", { name: /save changes/i }).click();
  // NEW-SET-01 — the green line is a claim about now. With nothing edited
  // during the request it is true, and the save bar goes with it.
  await expect(page.getByText(/all changes saved/i)).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/you have unsaved changes/i)).toBeHidden();
  await capture(page, `${SHOTS}/settings-acknowledges-the-save.png`);

  await density.getByRole("radio", { name: /Comfortable/ }).click();
  await page.getByRole("button", { name: /save changes/i }).click();
  await expect(page.getByText(/all changes saved/i)).toBeVisible({ timeout: 60_000 });
});

test("Raiker addresses the owner by name, not by their principal id", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto(`${BASE}/#/settings?tab=account`);
  const name = page.getByLabel("Display name");
  await expect(name).toBeVisible({ timeout: 60_000 });

  // Set it only when the *server* says it is not set, so this round is
  // re-runnable against a workspace it has already been run against and does
  // not race its own fixture: the controls render before the settings read
  // lands (FIXED-85 keeps an edit made in that window), so the field is the
  // wrong thing to read the current value from.
  const stored = await page.evaluate(async () => {
    const response = await fetch("/api/settings", { credentials: "same-origin" });
    const body = (await response.json()) as { status?: { display_name?: string; username?: string } };
    return { name: body.status?.display_name ?? "", username: body.status?.username ?? "" };
  });
  if (stored.name !== "Rahul S") {
    // With no chosen name the server falls back to the sign-in handle, and the
    // field stays empty with that handle in its placeholder.
    const chosen = stored.name === "Owner" || stored.name === stored.username ? "" : stored.name;
    await expect(name).toHaveValue(chosen, { timeout: 30_000 });
    await name.fill("Rahul S");
    await name.blur();
    await page.getByRole("button", { name: /save changes/i }).click();
    await expect(page.getByText(/all changes saved/i)).toBeVisible({ timeout: 60_000 });
  }
  await expect(name).toHaveValue("Rahul S", { timeout: 30_000 });
  await capture(page, `${SHOTS}/account-display-name.png`);

  // RR-IDENTITY-01, the server half: the name the owner chose reaches the turn,
  // and the authorisation key is unchanged. Read through the product's own
  // route rather than out of the database.
  const status = await page.evaluate(async () => {
    const response = await fetch("/api/settings", { credentials: "same-origin" });
    const body = (await response.json()) as {
      status?: { username?: string; display_name?: string };
    };
    return body.status ?? {};
  });
  expect(status.display_name).toBe("Rahul S");
  expect(status.display_name ?? "").not.toMatch(/^principal_/);

  // And the UI half: Chat's empty state greets the owner with the name they
  // chose, not with the fixed sign-in handle and never with an identifier.
  await page.goto(`${BASE}/#/new-chat`);
  const greeting = page.locator(".empty-title").filter({ hasText: /What would you like to work on/ });
  await expect(greeting.first()).toBeVisible({ timeout: 60_000 });
  await expect(greeting.first()).toContainText("Rahul S");
  await expect(greeting.first()).not.toContainText(/principal_/);
  await capture(page, `${SHOTS}/chat-greets-by-name.png`, greeting.first());
});

test("no surface renders an internal principal identifier as a label", async ({ page }) => {
  test.setTimeout(180_000);
  // The acceptance criterion stated as a sweep: an ordinary page must not print
  // a `principal_…` key as though it were a name. Audit and diagnostics detail
  // may, and are not in this list.
  for (const route of ["workbench", "new-chat", "projects", "capabilities", "settings"]) {
    await page.goto(`${BASE}/#/${route}`);
    await page.waitForTimeout(1500);
    const text = (await page.locator("body").innerText()).replace(/\s+/g, " ");
    expect(text, `${route} renders an internal identifier`).not.toMatch(/principal_user_[0-9a-f]{8}/);
  }
});
