// B14 — the diff reader has one job: say exactly what the diff says. These
// guard the two ways that goes wrong — a line dropped because it did not fit
// the grammar, and a count that disagrees with what is on screen.
import { describe, expect, it } from "vitest";
import { diffSelectable, diffStat, diffSummary, hunkIds, parseUnifiedDiff } from "./diff";

const SIMPLE = `diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -10,3 +10,4 @@ def main():
     setup()
-    run()
+    run(timeout=30)
+    report()
`;

describe("parseUnifiedDiff", () => {
  it("names the file and counts what changed", () => {
    const [file] = parseUnifiedDiff(SIMPLE);
    expect(file.path).toBe("src/app.py");
    expect(file.added).toBe(2);
    expect(file.removed).toBe(1);
  });

  it("numbers lines from the hunk header", () => {
    const [file] = parseUnifiedDiff(SIMPLE);
    const context = file.lines.find((line) => line.kind === "context");
    expect(context?.oldLine).toBe(10);
    expect(context?.newLine).toBe(10);
    const added = file.lines.filter((line) => line.kind === "add");
    expect(added.map((line) => line.newLine)).toEqual([11, 12]);
  });

  it("keeps the text of every line, sign stripped", () => {
    const [file] = parseUnifiedDiff(SIMPLE);
    expect(file.lines.find((line) => line.kind === "add")?.text).toBe("    run(timeout=30)");
    expect(file.lines.find((line) => line.kind === "remove")?.text).toBe("    run()");
  });

  it("splits a multi-file diff", () => {
    const files = parseUnifiedDiff(`diff --git a/one.txt b/one.txt
@@ -1 +1 @@
-a
+b
diff --git a/two.txt b/two.txt
@@ -1 +1 @@
-c
+d
`);
    expect(files.map((file) => file.path)).toEqual(["one.txt", "two.txt"]);
    expect(diffStat(files)).toEqual({ files: 2, added: 2, removed: 2 });
  });

  it("reads a bare hunk with no file header", () => {
    const [file] = parseUnifiedDiff("@@ -1,2 +1,2 @@\n-old\n+new\n");
    expect(file.path).toBe("");
    expect(file.added).toBe(1);
  });

  it("keeps a no-newline marker as a note rather than a change", () => {
    const [file] = parseUnifiedDiff(
      ["@@ -1 +1 @@", "-a", "+b", String.raw`\ No newline at end of file`, ""].join("\n"),
    );
    expect(file.added).toBe(1);
    expect(file.removed).toBe(1);
    expect(file.lines.at(-1)?.kind).toBe("meta");
  });

  it("returns nothing for an empty diff rather than an empty file", () => {
    expect(parseUnifiedDiff("")).toEqual([]);
    expect(parseUnifiedDiff("   \n")).toEqual([]);
  });
});

describe("diffSummary", () => {
  it("states the size of the change", () => {
    expect(diffSummary(diffStat(parseUnifiedDiff(SIMPLE)))).toBe("1 file · +2 −1");
  });

  it("says nothing changed when nothing did", () => {
    expect(diffSummary(diffStat([]))).toBe("No change");
  });
});

// B14 — the browser and the server have to derive the same id from the same
// diff, or a checkbox would accept a different hunk from the one it names.
//
// These are the exact vectors `raiker/tools/patch_selection.py` produces, taken
// from it rather than written from the same assumption twice. A change to
// either parser that breaks the agreement fails here.
describe("hunk ids agree with the server", () => {
  it.each([
    [
      "two files",
      "--- a/poem.txt\n+++ b/poem.txt\n@@ -1,2 +1,2 @@\n-roses\n+red\n c\n@@ -5,2 +5,2 @@\n-sugar\n+sweet\n d\n--- a/note.txt\n+++ b/note.txt\n@@ -1 +1 @@\n-draft\n+final\n",
      ["0:0", "0:1", "1:0"],
    ],
    [
      "a git-style diff whose `diff --git` lines travel with their section",
      "diff --git a/one.txt b/one.txt\nindex 111..222 100644\n--- a/one.txt\n+++ b/one.txt\n@@ -1 +1 @@\n-a\n+b\ndiff --git a/two.txt b/two.txt\n--- a/two.txt\n+++ b/two.txt\n@@ -1 +1 @@\n-c\n+d\n",
      ["0:0", "1:0"],
    ],
    ["a file creation", "--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1 @@\n+hello\n", ["0:0"]],
  ])("matches the server for %s", (_name, patch, expected) => {
    expect(hunkIds(parseUnifiedDiff(patch))).toEqual(expected);
  });

  it("keeps a git preamble in the section it introduces, not in one of its own", () => {
    const files = parseUnifiedDiff(
      "diff --git a/one.txt b/one.txt\nindex 111..222 100644\n--- a/one.txt\n+++ b/one.txt\n@@ -1 +1 @@\n-a\n+b\n",
    );
    expect(files).toHaveLength(1);
    expect(files[0].path).toBe("one.txt");
    expect(files[0].lines.some((line) => line.text.startsWith("diff --git"))).toBe(true);
  });

  it("offers no per-hunk decision on a diff the server could not apply", () => {
    // No `---`/`+++` pair: readable, but its hunks have no id the server would
    // recognise, so a checkbox on one would produce a decision it must refuse.
    const files = parseUnifiedDiff(
      "diff --git a/one.txt b/one.txt\n@@ -1 +1 @@\n-a\n+b\ndiff --git a/two.txt b/two.txt\n@@ -1 +1 @@\n-c\n+d\n",
    );
    expect(files.every((file) => file.anchored)).toBe(false);
    expect(diffSelectable(files)).toBe(false);
  });

  it("offers no per-hunk decision when there is only one hunk", () => {
    // Accepting the only hunk is what Accept already does.
    expect(diffSelectable(parseUnifiedDiff("--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"))).toBe(
      false,
    );
  });

  it("tells every line which hunk it belongs to", () => {
    const [file] = parseUnifiedDiff(
      "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n@@ -5 +5 @@\n-c\n+d\n",
    );
    expect(file.lines.filter((line) => line.kind === "add").map((line) => line.hunkIndex)).toEqual([
      0, 1,
    ]);
    expect(file.lines.find((line) => line.kind === "meta")?.hunkIndex).toBeNull();
  });
});
