/**
 * First launch, driven stage by stage on an empty workspace.
 *
 * FIRST-02 through FIRST-10. The secure opening boundary above this screen —
 * runtime reachability, encrypted-store availability, owner registration versus
 * unlock, bootstrap verification — is FIRST-01 and is deliberately untouched;
 * what this asserts is the part after it, which used to ask an owner to
 * understand infrastructure before they had used the product once.
 *
 * It needs a workspace nothing has touched. A workspace whose setup is finished
 * does not mount the wizard at all, and one left part-way resumes on the stage
 * it stopped at; both skip with the reason rather than failing.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { OWNER_CREDENTIALS } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-21-quiet-ui-round-2";

/**
 * Sign in without answering the wizard.
 *
 * `signInAsOwner` finishes setup on the way past, which is right for every
 * other spec and wrong for the one spec that is *about* the wizard: it would
 * complete the flow and then assert against a screen that is no longer there.
 */
async function signInLeavingSetupOpen(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Checking Raiker…")).toBeHidden({ timeout: 30_000 });
  const username = page.getByLabel("Username");
  await expect(username).toBeEnabled({ timeout: 60_000 });
  await username.fill(OWNER_CREDENTIALS.user);
  await page.getByLabel("Password", { exact: true }).fill(OWNER_CREDENTIALS.password);
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill(OWNER_CREDENTIALS.password);
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: /unlock|sign in/i }).click();
  }
}

test("RT-QUI-16 — first launch is a setup conversation: Hello, Where should I think, How I'll ask, first task", async ({ page }) => {
  test.setTimeout(240_000);
  await signInLeavingSetupOpen(page);

  const title = page.locator("#setup-title");
  // A workspace whose setup is finished does not mount the wizard at all, and
  // one that was left part-way resumes on the stage it stopped at. Both are
  // states this spec cannot assert against, and neither is a defect: skip with
  // the reason rather than failing on a missing element.
  const opened = await title
    .waitFor({ state: "visible", timeout: 30_000 })
    .then(() => true)
    .catch(() => false);
  test.skip(!opened, "Setup is already complete here, so this is not a first run.");
  // The wizard mounts before its state read resolves, and says so — asking it
  // which stage it is on while it is still "Preparing your setup…" gets the
  // loading heading, which is not a stage and is not evidence of anything.
  await expect(title).not.toHaveText(/Preparing/, { timeout: 30_000 });
  const heading = ((await title.textContent()) ?? "").trim();
  // QUI-W02 — first run is a setup conversation, and it opens on Hello.
  test.skip(!heading.startsWith("Hi, I'm Raiker"), `Setup resumed on "${heading}", so this is not a first run.`);
  // FIRST-02 — no Account stage after the account was created; no Welcome or
  // Permissions stage either. QUI-W06 — the progress line names real steps.
  for (const gone of ["Account", "Backup", "Welcome", "Permissions"]) {
    await expect(page.locator(".stage-rail")).not.toContainText(gone);
  }
  await expect(page.locator(".stage-rail")).toContainText("Name");
  await expect(page.getByRole("button", { name: "Skip setup" })).toBeVisible();
  await capture(page, `${SHOTS}/16-setup-hello.png`);
  await page.getByLabel("Your name").fill("Rahul");
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  // A source checkout checks this device next; a desktop install does not.
  await expect(title).not.toHaveText(/^Hi, I'm Raiker/, { timeout: 30_000 });
  if ((await title.textContent())?.startsWith("What this computer can run")) {
    await page.getByRole("button", { name: "Continue", exact: true }).click();
  }
  // QUI-W03 — three answers to "Where should I think?".
  await expect(title).toHaveText("Where should I think?", { timeout: 30_000 });
  const sofar = page.getByRole("list", { name: "Setup so far" });
  await expect(sofar).toContainText("Rahul");
  for (const card of [/^On this computer/, /^An account I have/, /^Decide later/]) {
    await expect(page.getByRole("button", { name: card })).toBeVisible();
  }
  await expect(page.getByRole("link", { name: "Advanced setup" })).toBeVisible();
  await capture(page, `${SHOTS}/17-setup-where-to-think.png`);
  await page.getByRole("button", { name: /^Decide later/ }).click();

  // QUI-W04 — how Raiker will ask, and where data goes. No connection requests.
  await expect(title).toHaveText("Here is how I'll work for you.", { timeout: 30_000 });
  await expect(page.getByText(/I'll ask before I send, delete, pay or share anything/)).toBeVisible();
  await expect(sofar).toContainText("Decide later");
  await capture(page, `${SHOTS}/18-setup-how-i-ask.png`);
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  await expect(title).not.toHaveText("Here is how I'll work for you.", { timeout: 30_000 });
  if ((await title.textContent())?.includes("Checking your installation")) {
    const proceed = page.getByRole("button", { name: /^(Continue|Continue anyway)$/ });
    await expect(proceed).toBeEnabled({ timeout: 120_000 });
    await proceed.click();
  }
  // QUI-W05 / REM-LAUNCH-01 — this run deferred the model, so the last step
  // says what it actually did, and offers the first task anyway.
  await expect(title).toHaveText(/^Setup is saved\./, { timeout: 30_000 });
  await expect(page.getByRole("link", { name: "Choose a model" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Ways to start" }).getByRole("listitem")).toHaveCount(4);
  await expect(page.getByText("Kept in Threads as “Getting started”.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Set up backup" })).toBeVisible();
  await capture(page, `${SHOTS}/19-setup-first-task.png`);

  await page.getByRole("button", { name: "Go to Home" }).click();
  await expect(title).toBeHidden({ timeout: 30_000 });
  // QUI-W02 — Home greets the owner by the name given in setup.
  await expect(page.getByRole("heading", { name: /, Rahul$/ })).toBeVisible({ timeout: 30_000 });
});
