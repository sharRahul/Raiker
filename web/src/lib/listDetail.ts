/**
 * QUI-L02 — the arithmetic behind the shared list-and-detail layout, kept out
 * of the component so it can be tested without a DOM.
 *
 * The selected item has its own address: `?item=<id>` beside whatever else the
 * hash already says (`#/extensions?tab=services&item=github`). An id is a
 * coordinate, like a session or task id: it names a row the owner can already
 * see and grants nothing.
 */

/** The narrowest the list may be dragged: one readable row. */
export const LIST_MIN_PX = 180;
/** The narrowest the detail may be dragged: one readable paragraph. */
export const DETAIL_MIN_PX = 320;

/** The `?item=` a hash names, or null. */
export function itemFromHash(hash: string): string | null {
  const value = new URLSearchParams(hash.split("?", 2)[1] ?? "").get("item");
  return value !== null && value.length > 0 && value.length <= 256 ? value : null;
}

/** TOOL-72 — the service an `?add=` link asks the Add dialog to open on. */
export function addFromHash(hash: string): string | null {
  const value = new URLSearchParams(hash.split("?", 2)[1] ?? "").get("add");
  return value !== null && /^[a-z0-9-]{1,64}$/.test(value) ? value : null;
}

/**
 * The same hash with its `?item=` set to `id` (or removed for null), every
 * other part kept in place.
 */
export function hashWithItem(hash: string, id: string | null): string {
  const [path, query = ""] = (hash || "#/").split("?", 2);
  const params = new URLSearchParams(query);
  if (id === null) params.delete("item");
  else params.set("item", id);
  const next = params.toString();
  return next.length > 0 ? `${path}?${next}` : path;
}

/**
 * The list's width after a drag, held so neither side becomes unreadable. A
 * container too narrow for both minimums keeps the list at its minimum.
 */
export function clampListWidth(requested: number, containerWidth: number): number {
  const most = Math.max(LIST_MIN_PX, containerWidth - DETAIL_MIN_PX);
  return Math.round(Math.min(Math.max(requested, LIST_MIN_PX), most));
}

/**
 * The id one step from `current` in `ids`, for the arrow keys. With nothing
 * selected, Down picks the first row and Up the last; the ends do not wrap.
 */
export function stepSelection(
  ids: readonly string[],
  current: string | null,
  direction: 1 | -1,
): string | null {
  if (ids.length === 0) return null;
  const index = current === null ? -1 : ids.indexOf(current);
  if (index === -1) return direction === 1 ? ids[0] : ids[ids.length - 1];
  return ids[Math.min(Math.max(index + direction, 0), ids.length - 1)];
}
