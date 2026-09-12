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

const BASE = process.env.RAIKER_LIVE_BASE ?? "http://127.0.0.1:8765";

const SHOTS = "../../docs/screenshots/2026-09-12-first-launch";

/**
 * Sign in without answering the wizard.
 *
 * `signInAsOwner` finishes setup on the way past, which is right for every
 * other spec and wrong for the one spec that is *about* the wizard: it would
 * complete the flow and then assert against a screen that is no longer there.
 */
async function signInLeavingSetupOpen(page: Page): Promise<void> {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 30_000 });
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

test("first launch teaches Chat, Build and Design before any provider", async ({ page }) => {
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
  test.skip(
    !heading.startsWith("Meet Raiker"),
    `Setup resumed on "${heading}", so this is not a first run.`,
  );

  // FIRST-03 — the product model, before the infrastructure.
  for (const mode of ["Chat", "Build", "Design"]) {
    await expect(page.getByText(mode, { exact: true }).first()).toBeVisible();
  }
  // FIRST-10 — the posture in a sentence, not sixty-six gates to configure.
  await expect(page.getByText(/starts conservatively/i)).toBeVisible();
  // FIRST-02 — no Account stage after the account was created.
  await expect(page.locator(".stage-rail")).not.toContainText("Account");
  await expect(page.locator(".stage-rail")).not.toContainText("Backup");
  await capture(page, `${SHOTS}/first-run-01-welcome.png`);

  await page.getByRole("button", { name: "Continue" }).click();
  await expect(title).toHaveText(/Choose how Raiker should think/, { timeout: 30_000 });
  // FIRST-06 — the Models page is deeper configuration, not the way out.
  await expect(page.getByRole("link", { name: "Advanced setup" })).toBeVisible();
  await capture(page, `${SHOTS}/first-run-02-model.png`);

  await page.getByRole("button", { name: /^(Decide later|Continue)$/ }).click();
  // FIRST-07 — a question about where content travels.
  await expect(title).toHaveText(/Where may Raiker send model requests/, { timeout: 30_000 });
  await capture(page, `${SHOTS}/first-run-03-privacy.png`);

  await page.getByRole("button", { name: /Local, and the providers I connect/ }).click();
  await expect(title).toHaveText(/Your Raiker is ready/, { timeout: 30_000 });
  // FIRST-09 — finish into work. FIRST-08 — backup offered, not required.
  for (const mode of ["Chat", "Build", "Design"]) {
    await expect(page.getByRole("button", { name: mode, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "Set up backup" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open Workbench" })).toHaveCount(0);
  await capture(page, `${SHOTS}/first-run-04-ready.png`);

  await page.getByRole("button", { name: "Start using Raiker" }).click();
  await expect(title).toBeHidden({ timeout: 30_000 });
});

