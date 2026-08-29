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
}

export interface DiffFile {
  /** The file the hunks below change, or "" when the diff names none. */
  path: string;
  lines: DiffLine[];
  added: number;
  removed: number;
}

export interface DiffStat {
  files: number;
  added: number;
  removed: number;
}

const HUNK = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/;
const GIT_HEADER = /^diff --git a\/(.+?) b\/(.+)$/;

function newFile(path: string): DiffFile {
  return { path, lines: [], added: 0, removed: 0 };
}

/** Split a unified diff into per-file line lists. Never throws. */
export function parseUnifiedDiff(text: string): DiffFile[] {
  if (text.trim() === "") return [];
  const files: DiffFile[] = [];
  let current: DiffFile = newFile("");
  let started = false;
  let oldLine = 0;
  let newLine = 0;

  function start(path: string): DiffFile {
    current = newFile(path);
    files.push(current);
    started = true;
    oldLine = 0;
    newLine = 0;
    return current;
  }

  for (const raw of text.replace(/\r\n/g, "\n").split("\n")) {
    if (raw.startsWith("diff --git ")) {
      const match = GIT_HEADER.exec(raw);
      start(match?.[2] ?? "").lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null });
      continue;
    }
    if (raw.startsWith("+++ ")) {
      const path = raw.slice(4).replace(/^b\//, "").trim();
      // `+++ /dev/null` is a deletion: the file being changed is the `---` side,
      // which the current file already names.
      if (!started) start(path === "/dev/null" ? "" : path);
      else if (current.path === "" && path !== "/dev/null") current.path = path;
      current.lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null });
      continue;
    }
    if (raw.startsWith("--- ")) {
      if (!started) start(raw.slice(4).replace(/^a\//, "").trim());
      current.lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null });
      continue;
    }
    const hunk = HUNK.exec(raw);
    if (hunk !== null) {
      if (!started) start("");
      oldLine = Number(hunk[1]);
      newLine = Number(hunk[2]);
      current.lines.push({ kind: "hunk", text: raw, oldLine: null, newLine: null });
      continue;
    }
    if (!started) start("");
    if (raw.startsWith("+")) {
      current.lines.push({ kind: "add", text: raw.slice(1), oldLine: null, newLine: newLine++ });
      current.added += 1;
    } else if (raw.startsWith("-")) {
      current.lines.push({ kind: "remove", text: raw.slice(1), oldLine: oldLine++, newLine: null });
      current.removed += 1;
    } else if (raw.startsWith("\\")) {
      // "\ No newline at end of file" — a note about the diff, not a change.
      current.lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null });
    } else {
      const body = raw.startsWith(" ") ? raw.slice(1) : raw;
      current.lines.push({ kind: "context", text: body, oldLine: oldLine++, newLine: newLine++ });
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
