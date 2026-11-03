/**
 * Voice spec §5.3 — an answer as speakable sentences, ready before it ends.
 *
 * Speaking starts after the first sentence rather than after the whole answer,
 * so text is cut into sentences as it streams. A cut is made at `.`, `!` or `?`
 * followed by whitespace — not after a known abbreviation ("Dr.", "e.g."), a
 * single initial ("J."), or a decimal ("3.5") — and a sentence longer than
 * {@link MAX_SENTENCE_CHARS} is cut at the last comma or space before it.
 * Markdown is reduced to what is read aloud with `speechText()` first.
 */
import { speechText } from "../voice";

export const MAX_SENTENCE_CHARS = 220;

const ABBREVIATIONS = new Set([
  "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e", "approx", "no", "fig",
  "inc", "ltd", "co", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
]);

function endsSentence(text: string, index: number): boolean {
  const mark = text[index];
  if (mark !== "." && mark !== "!" && mark !== "?") return false;
  const next = text[index + 1];
  if (next !== undefined && !/\s/.test(next)) return false;
  if (mark !== ".") return true;
  const before = text.slice(0, index).match(/([A-Za-z.]+)$/)?.[1] ?? "";
  if (ABBREVIATIONS.has(before.toLowerCase())) return false;
  if (/^[A-Z]$/.test(before)) return false; // an initial
  if (/\d$/.test(text.slice(0, index)) && /^\s*\d/.test(text.slice(index + 1))) return false;
  return true;
}

function cutLong(sentence: string): string[] {
  const out: string[] = [];
  let rest = sentence.trim();
  while (rest.length > MAX_SENTENCE_CHARS) {
    const window = rest.slice(0, MAX_SENTENCE_CHARS);
    const at = Math.max(window.lastIndexOf(", "), window.lastIndexOf("; "));
    const cut = at > MAX_SENTENCE_CHARS / 3 ? at + 1 : window.lastIndexOf(" ") > 0 ? window.lastIndexOf(" ") : MAX_SENTENCE_CHARS;
    out.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trim();
  }
  if (rest) out.push(rest);
  return out;
}

/** Every complete sentence in `text`, and what is left waiting for more. */
export function takeSentences(text: string): { sentences: string[]; rest: string } {
  const sentences: string[] = [];
  let start = 0;
  for (let i = 0; i < text.length; i += 1) {
    if (endsSentence(text, i)) {
      const piece = text.slice(start, i + 1).trim();
      if (piece) sentences.push(...cutLong(piece));
      start = i + 1;
    }
  }
  return { sentences, rest: text.slice(start) };
}

/** A whole answer as sentences to speak. */
export function splitSentences(markdown: string): string[] {
  const readable = speechText(markdown);
  const { sentences, rest } = takeSentences(readable);
  return [...sentences, ...cutLong(rest)].filter((s) => /[\p{L}\p{N}]/u.test(s));
}

/**
 * Sentences from a streaming answer: feed it the text so far, get back the
 * sentences that became complete since the last feed.
 */
export function createSentenceStream(): { push(textSoFar: string): string[]; finish(): string[] } {
  let consumed = 0;
  let buffer = "";
  return {
    push(textSoFar) {
      buffer += textSoFar.slice(consumed);
      consumed = textSoFar.length;
      const { sentences, rest } = takeSentences(buffer);
      buffer = rest;
      return sentences;
    },
    finish() {
      const out = cutLong(buffer).filter((s) => /[\p{L}\p{N}]/u.test(s));
      buffer = "";
      return out;
    },
  };
}
