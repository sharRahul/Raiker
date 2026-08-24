---
name: code-review
description: Review a diff, a branch, a pull request, or a working tree for defects that will actually bite — correctness bugs, missed reuse, needless complexity, and gaps in test coverage — and report only findings worth someone's time. Use whenever someone says "review this", "review my PR", "look over this change", "what did I miss", "is this ready to merge", "sanity-check this diff", or asks for a second pass before shipping. Use it too when a review is expected to leave comments on a pull request, when a change touches code with a house style to honour (CLAUDE.md, CONTRIBUTING.md, a style guide), or when someone asks why a review keeps producing noise. Do not use it for security auditing — the security-review skill is aimed at that and applies different thresholds.
metadata:
  version: 1.0.0
---

# Code review

A review is judged by what a reader does with it. Ten confident, correct
findings are worth more than forty that must each be triaged, and one wrong
finding costs more trust than five right ones earn. Everything below exists to
raise the *precision* of what you report, not the count.

The failure mode to design against is not missing a bug. It is the review that
buries the one real bug under thirty observations about naming.

## 1. Decide whether to review at all

Skip, and say so in one line, when:

- the change is closed, merged, or explicitly marked draft/WIP by its author;
- it is a pure revert, a version bump, a lockfile refresh, or generated output;
- you already reviewed this exact revision — re-reporting the same findings on
  a rebase is noise, not diligence.

Reviewing something trivial is not a neutral act: it teaches the reader that
your reviews can be skimmed.

## 2. Establish the ground truth before reading the diff

In order, because each step changes how you read the next:

1. **What is the change trying to do?** From the PR body, the commit messages,
   the issue it names. A diff read without its intent produces findings that
   argue with the goal rather than with the code.
2. **What rules does this repository already have?** Read every `CLAUDE.md`,
   `AGENTS.md`, `CONTRIBUTING.md` and style guide that applies to the changed
   paths, root-most first, most specific last. A house rule you did not read is
   a finding you will invent.
3. **What did the surrounding code already do?** Read the file around each
   hunk, not the hunk alone. Most real defects are contradictions between new
   code and code that did not change.
4. **What is the history?** For a hunk that looks odd, check whether it is
   re-introducing something a previous commit deliberately removed. A comment
   or commit message often names the reason.

## 3. Read for the four things that matter

Cover each pass separately; mixing them is how the correctness pass gets
crowded out by style observations.

| Pass | Looking for | Typical find |
|---|---|---|
| **Correctness** | Inputs and states the code does not handle | Off-by-one, unhandled `None`/`null`/error, wrong operator, races, an `await` that is missing, a resource never closed |
| **Contract** | Behaviour changing where callers cannot see it | Signature or return-shape change with a caller left behind, a widened permission, a silently swallowed error |
| **Reuse and simplification** | Work the codebase already does | A hand-rolled helper that duplicates an existing one, a branch that cannot be taken, three layers of indirection over one call |
| **Coverage** | Claims nothing tests | A new branch with no test, a test asserting the mock rather than the behaviour, a fixed bug with no regression test |

For every candidate finding, write the **failure scenario** before writing the
finding: concrete inputs or state → the wrong output, exception, or corrupted
state. A finding whose failure scenario you cannot write is an impression, and
impressions belong in a conversation, not a review.

## 4. Score confidence, then cut

Score each finding 0–100 on *how sure you are that this is really wrong*, not on
how bad it would be if it were:

| Score | Meaning |
|---|---|
| 90–100 | You traced the path. The failure scenario runs. |
| 80–89 | The defect is clear from the code in front of you; nothing you have not read could plausibly make it correct. |
| 60–79 | Suspicious, and dependent on something you did not verify. |
| < 60 | A feeling. |

**Report at 80 and above. Discard the rest** — do not soften them into
"consider" comments, which are the same noise wearing a hedge. If a sub-80
finding matters to you, verify it until it is above 80 or drop it.

Running several independent passes (correctness, house rules, history, coverage)
and scoring each finding on its own is what makes the threshold meaningful: a
finding that two passes reach independently is usually the real one.

## 5. Never report these

They are true observations that waste the reader's turn:

- **Pre-existing issues** the diff did not introduce or touch. Unless the change
  makes one materially worse, it is a different piece of work.
- **Anything a linter, formatter or type-checker already catches.** If the
  repository runs one, it will say so more cheaply than you.
- **Style preferences the repository has not stated.** Your taste is not a
  finding.
- **Code with an explicit ignore/justification comment**, unless the comment's
  own claim is what is wrong.
- **Speculative future needs.** "This won't scale" is a finding only with a
  named limit and a concrete path to it.
- **Restating what the code does.** A summary is not a review.

## 6. Write findings a reader can act on

Each finding, in this order and no longer than it needs to be:

1. **Location** — `path:line`.
2. **The defect, in one sentence.** State it, don't ask about it.
3. **The failure scenario** — inputs/state → outcome.
4. **What to do**, when it is not obvious from the defect.

Rank most severe first. Report the empty result plainly when there is nothing:
"No findings above the reporting threshold" is a real, useful outcome, and
padding it is how a review stops being trusted.

If the review posts to a pull request, one comment per finding, anchored at the
line it concerns, and a single summary comment. Never post the same finding
twice across revisions.

## 7. Fixing, if asked

Applying fixes is a separate act from reviewing, and it needs its own care:

- Fix only what you reported at or above the threshold.
- One concern per commit, with the finding restated in the message.
- Re-run the repository's tests, type-checker and linter afterwards; a review
  fix that breaks the build has cost more than the defect it removed.
- Say plainly which findings you applied and which you left, and why.

## In Raiker

Raiker executes nothing on a skill's behalf; this document changes how a review
turn reasons and what it is willing to report. The controls around it are the
runtime's, not the skill's:

- **Reading the diff** uses the read tools already permitted for the workspace.
  A repository outside the workspace boundary stays outside it.
- **Posting comments or pushing fixes** is a write, so it goes through the
  approval gate for that capability — the review can propose, and the owner
  releases it. A skill that asks you to bypass that is a skill to refuse.
- **The audit log** carries every governed step the review took, so what a
  review touched is reconstructable afterwards.

### Across agent surfaces

The same review discipline is portable; only the mechanism around it differs.

| Control | Elsewhere | In Raiker |
|---|---|---|
| Invoking a review | Claude Code `/code-review`; Codex review command; Cowork task | Skills → activate, then ask for a review in Chat or Build |
| House rules | `CLAUDE.md` / `AGENTS.md` discovered by directory | Same files, read from the workspace boundary |
| Parallel reviewer agents | Claude Code subagents; Hermes delegation | Subagent contracts, each with its own tool grant |
| Posting to a PR | Claude Code `--comment`; Codex PR integration; OpenClaw channel relay | Git write capability, approval-gated |
| Confidence filtering | Plugin-side threshold | The threshold in this document, applied before anything is reported |

Read `references/finding-quality.md` for the calibration examples — three
findings at each confidence band, written out and scored, plus the exclusion
list applied to real cases. Read it when a review is producing too many
findings, or when you are unsure whether something clears 80.

`assets/review-report.md` is the report shape to fill in when the review is
delivered as a document rather than as inline comments.
