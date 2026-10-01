/**
 * Projects §3.12 of the release-readiness review, against a running host.
 *
 * UX-PROJ-04 to UX-PROJ-09: a project's shared files by name, an archive with a
 * way back, a move that refuses its own subtree, a delete that counts what it
 * removes and asks for the owner's password, chat rows that resume, and one
 * "current project". The provider key reaches the product through its own
 * Models page, as an owner's would.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import {
  OWNER_CREDENTIALS,
  chooseModelForTurn,
  signInAsOwner,
} from "./hosted-provider";
import { roundName } from "./naming";
import { LIVE_BASE as BASE, ANTHROPIC_KEY, sendTurn, useAnthropic } from "./live";

const SHOTS = "../../docs/screenshots/2026-10-01-projects-lifecycle";

const PARENT = roundName("Lifecycle parent");
const CHILD = roundName("Lifecycle child");

test.describe.configure({ mode: "serial" });

/** One governed API call from inside the signed-in page, with its CSRF pair. */
async function inPage(page: Page, method: string, path: string, body?: unknown): Promise<unknown> {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/)?.[1];
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          ...(csrf ? { "X-Raiker-CSRF": decodeURIComponent(csrf) } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!response.ok) throw new Error(`${method} ${path}: ${response.status}`);
      return response.json();
    },
    { method, path, body },
  );
}

async function projectCard(page: Page, name: string) {
  return page.locator("article.project").filter({ has: page.getByRole("button", { name: `Open project ${name}` }) });
}

async function openLifecycle(page: Page, name: string, item: RegExp): Promise<void> {
  await page.getByRole("button", { name: new RegExp(`More actions for ${name}`) }).click();
  await page.getByRole("menuitem", { name: item }).click();
}

test("the owner connects Anthropic through Models", async ({ page }) => {
  test.setTimeout(300_000);
  expect(ANTHROPIC_KEY, "set RAIKER_LIVE_ANTHROPIC_KEY").not.toBe("");
  await signInAsOwner(page, BASE);
  const card = await useAnthropic(page);
  await expect(card.getByText(/can reach/i).first()).toBeVisible();
});

test("a chat filed under a project is a row that resumes it, and the project is current (UX-PROJ-08/09)", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/projects`);
  for (const name of [PARENT, CHILD]) {
    await page.getByLabel("New project name").fill(name);
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page.getByRole("button", { name: `Open project ${name}` })).toBeVisible({
      timeout: 30_000,
    });
  }

  // New chat makes the project current and files the chat under it.
  const parent = await projectCard(page, PARENT);
  await parent.getByRole("button", { name: "New chat" }).click();
  await expect(page).toHaveURL(/#\/new-chat/);
  await chooseModelForTurn(page, /Haiku 4\.5/i);
  await sendTurn(page, "Reply with exactly: lifecycle check ok");
  await expect(page.getByText(/lifecycle check ok/i).last()).toBeVisible({ timeout: 120_000 });
  // A new chat is filed when its turn settles, and the composer says so. Leaving
  // before that is leaving before the thing this test is about has happened.
  await expect(page.getByText(`Filed under ${PARENT}.`)).toBeVisible({ timeout: 120_000 });

  await page.goto(`${BASE}/#/projects`);
  await expect(page.getByText(`Current project: ${PARENT}`, { exact: false })).toBeVisible({
    timeout: 30_000,
  });
  await expect((await projectCard(page, PARENT)).getByText("current project")).toBeVisible();
  await expect((await projectCard(page, PARENT)).getByText(/last active/)).toBeVisible();
  await capture(page, `${SHOTS}/01-current-project-and-last-activity.png`);

  await page.getByRole("button", { name: `Open project ${PARENT}` }).click();
  await page.getByRole("tab", { name: "Work" }).click();
  const row = page.locator(".session-rows a").first();
  await expect(row).toContainText(/Chat · 1 exchange/);
  await expect(row).not.toContainText(/sess_/);
  await capture(page, `${SHOTS}/02-chat-rows-resume.png`, row);
  const href = await row.getAttribute("href");
  expect(href).toMatch(/^#\/new-chat\?session=/);
  await row.click();
  await expect(page).toHaveURL(/#\/new-chat\?session=/);
  await expect(page.getByText(/lifecycle check ok/i).last()).toBeVisible({ timeout: 60_000 });
});

test("shared files read by name, with the ids one disclosure away (UX-PROJ-04)", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/projects`);
  await expect(page.getByRole("button", { name: `Open project ${PARENT}` })).toBeVisible({
    timeout: 30_000,
  });
  // There is no picker for a project's shared files yet; the context route is
  // the one an attachment reaches it by, so the round seeds it the same way.
  const list = (await inPage(page, "GET", "/api/projects")) as {
    projects: { project_id: string; name: string }[];
  };
  const parentId = list.projects.find((p) => p.name === PARENT)!.project_id;
  // A 1×1 PNG: the attachment store sniffs the bytes, so a name alone is refused.
  const png =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
  const uploaded = (await inPage(page, "POST", "/api/attachments", {
    filename: "moodboard.png",
    media_type: "image/png",
    data_base64: png,
  })) as { attachment_id: string };
  await inPage(page, "PUT", `/api/projects/${parentId}/context`, {
    instructions: "",
    attachment_ids: [uploaded.attachment_id],
    memory_enabled: false,
    memory_mode: "inherit",
  });

  await page.reload();
  await page.getByRole("button", { name: `Open project ${PARENT}` }).click();
  await expect(page.getByText("moodboard.png")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/PNG · \d+ B/)).toBeVisible();
  await expect(page.getByText(uploaded.attachment_id)).toBeHidden();
  await capture(page, `${SHOTS}/03-shared-files-by-name.png`, page.getByText("moodboard.png"));
});

test("a move into the project's own subtree is not offered, and a real one lands (UX-PROJ-06)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/projects`);
  await openLifecycle(page, CHILD, /^Move…$/);
  let dialog = page.getByRole("dialog", { name: new RegExp(`Move “${CHILD}”`) });
  await dialog.getByText(PARENT, { exact: true }).click();
  await dialog.getByRole("button", { name: "Move here" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });

  await openLifecycle(page, PARENT, /^Move…$/);
  dialog = page.getByRole("dialog", { name: new RegExp(`Move “${PARENT}”`) });
  const childOption = dialog.locator("label").filter({ hasText: CHILD });
  await expect(childOption).toContainText("inside this project");
  await expect(childOption.locator("input")).toBeDisabled();
  await expect(dialog.locator("label").filter({ hasText: PARENT }).locator("input")).toBeDisabled();
  await capture(page, `${SHOTS}/04-move-refuses-own-subtree.png`);
  await dialog.getByRole("button", { name: "Cancel" }).click();
});

