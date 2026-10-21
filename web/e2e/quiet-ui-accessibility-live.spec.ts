/**
 * QUI-G05 — accessibility beyond axe, against a running host.
 *
 * Axe already runs in `composer.spec.ts`. This walks every destination with
 * the keyboard alone, and checks Chat at 200% zoom on a 1280×800 screen.
 *
 * Live cases (docs/architecture/WEB_APP_LIVE_TEST.md, "Quiet UI round 2"):
 * RT-QUI-14 and RT-QUI-15.
 */
import { expect, test, type Page } from "@playwright/test";

import { capture } from "./capture";
import { DESTINATIONS, settled } from "./destinations";
import { signInAsOwner } from "./hosted-provider";
import { LIVE_BASE as BASE } from "./live";

const SHOTS = process.env.RAIKER_LIVE_SHOTS ?? "../../docs/screenshots/2026-10-21-quiet-ui-round-2";
const TABS_PER_PAGE = 25;

/** Where focus is, whether it can be seen, and whether it shows that it has focus. */
async function focusState(page: Page) {
  return page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    if (element === null || element === document.body) return { onBody: true, visible: false, marked: false, name: "body" };
    const box = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    const marked =
      (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0) ||
      style.boxShadow !== "none" ||
      // A control styled by a wrapper (a custom checkbox, a segmented control)
      // shows focus on the wrapper: `:focus-within` is the same signal.
      element.parentElement?.matches(":focus-within") === true;
    return {
      onBody: false,
      visible: box.width > 0 && box.height > 0,
      marked,
      name: `${element.tagName.toLowerCase()} "${(element.getAttribute("aria-label") ?? element.textContent ?? "").trim().slice(0, 40)}"`,
    };
  });
}

test("RT-QUI-14 — every destination can be walked with Tab, and focus is always visible", async ({ page }) => {
  test.setTimeout(600_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAsOwner(page, BASE);
  const problems: string[] = [];
  for (const { route } of DESTINATIONS) {
    await page.goto(`${BASE}/#/${route}`);
    await settled(page);
    await page.locator("body").click({ position: { x: 1, y: 1 } });
    let reached = 0;
    for (let step = 0; step < TABS_PER_PAGE; step += 1) {
      await page.keyboard.press("Tab");
      const state = await focusState(page);
      if (state.onBody) continue;
      reached += 1;
      if (!state.visible) problems.push(`#/${route} · Tab ${step + 1} · focus on an invisible ${state.name}`);
      else if (!state.marked) problems.push(`#/${route} · Tab ${step + 1} · no focus indicator on ${state.name}`);
    }
    if (reached === 0) problems.push(`#/${route} · Tab never left the page body`);
  }
  expect(problems).toEqual([]);
});

test("RT-QUI-15 — at 200% zoom on a 1280×800 screen, Chat's Send stays visible", async ({ page }) => {
  test.setTimeout(180_000);
  // 200% zoom on 1280×800 leaves 640×400 CSS pixels.
  await page.setViewportSize({ width: 640, height: 400 });
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/new-chat`);
  await settled(page);
  const box = page.getByPlaceholder("What would you like Raiker to do?");
  await box.fill("Checking the composer at 200% zoom");
  const send = page.getByRole("button", { name: "Send", exact: true });
  await expect(send).toBeInViewport();
  await expect(box).toBeInViewport();
  await capture(page, `${SHOTS}/15-chat-200-percent-zoom.png`);
});
