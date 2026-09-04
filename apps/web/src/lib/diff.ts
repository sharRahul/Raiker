/**
 * B14 — reading a unified diff, so a proposed change can be reviewed where it
 * was proposed instead of as one block of monospaced text in another route.
 *
 * This parses only what a unified diff states and invents nothing: a line that
 * does not fit the grammar is kept verbatim as context rather than dropped, so
 * a preview the server produced is never silently shortened. Line numbers come
 * from the hunk headers; when a diff carries none, they stay null and the
 * gutter is simply empty.
 */

export type DiffLineKind = "add" | "remove" | "context" | "hunk" | "meta";

export interface DiffLine {
  kind: DiffLineKind;
  text: string;
  oldLine: number | null;
  newLine: number | null;
  /**
   * B14 — which hunk of this file the line belongs to, 0-based, or null for the
   * file's own header lines. It is what lets a reviewer accept one hunk and not
   * another: the id the server validates is `<file index>:<hunk index>`, and
   * both are positions in this same parse.
   */
  hunkIndex: number | null;
}

export interface DiffFile {
  /** The file the hunks below change, or "" when the diff names none. */
  path: string;
  lines: DiffLine[];
  added: number;
  removed: number;
  /** How many hunks this file section holds. */
  hunks: number;
  /**
   * B14 — whether this section began at a `---`/`+++` pair, which is the only
   * shape the server's patch applier and its hunk selector both understand. A
   * section split off a bare `diff --git` renders, but its hunks have no id the
   * server would recognise, so it is never offered for per-hunk acceptance.
   */
  anchored: boolean;
}

export interface DiffStat {
  files: number;
  added: number;
  removed: number;
}

const HUNK = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/;
const GIT_HEADER = /^diff --git a\/(.+?) b\/(.+)$/;

function newFile(path: string, anchored: boolean): DiffFile {
  return { path, lines: [], added: 0, removed: 0, hunks: 0, anchored };
}

/**
 * B14 — the id of one hunk, as the server validates it.
 *
 * `raiker/tools/patch_selection.py` derives exactly the same string from the
 * same diff, which is what lets a browser send a selection without either side
 * having to send the other a list first. Both count file sections by their
 * `---`/`+++` pair — a `diff --git` line travels with the section it introduces
 * rather than starting one — so the two agree on a git-style diff and on a bare
 * unified one alike.
 */
export function hunkId(fileIndex: number, hunkIndex: number): string {
  return `${fileIndex}:${hunkIndex}`;
}

/** Every hunk in a parsed diff, in the order they appear. */
export function hunkIds(files: DiffFile[]): string[] {
  return files.flatMap((file, fileIndex) =>
    Array.from({ length: file.hunks }, (_unused, hunkIndex) => hunkId(fileIndex, hunkIndex)),
  );
}

/**
 * Whether a per-hunk decision can be offered on this diff at all.
 *
 * False for a diff whose sections are not anchored on `---`/`+++` pairs, and
 * for one with a single hunk — accepting the only hunk is what Accept already
 * does, so a checkbox there would be a control with no second state.
 */
export function diffSelectable(files: DiffFile[]): boolean {
  return files.every((file) => file.anchored) && hunkIds(files).length > 1;
}

/**
 * A diff with no `---`/`+++` pair anywhere, parsed so it can still be read.
 *
 * `diff --git` splits sections here, because it is the only boundary such a
 * diff has. The sections are marked unanchored, so no per-hunk decision is ever
 * offered on them: the server's applier requires the file headers this diff
 * does not carry, and a checkbox that produced an id the server would reject is
 * worse than no checkbox.
 */
function parseLoosely(rows: string[]): DiffFile[] {
  const files: DiffFile[] = [];
  let current: DiffFile = newFile("", false);
  let started = false;
  let oldLine = 0;
  let newLine = 0;
  let hunkIndex: number | null = null;

  function start(path: string): DiffFile {
    current = newFile(path, false);
    files.push(current);
    started = true;
    oldLine = 0;
    newLine = 0;
    hunkIndex = null;
    return current;
  }

  for (const raw of rows) {
    if (raw.startsWith("diff --git ")) {
      const match = GIT_HEADER.exec(raw);
      start(match?.[2] ?? "").lines.push({
        kind: "meta", text: raw, oldLine: null, newLine: null, hunkIndex: null,
      });
      continue;
    }
    const hunk = HUNK.exec(raw);
    if (hunk !== null) {
      if (!started) start("");
      oldLine = Number(hunk[1]);
      newLine = Number(hunk[2]);
      hunkIndex = current.hunks;
      current.hunks += 1;
      current.lines.push({ kind: "hunk", text: raw, oldLine: null, newLine: null, hunkIndex });
      continue;
    }
    if (!started) start("");
    if (raw.startsWith("+")) {
      current.lines.push({
        kind: "add", text: raw.slice(1), oldLine: null, newLine: newLine++, hunkIndex,
      });
      current.added += 1;
    } else if (raw.startsWith("-")) {
      current.lines.push({
        kind: "remove", text: raw.slice(1), oldLine: oldLine++, newLine: null, hunkIndex,
      });
      current.removed += 1;
    } else if (raw.startsWith("\\")) {
      current.lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null, hunkIndex });
    } else {
      const body = raw.startsWith(" ") ? raw.slice(1) : raw;
      current.lines.push({
        kind: "context", text: body, oldLine: oldLine++, newLine: newLine++, hunkIndex,
      });
    }
  }
  for (const file of files) {
    const last = file.lines.at(-1);
    if (last !== undefined && last.kind === "context" && last.text === "") file.lines.pop();
  }
  return files.filter((file) => file.lines.length > 0);
}

