/**
 * Where a notice leads, and when the page being shown already says it.
 *
 * BUG-309. The dock showed *Approval needed* on Approvals, over the queue that
 * listed the same approval, because nothing knew which page a notice was about.
 * The approval card had learned not to cover its own queue (FIXED-621); the
 * notice about that approval had not. This is the rule for every destination,
 * not a patch for one: a notice whose subject is the page on screen is already
 * answered by that page.
 */
import type { Notification as RaikerNotification } from "./apiTypes";

/**
 * Raised on `window` whenever this page marks a notice read. The bell and the
 * dock each read notifications on their own; without this, marking one read in
 * either left the other counting it until its next poll — the bell still said
 * *1* on Approvals after the dock had read the approval notice.
 */
export const NOTICES_CHANGED = "raiker:notices-changed";

/** Tell every reader on this page that the notice record changed. */
export function announceNoticesChanged(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(NOTICES_CHANGED));
}

/** The record every notice is kept in, whatever its kind. */
export const NOTICE_RECORD = "#/observe?tab=notifications";

/** Kinds with a page of their own. Everything else lands on the record. */
const DESTINATIONS: Record<string, string> = {
  approval_pending: "#/approvals",
  critical_approval_pending: "#/approvals",
  task_finished: "#/tasks",
  // BUG-322 — the notice about a damaged index opens its repair.
  search_index_damaged: "#/observe?tab=overview&repair=indexes",
};

/** The page a notice of this kind opens. */
export function noticeDestination(kind: string): string {
  return DESTINATIONS[kind] ?? NOTICE_RECORD;
}

/** The route part of an address: `#/tasks?task=t1` → `#/tasks`. */
function routeOf(hash: string): string {
  return hash.split("?")[0] ?? "";
}

/**
 * True when the page on screen is where this notice would take the owner, so
 * the page itself already shows what the notice says. Only kinds with a page
 * of their own qualify: the record lists every notice, and marking something
 * read because the owner happened to open the record would be a guess.
 */
export function answeredByPage(notification: RaikerNotification, hash: string): boolean {
  const destination = DESTINATIONS[notification.kind];
  return destination !== undefined && routeOf(hash) === destination;
}

/**
 * Kinds the approval card already presents on every page it stands on.
 *
 * The card is on every page but Approvals, and Approvals answers the notice
 * itself (BUG-309), so docking an approval notice would repeat what is on
 * screen — and covered page controls where it did. It stays unread: the bell
 * counts it and the record lists it, because seeing the card is not reading
 * the notice.
 */
const SHOWN_BY_APPROVAL_CARD = new Set(["approval_pending", "critical_approval_pending"]);

/** True when the approval card is the place this notice is already shown. */
export function shownByApprovalCard(notification: RaikerNotification): boolean {
  return SHOWN_BY_APPROVAL_CARD.has(notification.kind);
}

/** True on the record itself, where a docked notice would repeat a row. */
export function onNoticeRecord(hash: string): boolean {
  return routeOf(hash) === "#/observe" && hash.includes("tab=notifications");
}
