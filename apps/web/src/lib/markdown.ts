/**
 * A small, dependency-free, escape-first Markdown renderer for model output.
 *
 * Security posture — the one the file-inspector design already states
 * (*"Markdown is sanitized before rendering"*, *"Preview renderers never
 * execute embedded code or macros"*) — is enforced structurally rather than by
 * filtering:
 *
 * 1. **Escape first, mark up second.** Every run of model text passes through
 *    `escapeHtml` *before* any tag is produced. Raw HTML in a model response is
 *    therefore data: `<script>alert(1)</script>` renders as those literal
 *    characters. There is no sanitiser to bypass because raw HTML is never
 *    parsed as HTML in the first place.
 * 2. **A closed tag set.** Only the tags written literally in this file can
 *    reach the DOM — headings, paragraphs, lists, blockquote, table, `pre`,
 *    `code`, `a`, `strong`, `em`, `del`, `hr`, `br`. No attribute is ever
 *    copied from the source: the only attributes emitted are a `class` from a
 *    fixed allowlist, and `href`, which must match `http(s):` or `mailto:` or
 *    the link is downgraded to plain text. `javascript:`, `data:` and
 *    `vbscript:` URLs can never be emitted.
 * 3. **No remote fetches.** Images render as a labelled link, never an `<img>`,
 *    so a model cannot make the browser call out to a third-party host (a
 *    tracking pixel) merely by answering a question. Raiker's built UI makes no
 *    external requests and that stays true with markdown on.
 *
 * The output is a string of HTML intended for `{@html}` in `Markdown.svelte`.
 * That is the only supported caller, and it is safe *because of the above* —
 * do not feed this function's output through any other escaping step, and do
 * not extend the emitters with source-derived attributes.
 */

import { highlight, languageLabel } from "./highlight";
import { ICON_PATHS, type IconName } from "./icons";

/**
 * One inline SVG glyph from the shipped icon set.
 *
 * Literal markup built from a fixed, in-repo path table — nothing here is
 * derived from model output, so it does not widen the closed tag set in any way
 * that source text can reach. Used for the copy action on a code block, which
 * reads better as a glyph than as the word "Copy code" repeated down a
 * transcript.
 */
function iconSvg(name: IconName, state: string): string {
  const paths = ICON_PATHS[name].map((d) => `<path d="${d}" />`).join("");
  return (
    `<svg class="md-copy-glyph" data-state="${state}" width="14" height="14" viewBox="0 0 24 24" ` +
    `fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" ` +
    `stroke-linejoin="round" aria-hidden="true">${paths}</svg>`
  );
}

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

/** Neutralise every character that could open a tag, attribute or entity. */
export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (char) => HTML_ESCAPES[char]);
}

/** Schemes a link is allowed to carry. Anything else renders as plain text. */
const SAFE_URL = /^(?:https?:\/\/|mailto:)\S+$/i;

/** Language hints we are willing to echo into a `class`, once normalised. */
const LANGUAGE_TOKEN = /^[A-Za-z0-9][A-Za-z0-9+#._-]{0,23}$/;

const BLOCK_MARKERS = {
  fence: /^ {0,3}(`{3,}|~{3,})\s*([^`\n]*)$/,
  heading: /^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$/,
  rule: /^ {0,3}([-*_])\s*(?:\1\s*){2,}$/,
  quote: /^ {0,3}>\s?(.*)$/,
  listItem: /^(\s*)([-*+]|\d{1,9}[.)])(\s+)(.*)$/,
};

/** Render a Markdown document to a safe HTML fragment. */
export function renderMarkdown(source: string): string {
  if (source.trim() === "") return "";
  const lines = source.replace(/\r\n?/g, "\n").replace(/\t/g, "    ").split("\n");
  return renderBlocks(lines);
}

