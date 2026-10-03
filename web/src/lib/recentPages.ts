/**
 * UX-SETPOP-02 — the destinations this viewer opened last, for the More window.
 *
 * DEC-09 gave page *search* to the command palette, which already finds every
 * page, every Settings section and the commands beside them. More keeps the
 * stable groups and the one thing a list can do that a search box cannot:
 * show where you were a moment ago without asking you to remember its name.
 *
 * A per-viewer convenience, so it lives in this browser and nowhere else. A
 * storage that throws — a private window, blocked site data — leaves the list
 * empty rather than breaking navigation.
 */
import { NAV_ITEMS } from "./nav";

const KEY = "raiker.recent-pages";
const KEEP = 6;

function read(): string[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((entry): entry is string => typeof entry === "string") : [];
  } catch {
    return [];
  }
}

/** Record that this route was opened. Unknown routes are not remembered. */
export function rememberPage(route: string): void {
  if (!NAV_ITEMS.some((item) => item.id === route)) return;
  const next = [route, ...read().filter((entry) => entry !== route)].slice(0, KEEP);
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Remembering is a convenience; a refusal costs nothing but the list.
  }
}

/** The most recent destinations, newest first, leaving out the one you are on. */
export function recentPages(current: string, limit = 4): typeof NAV_ITEMS {
  return read()
    .filter((route) => route !== current)
    .map((route) => NAV_ITEMS.find((item) => item.id === route))
    .filter((item): item is (typeof NAV_ITEMS)[number] => item !== undefined)
    .slice(0, limit);
}
