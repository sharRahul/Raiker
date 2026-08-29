// B14 — the diff reader has one job: say exactly what the diff says. These
// guard the two ways that goes wrong — a line dropped because it did not fit
// the grammar, and a count that disagrees with what is on screen.
import { describe, expect, it } from "vitest";
import { diffStat, diffSummary, parseUnifiedDiff } from "./diff";

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