function renderBlocks(lines: string[]): string {
  const out: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim() === "") {
      i += 1;
      continue;
    }

    const fence = BLOCK_MARKERS.fence.exec(line);
    if (fence) {
      const consumed = renderFence(lines, i, fence[1], fence[2]);
      out.push(consumed.html);
      i = consumed.next;
      continue;
    }

    const heading = BLOCK_MARKERS.heading.exec(line);
    if (heading) {
      const level = heading[1].length;
      out.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      i += 1;
      continue;
    }

    if (BLOCK_MARKERS.rule.test(line)) {
      out.push("<hr />");
      i += 1;
      continue;
    }

    if (BLOCK_MARKERS.quote.test(line)) {
      const inner: string[] = [];
      while (i < lines.length) {
        const quoted = BLOCK_MARKERS.quote.exec(lines[i]);
        if (!quoted) break;
        inner.push(quoted[1]);
        i += 1;
      }
      out.push(`<blockquote>${renderBlocks(inner)}</blockquote>`);
      continue;
    }

    const table = renderTable(lines, i);
    if (table) {
      out.push(table.html);
      i = table.next;
      continue;
    }

    if (BLOCK_MARKERS.listItem.test(line)) {
      const list = renderList(lines, i);
      out.push(list.html);
      i = list.next;
      continue;
    }

    const paragraph: string[] = [];
    while (i < lines.length && lines[i].trim() !== "" && !startsBlock(lines, i)) {
      paragraph.push(lines[i].trim());
      i += 1;
    }
    if (paragraph.length > 0) {
      // Soft line breaks are preserved: a model that lays a reply out over
      // several lines meant those lines, and a chat transcript is not prose
      // reflow. This matches how the plain-text bubble behaved before.
      out.push(`<p>${paragraph.map(renderInline).join("<br />")}</p>`);
    } else {
      // Defensive: a line that opens a block the loop above did not consume
      // would otherwise spin forever.
      i += 1;
    }
  }

  return out.join("");
}

/** Would `lines[i]` open a new block? Used to close a running paragraph. */
function startsBlock(lines: string[], i: number): boolean {
  const line = lines[i];
  return (
    BLOCK_MARKERS.fence.test(line) ||
    BLOCK_MARKERS.heading.test(line) ||
    BLOCK_MARKERS.rule.test(line) ||
    BLOCK_MARKERS.quote.test(line) ||
    BLOCK_MARKERS.listItem.test(line) ||
    renderTable(lines, i) !== null
  );
}

function renderFence(
  lines: string[],
  start: number,
  fence: string,
  info: string,
): { html: string; next: number } {
  const closer = new RegExp(`^ {0,3}\\${fence[0]}{${fence.length},}\\s*$`);
  const body: string[] = [];
  let i = start + 1;
  while (i < lines.length && !closer.test(lines[i])) {
    body.push(lines[i]);
    i += 1;
  }
  // An unterminated fence still renders as code — truncated or still-streaming
  // model output is the common case, and showing it as a code block is the
  // honest reading of what the model was writing.
  const next = i < lines.length ? i + 1 : i;
  const language = info.trim().split(/\s+/)[0] ?? "";
  const named = LANGUAGE_TOKEN.test(language);
  const token = named ? language.toLowerCase() : "";
  const source = body.join("\n");

  // BUG-23 — every block carries a language label and a keyboard-operable copy
  // action, and its contents are highlighted by the locally-shipped grammar
  // scanner. The rules of this file are unchanged: the classes below are
  // literals, `data-lang` is the normalised token matched against
  // LANGUAGE_TOKEN (never raw source), and `highlight()` escapes every token it
  // emits. The copy button carries no handler — Markdown.svelte delegates one
  // click listener on the wrapper, so no source-derived script can ride along.
  const label = named ? languageLabel(language) : "Code";
  // BUG-23 / composer polish — the copy action is a glyph, not a word. A
  // transcript full of "Copy code" reads as chrome competing with the answer;
  // the icon is the same affordance, quieter, and still fully labelled for a
  // screen reader and a tooltip. All three states ship in the markup and CSS
  // picks one, so the delegated handler only ever sets an attribute — it never
  // writes text into the button.
  const header =
    `<div class="md-code-head">` +
    `<span class="md-code-lang">${escapeHtml(label)}</span>` +
    `<button type="button" class="md-copy" data-md-copy data-copy-state="idle" ` +
    `aria-label="Copy code" title="Copy code">` +
    iconSvg("copy", "idle") +
    iconSvg("check", "copied") +
    iconSvg("warning", "failed") +
    `</button>` +
    `</div>`;
  const attr = named ? ` class="language-${token}"` : "";
  const rendered = named ? highlight(source, token) : escapeHtml(source);
  return {
    html:
      `<div class="md-code"${named ? ` data-lang="${token}"` : ""}>${header}` +
      `<pre><code${attr}>${rendered}</code></pre></div>`,
    next,
  };
}