test("archive takes the subtree out of new work, and restore brings it back (UX-PROJ-05)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/projects`);
  await openLifecycle(page, PARENT, /^Archive$/);
  await expect(page.getByText(/No current project/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: `Open project ${PARENT}` })).toBeHidden();

  await page.getByRole("tab", { name: /^Archived/ }).click();
  await expect(page.getByRole("button", { name: `Open project ${PARENT}` })).toBeVisible();
  await expect(page.getByRole("button", { name: `Open project ${CHILD}` })).toBeVisible();
  await expect(page.getByText(/Nothing expires/)).toBeVisible();
  await capture(page, `${SHOTS}/05-archived-list.png`);

  await (await projectCard(page, PARENT)).getByRole("button", { name: "Restore" }).click();
  await page.getByRole("tab", { name: /^Active/ }).click();
  await expect(page.getByRole("button", { name: `Open project ${PARENT}` })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByRole("button", { name: `Open project ${CHILD}` })).toBeVisible();
});

test("deleting a managed project counts what goes and asks for the password (UX-PROJ-07)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/projects`);
  await openLifecycle(page, PARENT, /^Delete…$/);
  const dialog = page.getByRole("dialog", { name: new RegExp(`Delete “${PARENT}”`) });
  await expect(dialog.getByText(/1 chat \(1 exchange\)/)).toBeVisible({ timeout: 30_000 });
  await expect(dialog.getByText(/^The folder .* from this computer/)).toBeVisible();
  await expect(dialog.getByText(/1 project inside it/)).toBeVisible();
  const remove = dialog.getByRole("button", { name: "Delete project" });
  await dialog.getByLabel("Project name to confirm deletion").fill(PARENT);
  await expect(remove).toBeDisabled();
  await capture(page, `${SHOTS}/06-delete-counts-and-step-up.png`);

  await dialog.getByLabel("Password").fill("not the password");
  await remove.click();
  await expect(dialog.getByText(/Nothing was deleted/)).toBeVisible({ timeout: 30_000 });

  await dialog.getByLabel("Password").fill(OWNER_CREDENTIALS.password);
  await remove.click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: `Open project ${PARENT}` })).toBeHidden();
  // The child was kept: archived, at the top level, restorable.
  await page.getByRole("tab", { name: /^Archived/ }).click();
  await expect(page.getByRole("button", { name: `Open project ${CHILD}` })).toBeVisible();
  await capture(page, `${SHOTS}/07-child-kept-archived.png`);
});

test("Projects at phone width keeps its lifecycle reachable", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/projects`);
  await page.getByRole("tab", { name: /^Archived/ }).click();
  await expect(page.getByRole("button", { name: `Open project ${CHILD}` })).toBeVisible({
    timeout: 30_000,
  });
  const bleed = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(bleed).toBeLessThanOrEqual(0);
  await capture(page, `${SHOTS}/08-mobile-archived.png`);
});

test("a pending approval is shown once, by its card, and nothing covers Chat's header (found 2026-10-01)", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signInAsOwner(page, BASE);
  const pending = (await inPage(page, "GET", "/api/approvals?status=pending")) as unknown[];
  test.skip(pending.length === 0, "No approval is pending in this workspace to show.");
  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByRole("region", { name: "Approval needed" })).toBeVisible({
    timeout: 30_000,
  });
  const dock = page.getByRole("region", { name: "Notifications" });
  await expect(dock.filter({ hasText: "Approval needed" })).toHaveCount(0);
  // Whatever the header holds is the header's to be pressed.
  const newChat = page.getByRole("button", { name: "New chat" }).first();
  const covered = await newChat.evaluate((el) => {
    const r = el.getBoundingClientRect();
    const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return !(top === el || el.contains(top));
  });
  expect(covered).toBe(false);
  // And the card is never over the composer's Send, from the first frame the
  // composer exists rather than from the card's next measurement.
  const send = page
    .getByRole("group", { name: "Message composer" })
    .getByRole("button", { name: /^Send/ });
  await expect(send).toBeVisible({ timeout: 30_000 });
  const sendCovered = await send.evaluate((el) => {
    const r = el.getBoundingClientRect();
    const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return !(top === el || el.contains(top));
  });
  expect(sendCovered).toBe(false);
  await capture(page, `${SHOTS}/09-approval-shown-once-on-chat.png`);
});
