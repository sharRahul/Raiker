/**
 * QUI-L12 — Work's lists paginate after 50 rows.
 *
 * One number for every list on the Work page, so Tasks, Goals and Projects
 * cannot each pick their own.
 */
export const PAGE_SIZE = 50;

/** The rows a list draws when it has shown `shown` of `items`. */
export function page<T>(items: readonly T[], shown: number): T[] {
  return items.slice(0, Math.max(PAGE_SIZE, shown));
}