function renderList(lines: string[], start: number): { html: string; next: number } {
  const first = BLOCK_MARKERS.listItem.exec(lines[start]);
  // Only ever called when the line matched, but keep the type honest.
  if (!first) return { html: "", next: start + 1 };

  const baseIndent = first[1].length;
  const ordered = /\d/.test(first[2]);
  const items: string[][] = [];
  let i = start;

  while (i < lines.length) {
    const match = BLOCK_MARKERS.listItem.exec(lines[i]);
    if (!match || match[1].length !== baseIndent || /\d/.test(match[2]) !== ordered) break;

    const item: string[] = [match[4]];
    const contentIndent = baseIndent + match[2].length + match[3].length;
    const continuationIndent = Math.min(contentIndent, baseIndent + 2);
    i += 1;

    // A line belongs to this item while it is indented past the marker, or is
    // blank with more indented content after it. Nested lists arrive here as
    // indented content and are handled by the recursive renderBlocks call.
    while (i < lines.length) {
      const line = lines[i];
      if (line.trim() === "") {
        const next = nextNonBlank(lines, i + 1);
        if (next === null || leadingSpaces(next) < continuationIndent) break;
        item.push("");
        i += 1;
        continue;
      }
      if (leadingSpaces(line) < continuationIndent) break;
      item.push(line.slice(Math.min(leadingSpaces(line), contentIndent)));
      i += 1;
    }

    items.push(item);
  }

  const tag = ordered ? "ol" : "ul";
  const firstNumber = Number(first[2].replace(/\D/g, ""));
  const startAttr = ordered && Number.isFinite(firstNumber) && firstNumber !== 1 ? ` start="${firstNumber}"` : "";
  const body = items.map((item) => `<li>${unwrapSoleParagraph(renderBlocks(item))}</li>`).join("");
  return { html: `<${tag}${startAttr}>${body}</${tag}>`, next: i };
}

function nextNonBlank(lines: string[], from: number): string | null {
  for (let i = from; i < lines.length; i += 1) {
    if (lines[i].trim() !== "") return lines[i];
  }
  return null;
}

function leadingSpaces(line: string): number {
  return line.length - line.trimStart().length;
}

/**
 * Keep tight list items tight: an item whose only paragraph is its first block
 * loses the `<p>`, so `- outer` with a nested list reads as one line rather
 * than a paragraph followed by a list. A loose item — one that really does hold
 * several paragraphs — keeps them.
 */
function unwrapSoleParagraph(html: string): string {
  const match = /^<p>([\s\S]*?)<\/p>([\s\S]*)$/.exec(html);
  if (!match || match[2].includes("<p>")) return html;
  return `${match[1]}${match[2]}`;
}

const TABLE_DELIMITER = /^\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-*:?\s*\|?\s*$/;

