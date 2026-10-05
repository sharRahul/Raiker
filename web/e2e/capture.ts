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
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { test, type Locator, type Page } from "@playwright/test";

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

/**
 * DEC-19 step 5 — every capture says where it came from.
 *
 * A screenshot is evidence about one build, one viewport, one theme and one
 * scenario, and the folder held only the picture. Each capture now records
 * those beside it in the folder's `manifest.json`: the commit the round ran on
 * (and whether the working tree differed from it, which a round's own changes
 * usually make true), the viewport it was taken at, the theme it rendered in,
 * the route, and the test that took it. Rewritten in place for a retaken file.
 */
let commitCache: { commit: string; workingTreeChanged: boolean } | null = null;

function revision(): { commit: string; workingTreeChanged: boolean } {
  if (commitCache !== null) return commitCache;
  try {
    const commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: E2E_DIR, encoding: "utf-8" }).trim();
    const status = execFileSync("git", ["status", "--porcelain", "--", "../../raiker", "../src"], {
      cwd: E2E_DIR,
      encoding: "utf-8",
    }).trim();
    commitCache = { commit, workingTreeChanged: status.length > 0 };
  } catch {
    commitCache = { commit: "unknown", workingTreeChanged: true };
  }
  return commitCache;
}

async function recordCapture(page: Page, capturedTo: string, viewport: { width: number; height: number } | null) {
  const manifestPath = resolve(dirname(capturedTo), "manifest.json");
  let manifest: Record<string, unknown> = {};
  try {
    if (existsSync(manifestPath)) manifest = JSON.parse(readFileSync(manifestPath, "utf-8")) as Record<string, unknown>;
  } catch {
    manifest = {};
  }
  const theme = await page
    .evaluate(() => {
      const explicit = document.documentElement.dataset.theme;
      if (explicit === "light" || explicit === "dark") return explicit;
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    })
    .catch(() => "unknown");
  let title: string[];
  try {
    title = test.info().titlePath;
  } catch {
    // Outside a running test (a script calling the helper): no title to record.
    title = [];
  }
  const { commit, workingTreeChanged } = revision();
  manifest[basename(capturedTo)] = {
    commit,
    working_tree_changed: workingTreeChanged,
    viewport,
    theme,
    route: new URL(page.url()).hash || "/",
    test: title.join(" › "),
    captured_at: new Date().toISOString(),
  };
  const ordered = Object.fromEntries(Object.entries(manifest).sort(([a], [b]) => a.localeCompare(b)));
  writeFileSync(manifestPath, `${JSON.stringify(ordered, null, 2)}\n`);
}

/** Beyond this a capture is a wall of pixels nobody reads. */
const MAX_CAPTURE_HEIGHT = 6000;

/**
 * Wait for the pictures on the page to have arrived.
 *
 * **Found live on 2026-09-13**, in the same shape as BUG-241 above: the Design
 * canvas capture showed an asset rail of empty boxes. Nothing was broken — the
 * thumbnails load lazily, the resize below brings them into view, and the
 * screenshot fired before the bytes landed. A capture of a picture gallery with
 * no pictures in it is evidence of the wrong thing, and would be read as a
 * defect that does not exist.
 *
 * Bounded and non-fatal: an image that genuinely cannot load must still be
 * *visible* as a broken one in the capture rather than stopping the round.
 */
async function imagesSettled(page: Page): Promise<void> {
  await page
    .waitForFunction(
      () =>
        Array.from(document.images).every((image) => image.complete || image.naturalWidth > 0),
      undefined,
      { timeout: 5_000 },
    )
    .catch(() => undefined);
}

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
    await recordCapture(page, capturedTo, null);
    return;
  }
  const needed = Math.min(await contentHeight(page), MAX_CAPTURE_HEIGHT);
  const height = Math.max(viewport.height, needed);
  if (height !== viewport.height) {
    await page.setViewportSize({ width: viewport.width, height });
  }
  // After the resize, not before: the taller viewport is what brings a lazy
  // image into range, so waiting first would wait for the wrong set.
  await imagesSettled(page);
  try {
    await page.screenshot({ path: capturedTo, fullPage: true });
  } finally {
    if (height !== viewport.height) await page.setViewportSize(viewport);
  }
  await recordCapture(page, capturedTo, viewport);
}

/**
 * Screenshot one element rather than the page around it.
 *
 * For evidence about a single card or panel, where the rest of the route is
 * noise that makes two captures harder to tell apart, not easier.
 */
export async function captureElement(target: Locator, path: string): Promise<void> {
  await target.scrollIntoViewIfNeeded();
  await imagesSettled(target.page());
  const capturedTo = capturePath(path);
  await target.screenshot({ path: capturedTo });
  await recordCapture(target.page(), capturedTo, target.page().viewportSize());
}
