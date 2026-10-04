/**
 * DEC-09 step 5 — a page with unsaved work may ask before it is left.
 *
 * Every route change is a `hashchange`, so a page that unmounts on one took its
 * draft with it and nothing said so: Settings marked a section with a dot,
 * showed Save and Discard, and then dropped the edit the moment a rail link was
 * followed. A guard is a question the page asks the owner; when it says stay,
 * the shell puts the address back and does not change pages.
 *
 * The shell owns the answer because it owns the route: a page can only ask.
 * Reloading or closing the tab is the browser's own `beforeunload` prompt,
 * which a page registers alongside this through {@link guardUnload}.
 */

/** Returns `true` to let the navigation to `nextHash` go ahead. */
export type LeaveGuard = (nextHash: string) => boolean;

const guards = new Set<LeaveGuard>();

/** Ask `guard` before every route change until the returned function is called. */
export function registerLeaveGuard(guard: LeaveGuard): () => void {
  guards.add(guard);
  return () => {
    guards.delete(guard);
  };
}

/** Whether every registered guard lets the navigation to `nextHash` go ahead. */
export function mayLeave(nextHash: string): boolean {
  for (const guard of guards) {
    if (!guard(nextHash)) return false;
  }
  return true;
}

/**
 * The browser's own "Leave site?" prompt while `pending()` is true.
 * Returns the function that removes it.
 */
export function guardUnload(pending: () => boolean): () => void {
  const listener = (event: BeforeUnloadEvent) => {
    if (!pending()) return;
    event.preventDefault();
    // Older engines read the prompt from `returnValue`; none show its text.
    event.returnValue = "";
  };
  window.addEventListener("beforeunload", listener);
  return () => window.removeEventListener("beforeunload", listener);
}
