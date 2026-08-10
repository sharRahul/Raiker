# Review — &lt;change under review&gt;

**Scope.** &lt;branch, PR number, or revision range&gt; · &lt;n&gt; files ·
&lt;n&gt; hunks
**House rules read.** &lt;CLAUDE.md paths, style guides — or "none found"&gt;
**Result.** &lt;n&gt; findings at or above the reporting threshold.

---

## Findings

### 1. &lt;one-sentence defect&gt;

**Where.** `path/to/file.py:120`
**Confidence.** 90
**Failure scenario.** Given &lt;concrete inputs or state&gt;, &lt;what goes
wrong&gt;.
**Fix.** &lt;what to do — omit when it follows from the defect&gt;

### 2. &lt;one-sentence defect&gt;

**Where.** `path/to/other.ts:44`
**Confidence.** 85
**Failure scenario.** …
**Fix.** …

---

## Checked and clear

One line each, only where a reader would otherwise wonder whether it was looked
at — the migration, the concurrency, the error path. Not a list of everything.

- &lt;area&gt; — &lt;what was verified, and how&gt;

## Not reported

Only when something was deliberately left out and the reader might expect it:

- &lt;observation&gt; — &lt;pre-existing / linter-covered / below threshold&gt;

---

When there is nothing to report, the whole document is one line: **No findings
above the reporting threshold.** Followed, if it helps, by the *Checked and
clear* list. Padding an empty result is how a review stops being read.
