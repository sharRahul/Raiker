/**
 * Every destination this app has, derived from the app's own registry.
 *
 * Found 2026-09-05, while walking the product at four widths.
 *
 * Two specs sweep "every page" — `all-pages-live` photographs them and
 * `all-pages-theme-live` checks each one in both themes — and each carried its
 * own hand-copied list. `all-pages-live` even carries a comment saying *"The
 * sweep is only a sweep if it covers every tab the nav offers"*, written the
 * last time a copy had drifted. Both had drifted again, in the same two
 * directions:
 *
 * * **Two routes that no longer exist.** `extensions?tab=channels` — Channels
 *   left Extensions for the Messaging destination — and `observe?tab=diagnostics`,
 *   which is an alias onto Overview. Each was being photographed as though it
 *   were a page of its own.
 * * **Twenty destinations that do exist and neither list held.** Design,
 *   Messaging and the Guide; all six Models tabs; all ten Settings sections. A
 *   regression on any of them would have gone unseen by both sweeps.
 *
 * A hand-copied list of the nav is the same defect as a hand-copied list of the
 * settings rail, and `nav.test.ts` already refused that one: *"The rail itself,
 * not a copy of it."* This is the rail itself. `NAV_ITEMS` is the route registry
 * — `routeFromHash` resolves against it, so a destination not in it is not
 * reachable at all — and `HUB_TABS` is what each hub holds. A destination added
 * to either is swept from the next run, with nothing to remember.
 */
import { HUB_TABS, NAV_ITEMS } from "../src/lib/nav";

export interface Destination {
  /** The hash path, without the leading `#/`. */
  readonly route: string;
  /** A stable, readable file name for a capture of it. */
  readonly name: string;
}

/**
 * Every destination, in nav order, a hub expanded into one entry per tab.
 *
 * Named by what it is rather than by its position, so adding a destination in
 * the middle does not rename the captures after it. (The theme sweep already
 * named its evidence this way; the page sweep used ordinals, and its
 * `01-`…`25-` files are replaced by these.)
 */
export const DESTINATIONS: readonly Destination[] = NAV_ITEMS.flatMap((item) => {
  const tabs = HUB_TABS[item.id];
  if (tabs === undefined) return [{ route: item.id, name: item.id }];
  return tabs.map((tab) => ({ route: `${item.id}?tab=${tab}`, name: `${item.id}-${tab}` }));
});

/**
 * The widths a responsive check walks.
 *
 * Not arbitrary: a narrow phone, the width where the navigation rail becomes a
 * drawer, a small laptop, and the width the rest of the suite runs at. The
 * three mobile bleeds of
 * [FIXED-395](../../../docs/plans/FIXED_ITEMS.md) were all found at the first.
 */
export const WIDTHS: readonly { readonly label: string; readonly width: number; readonly height: number }[] = [
  { label: "360", width: 360, height: 780 },
  { label: "768", width: 768, height: 1000 },
  { label: "1024", width: 1024, height: 900 },
  { label: "1440", width: 1440, height: 1000 },
];

/**
 * Anything sticking out past the right edge of the viewport, ignoring what a
 * scroll container is *supposed* to clip.
 *
 * A code block, a wide table and a tab strip all overflow their own box on
 * purpose and scroll inside it; their children's layout boxes still report
 * positions past the viewport, so a check that only measured `getBoundingClientRect`
 * called every one of them a bleed. Walking up for an ancestor that clips or
 * scrolls horizontally is what tells a real bleed from a working scroll
 * container — without it this returns noise and gets switched off.
 *
 * Returns a short, readable description per offender, capped so one broken
 * layout cannot produce a thousand-line failure.
 */
export async function horizontalBleed(
  page: import("@playwright/test").Page,
): Promise<string[]> {
  return page.evaluate(() => {
    const found: string[] = [];
    const root = document.documentElement;
    if (root.scrollWidth > root.clientWidth + 1) {
      found.push(`the page itself scrolls sideways (${root.scrollWidth} > ${root.clientWidth})`);
    }
    for (const element of Array.from(document.querySelectorAll<HTMLElement>("main#main *"))) {
      const box = element.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      if (box.right <= window.innerWidth + 1.5) continue;
      if (getComputedStyle(element).position === "fixed") continue;
      let ancestor: HTMLElement | null = element.parentElement;
      let clipped = false;
      while (ancestor !== null) {
        if (/auto|scroll|hidden/.test(getComputedStyle(ancestor).overflowX)) {
          clipped = true;
          break;
        }
        ancestor = ancestor.parentElement;
      }
      if (clipped) continue;
      const classes = element.className.toString().split(/\s+/).slice(0, 2).join(".");
      found.push(
        `${element.tagName.toLowerCase()}${classes ? `.${classes}` : ""} reaches ${Math.round(box.right)}px`,
      );
      if (found.length >= 8) break;
    }
    return found;
  });
}

/**
 * The one console error a sweep may forgive, and the condition it has to meet.
 *
 * A host with no route to `huggingface.co` answers the Hub reads `503`, and the
 * browser writes "Failed to load resource" for each. That is the *host's*
 * network rather than a defect in Raiker — but the same message is what a real
 * breakage looks like, so it is not waved away on that reasoning alone.
 *
 * Attach this to a page before the sweep starts. It watches for a 5xx from the
 * Hub routes; `filter` then drops matching console lines **only if one was
 * seen**, and the caller is expected to assert that the panel is telling the
 * owner the Hub could not be reached
 * ([FIXED-414](../../../docs/plans/FIXED_ITEMS.md)). A silent panel and a `503`
 * is still a failure.
 */
export function hubReachability(page: import("@playwright/test").Page): {
  refused: () => boolean;
  filter: (errors: readonly string[]) => string[];
} {
  let refused = false;
  page.on("response", (response) => {
    if (response.url().includes("/api/hugging-face/") && response.status() >= 500) {
      refused = true;
    }
  });
  return {
    refused: () => refused,
    filter: (errors) =>
      refused ? errors.filter((text) => !/Failed to load resource.*5\d\d/.test(text)) : [...errors],
  };
}