/**
 * Split a unified diff into per-file line lists. Never throws.
 *
 * A file section begins at its `---`/`+++` pair, not at `diff --git`. That is
 * the rule the server's `patch_selection._sections` uses, and the two have to
 * agree exactly or a hunk id would name a different hunk on each side. A
 * `diff --git` line, an `index` line, or anything else before the pair is
 * buffered and emitted as that section's own header — so it still renders, and
 * still cannot start a section of its own.
 */
export function parseUnifiedDiff(text: string): DiffFile[] {
  if (text.trim() === "") return [];
  const normalized = text.replace(/\r\n/g, "\n");
  const rows = normalized.split("\n");
  // Strict mode is the shape the server understands: every section anchored on
  // a `---`/`+++` pair. Anything else is a diff the applier would refuse anyway,
  // and is parsed only so it can be *read*.
  const anchored = rows.some(
    (row, index) => row.startsWith("--- ") && (rows[index + 1] ?? "").startsWith("+++ "),
  );
  if (!anchored) return parseLoosely(rows);
  const files: DiffFile[] = [];
  let current: DiffFile = newFile("", true);
  let started = false;
  let oldLine = 0;
  let newLine = 0;
  let hunkIndex: number | null = null;
  // Lines seen before a section's `---`/`+++` pair, waiting for it.
  let preamble: string[] = [];

  function start(path: string): DiffFile {
    current = newFile(path, true);
    files.push(current);
    started = true;
    oldLine = 0;
    newLine = 0;
    hunkIndex = null;
    for (const line of preamble) {
      current.lines.push({ kind: "meta", text: line, oldLine: null, newLine: null, hunkIndex: null });
    }
    preamble = [];
    return current;
  }

  for (const raw of rows) {
    if (raw.startsWith("--- ")) {
      // Every section starts here, including the second and later ones: seeing a
      // `---` while inside a section means the previous section ended.
      const path = raw.slice(4).replace(/^a\//, "").trim();
      start(path === "/dev/null" ? "" : path);
      current.lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null, hunkIndex: null });
      continue;
    }
    if (raw.startsWith("+++ ")) {
      const path = raw.slice(4).replace(/^b\//, "").trim();
      // `+++ /dev/null` is a deletion: the file being changed is the `---` side,
      // which the current section already names.
      if (!started) start(path === "/dev/null" ? "" : path);
      else if (path !== "/dev/null") current.path = path;
      current.lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null, hunkIndex: null });
      continue;
    }
    const hunk = HUNK.exec(raw);
    if (hunk !== null) {
      if (!started) start("");
      oldLine = Number(hunk[1]);
      newLine = Number(hunk[2]);
      hunkIndex = current.hunks;
      current.hunks += 1;
      current.lines.push({ kind: "hunk", text: raw, oldLine: null, newLine: null, hunkIndex });
      continue;
    }
    if (!started) {
      // Before any `---`: a git header, an index line, a mode change. Held for
      // the section it introduces rather than starting one.
      const match = GIT_HEADER.exec(raw);
      if (match !== null || raw.trim() !== "") preamble.push(raw);
      continue;
    }
    if (raw.startsWith("+")) {
      current.lines.push({
        kind: "add", text: raw.slice(1), oldLine: null, newLine: newLine++, hunkIndex,
      });
      current.added += 1;
    } else if (raw.startsWith("-")) {
      current.lines.push({
        kind: "remove", text: raw.slice(1), oldLine: oldLine++, newLine: null, hunkIndex,
      });
      current.removed += 1;
    } else if (raw.startsWith("\\")) {
      // "\ No newline at end of file" — a note about the diff, not a change.
      current.lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null, hunkIndex });
    } else {
      const body = raw.startsWith(" ") ? raw.slice(1) : raw;
      current.lines.push({
        kind: "context", text: body, oldLine: oldLine++, newLine: newLine++, hunkIndex,
      });
    }
  }

  // A diff that never reached a `---`/`+++` pair still has to render: its lines
  // are held in the preamble, so they become one unnamed section rather than
  // disappearing.
  if (!started && preamble.length > 0) {
    const held = preamble;
    preamble = [];
    start("");
    for (const line of held) {
      current.lines.push({ kind: "context", text: line, oldLine: null, newLine: null, hunkIndex: null });
    }
  }

  // A trailing newline produces one empty context line that means nothing.
  for (const file of files) {
    const last = file.lines.at(-1);
    if (last !== undefined && last.kind === "context" && last.text === "") file.lines.pop();
  }
  return files.filter((file) => file.lines.length > 0);
}

export function diffStat(files: DiffFile[]): DiffStat {
  return files.reduce<DiffStat>(
    (total, file) => ({
      files: total.files + 1,
      added: total.added + file.added,
      removed: total.removed + file.removed,
    }),
    { files: 0, added: 0, removed: 0 },
  );
}

/** "3 files · +42 −7", or "No change" for an empty diff. */
export function diffSummary(stat: DiffStat): string {
  if (stat.files === 0) return "No change";
  const files = `${stat.files} file${stat.files === 1 ? "" : "s"}`;
  return `${files} · +${stat.added} −${stat.removed}`;
}
