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
import { dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import type { Locator, Page } from "@playwright/test";

/**
 * Where a relative capture path is anchored: this directory, `web/e2e`.
 *
 * **Found live on 2026-09-07.** Every spec writes its evidence to a path like
 * `../../docs/plans/screenshots/pages/...`, which was correct while the web app
 * lived at `apps/web` — two levels up from `apps/web/e2e` is the repository
 * root. Moving it to `web/` made that one level too many, and because Playwright
 * resolves a relative screenshot path against the *process* directory rather
 * than the spec's, every capture in every live round has since been written to
 * `/home/user/docs/plans/screenshots/…` — outside the repository, where nothing
 * looks for it and git cannot see it. The sweeps reported success; the
 * `pages/` catalogue they are supposed to keep current simply stopped changing.
 *
 * Anchoring here rather than at the process directory is the fix, and it is the
 * one that needs no spec to be edited: `../../docs` from `web/e2e` is the
 * repository's `docs` again, which is what every one of those strings has always
 * meant.
 */
const E2E_DIR = dirname(fileURLToPath(import.meta.url));

/** A capture path as an absolute one, anchored at `web/e2e` when relative. */
export function capturePath(path: string): string {
  return isAbsolute(path) ? path : resolve(E2E_DIR, path);
}

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
  const capturedTo = capturePath(path);
  if (viewport === null) {
    await page.screenshot({ path: capturedTo, fullPage: true });
    return;
  }
  const needed = Math.min(await contentHeight(page), MAX_CAPTURE_HEIGHT);
  const height = Math.max(viewport.height, needed);
  if (height !== viewport.height) {
    await page.setViewportSize({ width: viewport.width, height });
  }
  try {
    await page.screenshot({ path: capturedTo, fullPage: true });
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
  await target.screenshot({ path: capturePath(path) });
}
