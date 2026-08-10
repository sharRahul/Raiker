# Security review — &lt;component or change under review&gt;

**Scope.** &lt;revision range, branch, or paths&gt;
**Security model read.** &lt;the project's own threat model / security docs, and
the existing defences found in phase one&gt;
**Classes swept.** &lt;the sections of `references/vulnerability-classes.md`
this review actually walked&gt;
**Result.** &lt;n&gt; findings at or above confidence 0.8.

---

## Findings

### 1. &lt;defect in one line&gt;

| | |
|---|---|
| **File** | `path/to/file.py:120` |
| **Severity** | high |
| **Category** | `sql-injection` |
| **Confidence** | 0.95 |

**Description.** &lt;one or two sentences: what is wrong&gt;

**Exploit scenario.** &lt;the concrete walk — what an attacker controls, what
they send, which transformations it survives, what happens. Name the source, not
"user input".&gt;

**Recommendation.** &lt;the specific fix, in this codebase's own idiom — the
helper it should use, the guard its neighbours already have&gt;

---

### 2. &lt;defect in one line&gt;

&lt;same fields&gt;

---

## Verified and clear

Only where a reader would otherwise assume it was not looked at:

- &lt;area&gt; — &lt;the guard that is present, and where&gt;

## Deliberately not reported

- &lt;observation&gt; — &lt;excluded class / below confidence floor / no reachable
  source&gt;

---

When nothing clears the floor, the document is two lines: the classes swept, and
**no findings at or above the reporting threshold**. That is a real result. Do
not pad it with defence-in-depth observations to look thorough — a review that
does this once is skimmed for ever after.
