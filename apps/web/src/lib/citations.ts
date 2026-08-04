// C6 — reading the citation markers a model wrote, against the ledger of what a
// turn actually read.
//
// The rule everything here follows: **the ledger decides.** A marker is only a
// citation when the runtime recorded a source with that id for that turn. A
// model that invents `[s9]`, or a file that happens to contain the characters
// `[s1]`, produces nothing — no chip, no link, no implied provenance. That is
// what keeps a citation from being something a model can simply assert.
import type { TurnSourceView } from "./apiTypes";

/** A citation marker: `[s1]`. Bounded digits so the scan cannot run away. */
const MARKER_RE = /\[(s\d{1,3})\]/g;

/** The sources recorded for one turn, in the order the turn used them. */
export function sourcesForTurn(
  sources: TurnSourceView[],
  turnId: string | null | undefined,
): TurnSourceView[] {
  if (turnId === null || turnId === undefined || turnId === "") return [];
  return sources
    .filter((source) => source.turn_id === turnId)
    .sort((a, b) => a.ordinal - b.ordinal);
}

/** Ids the answer text cites *and* the ledger knows about. */
export function citedSourceIds(
  answer: string,
  known: readonly TurnSourceView[],
): Set<string> {
  const ledger = new Set(known.map((source) => source.source_id));
  const cited = new Set<string>();
  for (const match of answer.matchAll(MARKER_RE)) {
    if (ledger.has(match[1])) cited.add(match[1]);
  }
  return cited;
}

/** The id set the Markdown renderer is allowed to turn into chips. */
export function renderableCitations(sources: readonly TurnSourceView[]): Set<string> {
  return new Set(sources.map((source) => source.source_id));
}

/** Bound on the sentence sent as a locating quote. A paragraph is not a quote. */
const MAX_QUOTE_CHARS = 600;

/**
 * The sentence a citation marker terminates.
 *
 * This is the only thing that knows *which part* of a source an answer rests
 * on: the ledger records that the turn read the file, and the sentence carrying
 * `[s1]` is the claim about what in it mattered. The server uses it to find an
 * offset and nothing else — it can only ever mark text the source already
 * contains — and a paraphrase that matches nothing simply yields no highlight.
 */
export function sentenceAround(answer: string, sourceId: string): string {
  const marker = `[${sourceId}]`;
  const at = answer.indexOf(marker);
  if (at < 0) return "";
  // Back to the end of the *previous* sentence, forward past this one's stop.
  // Models place the marker on either side of the full stop ("… 2029 [s1]." and
  // "… 2029.[s1]"), so a stop sitting immediately before the marker belongs to
  // the cited sentence and must not be mistaken for the boundary in front of it.
  const before = answer.slice(0, at).replace(/\s*[.!?]?\s*$/, "");
  const startMatch = /[.!?\n][^.!?\n]*$/.exec(before);
  const start = startMatch === null ? 0 : startMatch.index + 1;
  const after = answer.slice(at + marker.length);
  const endMatch = /[.!?\n]/.exec(after);
  const end = at + marker.length + (endMatch === null ? after.length : endMatch.index);
  return answer.slice(start, end).trim().slice(0, MAX_QUOTE_CHARS);
}

/**
 * An excerpt split into before / passage / after.
 *
 * The marked run is a *slice of the text*, never markup the source chose — the
 * same rule the file inspector has always followed, kept in one place now that
 * two surfaces render a highlighted passage.
 */
export function splitExcerpt(
  excerpt: string,
  start: number,
  length: number,
): { before: string; passage: string; after: string } {
  if (start < 0 || length <= 0) return { before: excerpt, passage: "", after: "" };
  return {
    before: excerpt.slice(0, start),
    passage: excerpt.slice(start, start + length),
    after: excerpt.slice(start + length),
  };
}
