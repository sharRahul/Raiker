/**
 * A locally-shipped, allowlisted syntax highlighter for rendered code blocks
 * (BUG-23).
 *
 * Raiker's built UI makes no external requests, and that has to stay true with
 * highlighting on — so there is no CDN grammar, no lazy-loaded language pack,
 * and no `eval`-based tokeniser. What exists instead is a small regular-grammar
 * scanner over a fixed language allowlist, shipped in the bundle.
 *
 * The security posture of `markdown.ts` is preserved exactly, and by the same
 * structural argument rather than by filtering:
 *
 * 1. **Escape at emit time, always.** Every token's text goes through
 *    `escapeHtml` in `highlight()` before it is wrapped. The scanner works on
 *    raw source and produces `(kind, start, end)` spans only — it never builds
 *    HTML, so there is no path by which source text reaches the DOM unescaped.
 * 2. **A closed tag set with fixed classes.** The only tag emitted is `<span>`,
 *    and its only attribute is a `class` drawn from {@link TOKEN_KINDS}. No
 *    class, tag, or attribute is ever derived from the source.
 * 3. **Unknown languages are not guessed.** A fence tagged with a language this
 *    module does not ship renders as plain escaped text with its label intact.
 *    Mis-highlighting reads as a lie about what the code is; plain text does
 *    not.
 *
 * Highlighting is deliberately coarse. It is here so a daily-use reader can see
 * structure at a glance — strings, comments, keywords, numbers — not to
 * reimplement a language server in a chat bubble.
 */

import { escapeHtml } from "./markdown";

/** Every class this module can emit. Fixed, never source-derived. */
export const TOKEN_KINDS = ["comment", "string", "keyword", "number", "type", "punct"] as const;

export type TokenKind = (typeof TOKEN_KINDS)[number];

interface Rule {
  kind: TokenKind;
  pattern: RegExp;
}

interface Grammar {
  /** Display label shown on the block header. */
  label: string;
  rules: Rule[];
}

/** Build a keyword rule: whole words only, so `information` is not `in`. */
function keywords(words: string[]): Rule {
  return { kind: "keyword", pattern: new RegExp(`\\b(?:${words.join("|")})\\b`, "g") };
}

const NUMBER: Rule = {
  kind: "number",
  pattern: /\b(?:0[xXbBoO][0-9a-fA-F_]+|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?)\b/g,
};

// Strings: single, double, and backtick, each stopping at an unescaped closer or
// the end of the line. Bounded on purpose — an unterminated quote in streaming
// output must not swallow the rest of the block.
const QUOTED: Rule = {
  kind: "string",
  pattern: /"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`/g,
};

