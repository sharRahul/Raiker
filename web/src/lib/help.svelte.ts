/**
 * QUI-L05 / QUI-L10 — the help panel's one piece of shared state.
 *
 * The Guide was a page of its own, thirteen screens long. It is a 360 px panel
 * now, opened from **?** in the top bar on the article for the page the owner
 * is on, from a "how this works" link, from the command palette's Help group,
 * or from an old `#/guide?section=` address. Every way in calls `openHelp`, so
 * there is one panel and one answer to which article it shows.
 */
import { sectionFromHash } from "./nav";

export const help = $state<{ open: boolean; slug: string | null }>({ open: false, slug: null });

/** Open the panel on an article, or on the article list when `slug` is null. */
export function openHelp(slug: string | null = null): void {
  help.slug = slug;
  help.open = true;
}

export function closeHelp(): void {
  help.open = false;
}

/** The article an old guide address names (`#/guide?section=memory`), or null. */
export function helpSlugFromHash(hash: string): string | null {
  return sectionFromHash(hash);
}

/** True when a hash is a guide address: the help panel answers it, not a page. */
export function isHelpAddress(hash: string): boolean {
  return /^#\/?guide(?:[?/]|$)/.test(hash);
}
