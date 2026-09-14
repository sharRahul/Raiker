/*
 * NEW-HOME-01 and NEW-MAP-01 — what a surface is showing, and when it was true.
 *
 * Two pages made the same mistake in two different ways, and both mistakes have
 * the same shape: `null` was used for *three* facts at once — nothing has been
 * read yet, the read failed, and there is nothing to report — and the page then
 * picked whichever reading flattered it.
 *
 * Home mapped a failed diagnostics read to zero runtime issues and could go on
 * to say **"Nothing needs you right now."** Nobody had checked. A readiness
 * claim made from an unread file is worse than no claim, because the owner acts
 * on it.
 *
 * The Knowledge Map kept the last graph it managed to load and went on
 * labelling it **"Live workspace graph"** — the label checked only that *some*
 * update had once happened. A graph an hour stale under a word meaning "now" is
 * the same defect pointing the other way.
 *
 * So: four states, named, and a value that can only be read out of the two that
 * have one. `stale` is the important one — it is what a page has after a
 * refresh fails, and the honest thing to do with it is go on showing it while
 * saying it is old. Throwing it away would be its own kind of lie, and calling
 * it current is the defect.
 */

/** What a surface knows about one thing it reads, and when it knew it. */
export type Freshness<T> =
  | { kind: "loading" }
  /** Read successfully, and nothing has failed since. */
  | { kind: "fresh"; value: T; at: number }
  /** Read successfully once; the newest attempt failed. Still worth showing. */
  | { kind: "stale"; value: T; at: number; reason: string }
  /** Never read successfully. There is nothing to show and nothing to claim. */
  | { kind: "unavailable"; reason: string };

/** Before the first read answers. */
export function loading<T>(): Freshness<T> {
  return { kind: "loading" };
}

/** A read answered. */
export function received<T>(value: T, at: number = Date.now()): Freshness<T> {
  return { kind: "fresh", value, at };
}

/**
 * A read failed. Whatever was already known survives as `stale`; a surface that
 * never had an answer says so rather than inventing one.
 */
export function failed<T>(previous: Freshness<T>, reason: string): Freshness<T> {
  if (previous.kind === "fresh" || previous.kind === "stale") {
    return { kind: "stale", value: previous.value, at: previous.at, reason };
  }
  return { kind: "unavailable", reason };
}

/** The value, or `null` when there is genuinely none. Never a stand-in. */
export function valueOf<T>(state: Freshness<T>): T | null {
  return state.kind === "fresh" || state.kind === "stale" ? state.value : null;
}

/**
 * Whether this is current enough to make a claim from.
 *
 * The one question a page must ask before saying anything reassuring. `stale`
 * deliberately answers **false**: an old answer is worth *showing* and is not
 * worth *asserting*, and conflating the two is what both defects were.
 */
export function isCurrent<T>(state: Freshness<T>): boolean {
  return state.kind === "fresh";
}

/** Whether there is anything at all to render. */
export function hasValue<T>(state: Freshness<T>): boolean {
  return state.kind === "fresh" || state.kind === "stale";
}

function ago(at: number, now: number): string {
  const seconds = Math.max(0, Math.round((now - at) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

/**
 * One line saying what the reader is looking at.
 *
 * *label* names the thing, so the sentence reads as itself on any surface:
 * `freshnessLabel(graph, "Workspace graph")` → "Workspace graph · updated 3
 * minutes ago". A stale line always carries both halves — when it was true, and
 * that the attempt to renew it failed — because either alone is misleading.
 */
export function freshnessLabel<T>(
  state: Freshness<T>,
  label: string,
  now: number = Date.now(),
): string {
  if (state.kind === "loading") return `${label} · loading`;
  if (state.kind === "fresh") return `${label} · updated ${ago(state.at, now)}`;
  if (state.kind === "stale") {
    return `${label} · last updated ${ago(state.at, now)} · refresh failed (${state.reason})`;
  }
  return `${label} · unavailable (${state.reason})`;
}