function renderTable(lines: string[], start: number): { html: string; next: number } | null {
  const header = lines[start];
  const delimiter = lines[start + 1];
  if (header === undefined || delimiter === undefined) return null;
  if (!header.includes("|") || !TABLE_DELIMITER.test(delimiter)) return null;

  const headerCells = splitRow(header);
  const alignments = splitRow(delimiter).map(alignmentOf);
  if (headerCells.length < 2 || headerCells.length !== alignments.length) return null;

  const rows: string[][] = [];
  let i = start + 2;
  while (i < lines.length && lines[i].trim() !== "" && lines[i].includes("|")) {
    rows.push(splitRow(lines[i]));
    i += 1;
  }

  const head = headerCells
    .map((cell, index) => `<th${alignClass(alignments[index])}>${renderInline(cell)}</th>`)
    .join("");
  const body = rows
    .map((row) => {
      const cells = headerCells
        .map((_, index) => `<td${alignClass(alignments[index])}>${renderInline(row[index] ?? "")}</td>`)
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");

  return {
    html: `<div class="md-table"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`,
    next: i,
  };
}

function splitRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split(/(?<!\\)\|/).map((cell) => cell.replace(/\\\|/g, "|").trim());
}

type Alignment = "left" | "right" | "center" | null;

function alignmentOf(cell: string): Alignment {
  const text = cell.trim();
  const left = text.startsWith(":");
  const right = text.endsWith(":");
  if (left && right) return "center";
  if (right) return "right";
  if (left) return "left";
  return null;
}

/** The only `class` a table cell can carry — a fixed value, never source-derived. */
function alignClass(alignment: Alignment): string {
  return alignment === null ? "" : ` class="md-align-${alignment}"`;
}

// ── Inline ───────────────────────────────────────────────────────────────────
//
// Code spans and links are lifted into placeholders *before* the text is
// escaped, so emphasis rules can never run inside a URL or a code span, and the
// finished HTML for those spans is never escaped a second time. The placeholder
// is delimited by two private-use code points, which are stripped from the
// source first so nothing in a model response can forge one.

const PLACEHOLDER_OPEN = "\uE000";
const PLACEHOLDER_CLOSE = "\uE001";
const PLACEHOLDER_RE = /\uE000(\d+)\uE001/g;

export function renderInline(source: string): string {
  const tokens: string[] = [];
  const hold = (html: string): string => {
    tokens.push(html);
    return `${PLACEHOLDER_OPEN}${tokens.length - 1}${PLACEHOLDER_CLOSE}`;
  };

  let text = source.replace(/[\uE000\uE001]/g, "");

  // 1. Code spans win over every other inline rule.
  text = text.replace(/(`+)([^`]|[\s\S]*?[^`])\1(?!`)/g, (_whole, _ticks, code: string) =>
    hold(`<code>${escapeHtml(code.replace(/^ ([\s\S]*) $/, "$1"))}</code>`),
  );

  // 2. Images render as links — never an <img>, so nothing fetches remotely.
  text = text.replace(
    /!\[([^\]]*)\]\(\s*([^()\s]+)(?:\s+"[^"]*")?\s*\)/g,
    (whole, alt: string, url: string) =>
      hold(link(url, applyEmphasis(escapeHtml(alt === "" ? url : alt)), whole, "md-image-link")),
  );

  // 3. Explicit links.
  text = text.replace(
    /\[([^\]]*)\]\(\s*([^()\s]+)(?:\s+"[^"]*")?\s*\)/g,
    (whole, label: string, url: string) =>
      hold(link(url, applyEmphasis(escapeHtml(label === "" ? url : label)), whole)),
  );

  text = escapeHtml(text);

  // 4. Bare URLs, now that no markup-bearing region remains.
  text = text.replace(/(^|[\s(])((?:https?:\/\/|www\.)[^\s<]+)/g, (whole, prefix: string, raw: string) => {
    const trailing = /[.,;:!?)\]]+$/.exec(raw)?.[0] ?? "";
    const shown = raw.slice(0, raw.length - trailing.length);
    const href = shown.startsWith("www.") ? `https://${shown}` : shown;
    if (!SAFE_URL.test(unescapeForCheck(href))) return whole;
    return `${prefix}${hold(anchor(href, shown))}${trailing}`;
  });

  text = applyEmphasis(text);

  return text.replace(PLACEHOLDER_RE, (_whole, index: string) => tokens[Number(index)] ?? "");
}

function applyEmphasis(text: string): string {
  return text
    .replace(/~~(?=\S)([\s\S]*?\S)~~/g, "<del>$1</del>")
    .replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|\s)__(?=\S)([\s\S]*?\S)__(?=$|[\s.,;:!?)])/g, "$1<strong>$2</strong>")
    .replace(/\*(?=[^\s*])([^*]*?[^\s*]|[^\s*])\*/g, "<em>$1</em>")
    .replace(/(^|\s)_(?=\S)([^_]*?\S|\S)_(?=$|[\s.,;:!?)])/g, "$1<em>$2</em>");
}

/** Build an anchor, or fall back to the literal source text if the URL is unsafe. */
function link(url: string, label: string, fallback: string, className?: string): string {
  if (!SAFE_URL.test(url)) return escapeHtml(fallback);
  return anchor(escapeHtml(url), label, className);
}

/** `href` must already be HTML-escaped; `label` must already be safe HTML. */
function anchor(href: string, label: string, className?: string): string {
  const cls = className === undefined ? "" : ` class="${className}"`;
  return `<a href="${href}" rel="noopener noreferrer nofollow ugc" target="_blank"${cls}>${label}</a>`;
}

/** Undo escaping before a scheme check, so `&amp;` in a query does not fail it. */
function unescapeForCheck(text: string): string {
  return text.replace(/&amp;/g, "&").replace(/&#39;/g, "'").replace(/&quot;/g, '"');
}
