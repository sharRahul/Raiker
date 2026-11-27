/**
 * Raiker Notes — Obsidian syntax turned into something the app's safe Markdown
 * renderer can show, without ever emitting markup of its own.
 *
 * Wikilinks become in-app `#/notes?note=…` links (the renderer's `inAppLinks`
 * option allows only addresses inside this app), embeds become a labelled
 * link, and `#tags` become a search. Everything else is ordinary Markdown.
 */

export interface NoteLinkTarget {
  target: string;
  heading: string;
  alias: string;
  embed: boolean;
}

const WIKILINK = /(!?)\[\[([^[\]\n]+?)\]\]/g;
const TAG = /(^|\s)#([\p{L}\p{N}_][\p{L}\p{N}_/-]*)/gu;

export function parseLinkBody(body: string, embed = false): NoteLinkTarget {
  const [targetPart, alias = ""] = body.split("|", 2);
  const [target, heading = ""] = targetPart.split("#", 2);
  return { target: target.trim(), heading: heading.replace(/^\^/, "").trim(), alias: alias.trim(), embed };
}

/** Only the characters Markdown would read as syntax are escaped in link text. */
function linkText(text: string): string {
  return text.replace(/[[\]\\*_`]/g, (char) => `\\${char}`);
}

export function noteHref(target: string, heading = ""): string {
  const query = `note=${encodeURIComponent(target)}${heading ? `&heading=${encodeURIComponent(heading)}` : ""}`;
  return `#/notes?${query}`;
}

/** Note source → Markdown the app's renderer shows with working wikilinks. */
export function noteToMarkdown(source: string): string {
  const body = source.replace(/^---\n[\s\S]*?\n(---|\.\.\.)\n?/, "");
  const lines = body.split("\n");
  let fenced = false;
  return lines
    .map((line) => {
      if (/^\s*(```|~~~)/.test(line)) {
        fenced = !fenced;
        return line;
      }
      if (fenced) return line;
      return line
        .replace(/\s\^[A-Za-z0-9-]+\s*$/, "")
        .replace(WIKILINK, (_match, bang: string, inner: string) => {
          const link = parseLinkBody(inner, bang === "!");
          const shown = link.alias || (link.heading ? `${link.target} › ${link.heading}` : link.target) || link.heading;
          const label = link.embed ? `↳ ${shown}` : shown;
          return `[${linkText(label)}](${noteHref(link.target, link.heading)})`;
        })
        .replace(TAG, (match, lead: string, tag: string) =>
          // A tag needs one character that is not a digit (`#1984` is not a tag).
          /^[\p{N}/-]+$/u.test(tag) ? match : `${lead}[#${linkText(tag)}](#/notes?search=${encodeURIComponent(`tag:${tag}`)})`,
        );
    })
    .join("\n");
}

/** The `[[` the caret is inside, for suggestions: the text typed after it, or null. */
export function openLinkQuery(text: string, caret: number): { start: number; query: string } | null {
  const before = text.slice(0, caret);
  const start = before.lastIndexOf("[[");
  if (start < 0) return null;
  const typed = before.slice(start + 2);
  if (typed.includes("]]") || typed.includes("\n") || typed.length > 80) return null;
  return { start: start + 2, query: typed };
}

/** Names that match what was typed, best first: prefix, then word start, then anywhere. */
export function suggestNotes(names: string[], query: string, limit = 8): string[] {
  const wanted = query.trim().toLowerCase();
  const scored = names
    .map((name) => {
      const lower = name.toLowerCase();
      const rank = !wanted ? 3 : lower.startsWith(wanted) ? 0 : lower.includes(` ${wanted}`) || lower.includes(`/${wanted}`) ? 1 : lower.includes(wanted) ? 2 : -1;
      return { name, rank };
    })
    .filter((item) => item.rank >= 0)
    .sort((a, b) => a.rank - b.rank || a.name.length - b.name.length || a.name.localeCompare(b.name));
  return scored.slice(0, limit).map((item) => item.name);
}

/** Positions for a small radial local graph: the note at the centre, neighbours around it. */
export function radialLayout(
  centre: string,
  nodes: string[],
  size = 260,
): Record<string, { x: number; y: number }> {
  const half = size / 2;
  const others = nodes.filter((node) => node !== centre);
  const radius = half - 34;
  const placed: Record<string, { x: number; y: number }> = { [centre]: { x: half, y: half } };
  others.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(1, others.length) - Math.PI / 2;
    placed[node] = { x: half + radius * Math.cos(angle), y: half + radius * Math.sin(angle) };
  });
  return placed;
}
