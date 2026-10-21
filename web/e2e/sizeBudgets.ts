/**
 * QUI-G01 — size budgets for every destination.
 *
 * With an empty workspace a destination page fits in one screen at 1440×900
 * and 1.25 screens at 1280×800; a Settings sub-page fits in 1.5 screens; and
 * no more than 60 interactive controls are visible at once, list rows aside.
 *
 * The sweep starts as a report (`all-pages-live.spec.ts` writes it) and becomes
 * a failing check once the long pages are rebuilt (01, QUI-L06 – L11).
 */
import type { Page } from "@playwright/test";

export const BUDGET_VIEWPORTS = [
  { label: "1440", width: 1440, height: 900, screens: 1 },
  { label: "1280", width: 1280, height: 800, screens: 1.25 },
] as const;

/** Settings sub-pages are allowed more room than a destination page. */
export const SETTINGS_SCREENS = 1.5;
export const MAX_VISIBLE_CONTROLS = 60;

export interface PageSize {
  /** Full scroll height of the routed view, in CSS pixels. */
  height: number;
  /** Interactive controls inside the viewport, excluding list and table rows. */
  controls: number;
}

/** Measure the routed view the way the budget is written. */
export async function measurePage(page: Page): Promise<PageSize> {
  return page.evaluate(() => {
    const main = document.querySelector("main#main") as HTMLElement | null;
    const scroller = document.scrollingElement as HTMLElement | null;
    const height = Math.max(main?.scrollHeight ?? 0, scroller?.scrollHeight ?? 0);
    const selector =
      "button, a[href], input:not([type=hidden]), select, textarea, [role=button], [role=tab], [role=menuitem], [role=switch], [role=checkbox]";
    let controls = 0;
    for (const element of document.querySelectorAll<HTMLElement>(selector)) {
      if (element.closest("li, tr, [role=row], [role=listitem]")) continue;
      const box = element.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      if (box.bottom <= 0 || box.top >= window.innerHeight || box.right <= 0 || box.left >= window.innerWidth) continue;
      controls += 1;
    }
    return { height, controls };
  });
}

/** What a page is over budget by, in words; empty when it is within it. */
export function overBudget(route: string, size: PageSize, viewport: { height: number; screens: number }): string[] {
  const screens = route.startsWith("settings") ? Math.max(viewport.screens, SETTINGS_SCREENS) : viewport.screens;
  const limit = Math.round(viewport.height * screens);
  const over: string[] = [];
  if (size.height > limit) over.push(`${size.height}px tall (budget ${limit}px)`);
  if (size.controls > MAX_VISIBLE_CONTROLS) over.push(`${size.controls} controls (budget ${MAX_VISIBLE_CONTROLS})`);
  return over;
}
