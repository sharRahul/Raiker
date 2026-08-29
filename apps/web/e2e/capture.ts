/**
 * BUG-241 — capturing evidence that contains the thing it is named for.
 *
 * The app shell gives the routed view its own scrolling container, so the page
 * itself never grows: Playwright's `fullPage: true` captured the viewport and
 * stopped, and every capture of a long page showed the same top of it. Two
 * captures taken at different points in a round came out byte-identical, and
 * were filed and read as proof of a change neither of them contained.
 *
 * That is the same shape as an inert switch — not a missing control, but a
 * wrong belief about one — so the fix belongs in the harness rather than in the
 * product: the page scrolls correctly in a browser, and nothing an owner uses
 * is wrong.
 *
 * `capture` resizes the viewport to the height of the shell's own scroll
 * container before shooting, so a full-page capture really is the full page. It
 * takes an optional locator, which is scrolled into view first — the cheapest
 * way to be certain the section a capture is named for is in it.
 */
import type { Locator, Page } from "@playwright/test";

/** Beyond this a capture is a wall of pixels nobody reads. */
const MAX_CAPTURE_HEIGHT = 6000;

/** The tallest content the shell is scrolling, in CSS pixels. */
async function contentHeight(page: Page): Promise<number> {
  return page.evaluate(() => {
    const heights = [document.documentElement.scrollHeight, document.body.scrollHeight];
    for (const element of Array.from(document.querySelectorAll<HTMLElement>("*"))) {
      const style = getComputedStyle(element);
      const scrolls = /auto|scroll|overlay/.test(`${style.overflowY}`);
      if (!scrolls || element.scrollHeight <= element.clientHeight) continue;
      // What the whole of this container would need: everything above it on the
      // page, plus all of its own content.
      heights.push(element.getBoundingClientRect().top + window.scrollY + element.scrollHeight);
    }
    return Math.ceil(Math.max(...heights));
  });
}

/**
 * Screenshot the whole routed view, not the first viewport of it.
 *
 * Pass `target` to guarantee a section is on screen and settled first; it is
 * scrolled into view before the height is measured.
 */
export async function capture(page: Page, path: string, target?: Locator): Promise<void> {
  if (target !== undefined) await target.scrollIntoViewIfNeeded();
  const viewport = page.viewportSize();
  if (viewport === null) {
    await page.screenshot({ path, fullPage: true });
    return;
  }
  const needed = Math.min(await contentHeight(page), MAX_CAPTURE_HEIGHT);
  const height = Math.max(viewport.height, needed);
  if (height !== viewport.height) {
    await page.setViewportSize({ width: viewport.width, height });
  }
  try {
    await page.screenshot({ path, fullPage: true });
  } finally {
    if (height !== viewport.height) await page.setViewportSize(viewport);
  }
}

/**
 * Screenshot one element rather than the page around it.
 *
 * For evidence about a single card or panel, where the rest of the route is
 * noise that makes two captures harder to tell apart, not easier.
 */
export async function captureElement(target: Locator, path: string): Promise<void> {
  await target.scrollIntoViewIfNeeded();
  await target.screenshot({ path });
}
