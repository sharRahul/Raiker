# Calibrating a finding

Read this when a review is producing more findings than a reader will act on,
or when you cannot decide whether something clears the reporting threshold.

- [The one test that settles it](#the-one-test-that-settles-it)
- [Worked examples by band](#worked-examples-by-band)
- [The exclusions, applied to real cases](#the-exclusions-applied-to-real-cases)
- [Wording that survives contact with a reader](#wording-that-survives-contact-with-a-reader)

## The one test that settles it

Write the failure scenario first:

> Given **&lt;concrete inputs or state&gt;**, this code **&lt;does the wrong
> thing&gt;**.

If both halves are concrete, the finding is real and you now know its score. If
either half needs "might", "could", or "in some cases", you have an impression.
Verify it until it is concrete or drop it — the middle option, reporting it
softly, is the one that ruins a review.

## Worked examples by band

### 95 — traced, and the path runs

```python
for index in range(len(rows) + 1):
    total += rows[index]["amount"]
```

*Given a non-empty `rows`, the final iteration indexes one past the end and
raises `IndexError`.* Both halves concrete, no unread code could rescue it.
Report.

### 85 — clear from what is in front of you

```python
connection = sqlite3.connect(path)
connection.execute(statement)
return connection.fetchall()
```

*Given any call, the connection is never closed, so a long-lived process leaks
handles until it hits its descriptor limit.* You have not measured the limit,
but nothing outside the hunk can close a connection this function never returns
in a closeable form. Report.

### 70 — suspicious, and resting on something unread

```python
if user.role in ADMIN_ROLES:
    return grant(user)
```

*If `ADMIN_ROLES` were populated from request data, this would be privilege
escalation.* You have not read where `ADMIN_ROLES` comes from. Two outcomes are
allowed: read it, and land at 95 or at nothing. Reporting it at 70 hands the
reader your homework.

### 45 — a feeling

> "This function is doing a lot; it might be worth splitting."

No failure scenario exists, because nothing fails. Drop it. If the complexity is
genuinely a defect, it will show up as a *concrete* one: a branch that cannot be
reached, a parameter no caller passes, a duplicated helper.

## The exclusions, applied to real cases

| Case | Verdict |
|---|---|
| The diff moves a function; the function has a pre-existing null check missing | **Not reported.** The move did not introduce it. Reviewing a diff means reviewing the change. |
| The diff moves a function *and* drops the null check while moving it | **Reported.** The change introduced it. |
| Line exceeds the project's line length | **Not reported.** The formatter says it more cheaply. |
| `# noqa: BLE001 — reported through the assert below` on a broad except | **Not reported.** Justified, and the justification holds. |
| `# type: ignore` on a line whose types genuinely do not line up at runtime | **Reported.** The comment's own claim is what is wrong. |
| "This map lookup will be slow with a million entries" on a config table of 20 | **Not reported.** No named limit, no path to it. |
| "This O(n²) join runs on the request path over a table that already holds 400k rows" | **Reported.** Named limit, named path. |
| A new public function with no test | **Reported** under coverage, once, naming the untested branch — not once per branch. |

## Wording that survives contact with a reader

| Instead of | Write |
|---|---|
| "Should we maybe handle the empty case?" | "`parse()` raises on an empty list; `load_config()` passes one when the file is absent." |
| "Consider using the existing helper." | "`normalise_path()` in `paths.py:44` already does this, including the Windows case this copy misses." |
| "This looks wrong." | State what is wrong, or do not report it. |
| "Nit: naming." | Nothing. Do not report it. |

State the defect; do not ask about it. A question transfers the work of deciding
back to the author, which is the thing they asked you for.

Rank by severity, not by file order. The reader stops somewhere; make sure what
they read first is the thing that would have shipped broken.
