/**
 * QUI-L05 / QUI-L10 — the help panel's one piece of shared state.
 *
 * The Guide was a page of its own, thirteen screens long. It is a 360 px panel
 * now, opened from **?** in the top bar on the article for the page the owner
 * is on, from a "how this works" link, from the command palette's Help group,
 * or from an old `#/guide?section=` address. Every way in calls `openHelp`, so
 * there is one panel and one answer to which article it shows.
 */
import { partFromHash, sectionFromHash } from "./nav";

export const help = $state<{ open: boolean; slug: string | null; part: string | null }>({
  open: false,
  slug: null,
  part: null,
});

/**
 * Open the panel on an article, one part of it, or the article list.
 *
 * `slug` may carry its part as `slug#part`, which is how a help source chip's
 * locator names the part a turn read.
 */
export function openHelp(slug: string | null = null, part: string | null = null): void {
  const [name, fragment] = (slug ?? "").split("#", 2);
  help.slug = name || null;
  help.part = part ?? (fragment || null);
  help.open = true;
}

export function closeHelp(): void {
  help.open = false;
}

/** The article an old guide address names (`#/guide?section=memory`), or null. */
export function helpSlugFromHash(hash: string): string | null {
  return sectionFromHash(hash);
}

/** The part an address names (`#/guide?section=working-in-chat&part=approvals`), or null. */
export function helpPartFromHash(hash: string): string | null {
  return partFromHash(hash);
}

/** True when a hash is a guide address: the help panel answers it, not a page. */
export function isHelpAddress(hash: string): boolean {
  return /^#\/?guide(?:[?/]|$)/.test(hash);
}
