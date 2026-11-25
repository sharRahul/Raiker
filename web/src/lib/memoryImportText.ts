/**
 * RU-16 — memories written for another agent, read as records to review.
 *
 * Hermes Agent keeps `MEMORY.md` and `USER.md` as entries separated by a line
 * holding `§`; Claude Code's and Cursor's notes are Markdown bullet lists. Each
 * entry becomes one record with `scope: "user"`, shown in Memory's import review
 * where the owner keeps or skips it — nothing is stored before Import.
 * Headings, empty entries and anything over the per-record limit are left out.
 */
export const MAX_IMPORTED_TEXT = 2000;
const SECTION = /^\s*§\s*$/m;
const BULLET = /^\s*(?:[-*+]|\d+[.)])\s+(.*)$/;

export function memoriesFromText(text: string): { text: string; scope: string }[] {
  const body = text.replace(/\r\n?/g, "\n").replace(/^\uFEFF/, "");
  let entries: string[];
  if (SECTION.test(body)) {
    entries = body.split(SECTION);
  } else if (body.split("\n").some((line) => BULLET.test(line))) {
    entries = body
      .split("\n")
      .map((line) => BULLET.exec(line)?.[1] ?? "")
      .filter(Boolean);
  } else {
    entries = body.split(/\n\s*\n/);
  }
  const seen = new Set<string>();
  const records: { text: string; scope: string }[] = [];
  for (const entry of entries) {
    const cleaned = entry
      .split("\n")
      .filter((line) => !/^\s*#/.test(line))
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
    if (!cleaned || cleaned.length > MAX_IMPORTED_TEXT || seen.has(cleaned)) continue;
    seen.add(cleaned);
    records.push({ text: cleaned, scope: "user" });
  }
  return records;
}