const SLASH_COMMENT: Rule = { kind: "comment", pattern: /\/\/[^\n]*|\/\*[\s\S]*?\*\//g };
const HASH_COMMENT: Rule = { kind: "comment", pattern: /#[^\n]*/g };
const PUNCT: Rule = { kind: "punct", pattern: /[{}[\]()<>;,.:=+\-*/%!&|^~?]/g };

const JS_KEYWORDS = [
  "as", "async", "await", "break", "case", "catch", "class", "const", "continue", "debugger",
  "default", "delete", "do", "else", "enum", "export", "extends", "false", "finally", "for",
  "from", "function", "if", "implements", "import", "in", "instanceof", "interface", "let",
  "new", "null", "of", "private", "protected", "public", "readonly", "return", "satisfies",
  "static", "super", "switch", "this", "throw", "true", "try", "type", "typeof", "undefined",
  "var", "void", "while", "yield",
];

const PY_KEYWORDS = [
  "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del", "elif",
  "else", "except", "False", "finally", "for", "from", "global", "if", "import", "in", "is",
  "lambda", "None", "nonlocal", "not", "or", "pass", "raise", "return", "True", "try", "while",
  "with", "yield",
];

const SHELL_KEYWORDS = [
  "case", "do", "done", "elif", "else", "esac", "export", "fi", "for", "function", "if", "in",
  "local", "readonly", "return", "then", "until", "while",
];

const SQL_KEYWORDS = [
  "ALTER", "AND", "AS", "ASC", "BY", "CREATE", "DELETE", "DESC", "DISTINCT", "DROP", "FROM",
  "GROUP", "HAVING", "INNER", "INSERT", "INTO", "JOIN", "LEFT", "LIMIT", "NOT", "NULL", "ON",
  "OR", "ORDER", "OUTER", "SELECT", "SET", "TABLE", "UNION", "UPDATE", "VALUES", "WHERE",
];

const TYPE_RULE: Rule = { kind: "type", pattern: /\b[A-Z][A-Za-z0-9_]*\b/g };

const JS: Grammar = {
  label: "JavaScript",
  rules: [SLASH_COMMENT, QUOTED, keywords(JS_KEYWORDS), NUMBER, TYPE_RULE, PUNCT],
};
const TS: Grammar = { ...JS, label: "TypeScript" };
const PYTHON: Grammar = {
  label: "Python",
  rules: [
    { kind: "string", pattern: /"""[\s\S]*?"""|'''[\s\S]*?'''/g },
    HASH_COMMENT,
    QUOTED,
    keywords(PY_KEYWORDS),
    NUMBER,
    TYPE_RULE,
    PUNCT,
  ],
};
const SHELL: Grammar = {
  label: "Shell",
  rules: [HASH_COMMENT, QUOTED, keywords(SHELL_KEYWORDS), NUMBER, PUNCT],
};
const JSON_GRAMMAR: Grammar = {
  label: "JSON",
  rules: [
    { kind: "string", pattern: /"(?:[^"\\\n]|\\.)*"/g },
    keywords(["true", "false", "null"]),
    NUMBER,
    PUNCT,
  ],
};
const CSS: Grammar = {
  label: "CSS",
  rules: [
    { kind: "comment", pattern: /\/\*[\s\S]*?\*\//g },
    QUOTED,
    { kind: "keyword", pattern: /@[a-z-]+|:[a-z-]+(?=[\s{:,)])/g },
    NUMBER,
    PUNCT,
  ],
};
const HTML_GRAMMAR: Grammar = {
  label: "HTML",
  rules: [
    { kind: "comment", pattern: /<!--[\s\S]*?-->/g },
    QUOTED,
    { kind: "keyword", pattern: /<\/?[A-Za-z][A-Za-z0-9-]*|\/?>/g },
    { kind: "type", pattern: /\b[a-zA-Z-]+(?==)/g },
  ],
};
const YAML: Grammar = {
  label: "YAML",
  rules: [
    HASH_COMMENT,
    QUOTED,
    { kind: "type", pattern: /^\s*[-\w.]+(?=:)/gm },
    keywords(["true", "false", "null", "yes", "no"]),
    NUMBER,
  ],
};
const SQL: Grammar = {
  label: "SQL",
  rules: [
    { kind: "comment", pattern: /--[^\n]*|\/\*[\s\S]*?\*\//g },
    QUOTED,
    { kind: "keyword", pattern: new RegExp(`\\b(?:${SQL_KEYWORDS.join("|")})\\b`, "gi") },
    NUMBER,
    PUNCT,
  ],
};
const DIFF: Grammar = {
  label: "Diff",
  rules: [
    { kind: "comment", pattern: /^@@[^\n]*$/gm },
    { kind: "string", pattern: /^\+[^\n]*$/gm },
    { kind: "keyword", pattern: /^-[^\n]*$/gm },
  ],
};

/**
 * The allowlist. A fence tagged with anything not in here renders as plain
 * escaped text — the label is still shown, so the reader knows what the model
 * claimed it was writing.
 */
const GRAMMARS: Record<string, Grammar> = {
  bash: SHELL, sh: SHELL, shell: SHELL, zsh: SHELL, console: SHELL,
  js: JS, jsx: JS, javascript: JS, mjs: JS, cjs: JS,
  ts: TS, tsx: TS, typescript: TS,
  svelte: HTML_GRAMMAR, html: HTML_GRAMMAR, xml: HTML_GRAMMAR,
  py: PYTHON, python: PYTHON,
  json: JSON_GRAMMAR, jsonc: JSON_GRAMMAR,
  css: CSS, scss: CSS,
  yaml: YAML, yml: YAML,
  sql: SQL,
  diff: DIFF, patch: DIFF,
};

/** Human-readable names for languages we label but do not tokenise. */
const LABELS_ONLY: Record<string, string> = {
  md: "Markdown", markdown: "Markdown", text: "Text", txt: "Text", plaintext: "Text",
  go: "Go", rust: "Rust", rs: "Rust", java: "Java", c: "C", cpp: "C++", "c++": "C++",
  cs: "C#", rb: "Ruby", ruby: "Ruby", php: "PHP", swift: "Swift", kotlin: "Kotlin",
  toml: "TOML", ini: "INI", make: "Make", makefile: "Makefile", dockerfile: "Dockerfile",
};

/** Is this language token one the highlighter actually tokenises? */
export function isHighlightable(language: string): boolean {
  return Object.hasOwn(GRAMMARS, language.toLowerCase());
}

/**
 * The label to show on a code block's header.
 *
 * A known language gets its conventional name (`ts` → TypeScript). An unknown
 * one is echoed back uppercased rather than dropped: the model said something
 * about this block, and hiding that is worse than showing an unfamiliar word.
 */
export function languageLabel(language: string): string {
  const key = language.toLowerCase();
  return GRAMMARS[key]?.label ?? LABELS_ONLY[key] ?? language.toUpperCase();
}

interface Span {
  start: number;
  end: number;
  kind: TokenKind;
}

/**
 * Highlight `source` as `language`, returning escaped HTML.
 *
 * Falls back to plain escaped text for any language outside the allowlist, and
 * for input long enough that scanning would be felt (a 200 KB paste is not a
 * code block anyone is reading).
 */
export function highlight(source: string, language: string): string {
  const grammar = GRAMMARS[language.toLowerCase()];
  if (grammar === undefined || source.length > 100_000) return escapeHtml(source);

  // Earlier rules win: a keyword inside a string is part of the string, and a
  // string inside a comment is part of the comment. Overlaps are resolved by
  // claim order rather than by nesting, which is why comment and string rules
  // are listed first in every grammar.
  const claimed: Span[] = [];
  const overlaps = (start: number, end: number): boolean =>
    claimed.some((span) => start < span.end && end > span.start);

  for (const rule of grammar.rules) {
    const pattern = new RegExp(rule.pattern.source, rule.pattern.flags);
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(source)) !== null) {
      if (match[0] === "") {
        pattern.lastIndex += 1;
        continue;
      }
      const start = match.index;
      const end = start + match[0].length;
      if (!overlaps(start, end)) claimed.push({ start, end, kind: rule.kind });
    }
  }

  claimed.sort((a, b) => a.start - b.start);

  let out = "";
  let cursor = 0;
  for (const span of claimed) {
    if (span.start < cursor) continue;
    out += escapeHtml(source.slice(cursor, span.start));
    out += `<span class="tok-${span.kind}">${escapeHtml(source.slice(span.start, span.end))}</span>`;
    cursor = span.end;
  }
  out += escapeHtml(source.slice(cursor));
  return out;
}
