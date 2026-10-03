/*
 * UX-DESIGN-03 — research the owner chose to send with an image prompt.
 *
 * Design's Research runs a governed turn and shows what it found beside the
 * pages it read (BUG-281). Using that as a reference was copying prose into the
 * prompt by hand, which kept no record of where it came from and gave no moment
 * at which the owner said "yes, send this to the image provider". DEC-07 step 5
 * asks for both: references with research provenance, and a disclosure of
 * which content leaves the device — never research fed silently into a
 * provider.
 *
 * So a reference is three things, each bounded the way the executor bounds
 * them: a name (the question asked), a passage (the answer, as plain text) and
 * the pages it came from. Building one sends nothing. It is sent only when the
 * owner ticks it for the provider named beside it, and then as its own audited
 * argument, not spliced into their prompt.
 */
import type { TurnSourceView } from "./apiTypes";

/** The executor's bounds, mirrored so the page never builds one it will refuse. */
export const MAX_REFERENCES = 3;
export const MAX_REFERENCE_NAME_CHARS = 80;
export const MAX_REFERENCE_TEXT_CHARS = 1_000;
export const MAX_REFERENCE_SOURCES = 5;

export interface DesignReference {
  /** Stable within the page, so a chip can be removed or ticked by key. */
  key: string;
  name: string;
  text: string;
  sources: string[];
  /** Whether the owner has agreed to send it. Never true until they tick it. */
  consented: boolean;
}

/** Markdown read as plain text: the provider is drawing, not rendering. */
export function plainText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    // Raiker's own citation markers ([s1]) are for the reader, not the provider.
    .replace(/\s*\[s?\d{1,3}\]/g, "")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/[*_`>~]/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s+([.,;:!?])/g, "$1")
    .trim();
}

function clip(text: string, limit: number): string {
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit - 1);
  const space = cut.lastIndexOf(" ");
  return `${(space > limit * 0.6 ? cut.slice(0, space) : cut).trimEnd()}…`;
}

/**
 * The web pages a research turn read, cited ones first, as the provenance a
 * reference carries. Only http(s) locators: a reference's sources are pages a
 * reader can open, and nothing else is.
 */
export function referenceSources(
  sources: TurnSourceView[],
  citedIds: Set<string> | string[] = [],
): string[] {
  const cited = citedIds instanceof Set ? citedIds : new Set(citedIds);
  const urls = [...sources]
    .sort((left, right) => Number(cited.has(right.source_id)) - Number(cited.has(left.source_id)))
    .map((source) => source.locator.trim())
    .filter((url) => /^https?:\/\/\S+$/.test(url) && url.length <= 500);
  return [...new Set(urls)].slice(0, MAX_REFERENCE_SOURCES);
}

/** One research answer as a named, sourced, bounded reference — not yet consented. */
export function referenceFromResearch(
  question: string,
  answer: string,
  sources: TurnSourceView[],
  citedIds: Set<string> | string[] = [],
  key = `ref_${Date.now().toString(36)}`,
): DesignReference | null {
  const text = clip(plainText(answer), MAX_REFERENCE_TEXT_CHARS);
  const name = clip(question.trim() || "Research", MAX_REFERENCE_NAME_CHARS);
  if (text === "") return null;
  return { key, name, text, sources: referenceSources(sources, citedIds), consented: false };
}

/** What a generate request carries: only what the owner ticked, without page-only fields. */
export function referencesToSend(
  references: DesignReference[],
): { name: string; text: string; sources: string[] }[] {
  return references
    .filter((reference) => reference.consented)
    .slice(0, MAX_REFERENCES)
    .map(({ name, text, sources }) => ({ name, text, sources }));
}
