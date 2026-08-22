/**
 * BUG-219 — the unattended approval posture, against a real instance.
 *
 * The property worth proving live is the one a unit test cannot: that the mode
 * **persists** through the settings endpoint and comes back on the next visit,
 * because the whole point of it is a run nobody is watching — and a posture that
 * silently reverts to Manual between sessions would park exactly the run it
 * exists to keep moving.
 *
 * The menu copy is asserted here too. Four postures is one more than a label can
 * carry, and *Skip* and *Decline* mean opposite things.
 */
import { expect, test } from "@playwright/test";
import { dismissFirstRunModelSetup } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/plans/screenshots/working";

async function signIn(page: import("@playwright/test").Page) {
  await page.goto(`${BASE}/#/workbench`);
  await expect(page.getByText("Verifying runtime…")).toBeHidden({ timeout: 15_000 });
  await page.getByLabel("Username").fill("Rahul");
  await page.getByLabel("Password", { exact: true }).fill("Ithink@10");
  const confirm = page.getByLabel("Confirm password");
  if (await confirm.isVisible().catch(() => false)) {
    await confirm.fill("Ithink@10");
    await page.getByRole("button", { name: "Create a User Account", exact: true }).click();
  } else {
    await page.getByRole("button", { name: "Unlock Raiker", exact: true }).click();
  }
  // The Workbench greets a fresh instance and a returning owner differently
  // ("Welcome to your Work Dashboard" vs "Welcome back"), and a workspace turns
  // from the first into the second the moment it holds any work. Keying sign-in
  // to one of them makes a spec pass or fail on how much history the instance
  // happens to have, which is not what any of these tests are about.
  const workbench = page.getByRole("heading", { name: /Welcome (to your Work Dashboard|back)/ });
  await expect(
    page.getByRole("button", { name: "Decide later" }).or(workbench).first(),
  ).toBeVisible({ timeout: 60_000 });
  await dismissFirstRunModelSetup(page);
  await expect(workbench.first()).toBeVisible({ timeout: 30_000 });
}

/**
 * Open the posture menu and hand back a locator for it.
 *
 * Written as "click only while it is closed" rather than "click once": the
 * trigger toggles, so a spec that clicks blind can just as easily shut a menu
 * another step already opened and then wait forever for an item inside it.
 */
const openMenu = async (page: import("@playwright/test").Page) => {
  const trigger = page.getByRole("button", { name: /approval mode/i }).last();
  const menu = page.getByRole("menu", { name: /approval mode/i });
  await expect(trigger).toBeVisible({ timeout: 30_000 });
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (await menu.isVisible().catch(() => false)) return menu;
    await trigger.click();
    await page.waitForTimeout(200);
  }
  await expect(menu).toBeVisible({ timeout: 10_000 });
  return menu;
};

test.describe.configure({ mode: "serial" });

test("the menu tells skip and decline apart in words", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(`${BASE}/#/new-chat`);

  const menu = await openMenu(page);
  await expect(menu).toBeVisible({ timeout: 30_000 });
  const skip = menu.getByRole("menuitemradio", { name: /Skip all approvals/ });
  const decline = menu.getByRole("menuitemradio", { name: /Decline instead of asking/ });
  await expect(skip).toContainText(/No approval is raised at all/i);
  await expect(decline).toContainText(/refused, not queued/i);

  // The control lives in the composer bar, which is pinned to the bottom of the
  // viewport — so every option has to be *on screen*, not merely rendered. A
  // menu that drops below the fold puts the last posture out of reach on a page
  // that does not scroll.
  for (const option of ["Manually approve", "Automatically approve", "Skip all", "Decline instead"]) {
    await expect(
      menu.getByRole("menuitemradio", { name: new RegExp(option) }),
    ).toBeInViewport();
  }

  await page.screenshot({ path: `${SHOTS}/bug-219-approval-modes.png` });
});

test("every posture is on screen at 390px too", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page);
  await page.goto(`${BASE}/#/new-chat`);

  const menu = await openMenu(page);
  await expect(menu).toBeVisible({ timeout: 30_000 });
  await expect(menu.getByRole("menuitemradio", { name: /Decline instead/ })).toBeInViewport();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);

  await page.screenshot({ path: `${SHOTS}/bug-219-approval-modes-mobile.png` });
});

test("choosing decline persists it across a visit", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(`${BASE}/#/new-chat`);

  const menu = await openMenu(page);
  await menu.getByRole("menuitemradio", { name: /Decline instead of asking/ }).click();
  await expect(page.getByRole("button", { name: /Decline, don't ask/i })).toBeVisible({
    timeout: 30_000,
  });

  // A posture that reverts between sessions would park the run it exists to keep
  // moving, so leaving and coming back is the whole test.
  await page.goto(`${BASE}/#/build`);
  await page.goto(`${BASE}/#/new-chat`);
  await expect(page.getByRole("button", { name: /Decline, don't ask/i })).toBeVisible({
    timeout: 30_000,
  });

  // Put it back, so this spec does not leave the workspace in a refusing posture
  // for whatever runs next.
  const again = await openMenu(page);
  await again.getByRole("menuitemradio", { name: /Manually approve/ }).click();
  await expect(page.getByRole("button", { name: /Manually approve/i })).toBeVisible({
    timeout: 30_000,
  });
});
