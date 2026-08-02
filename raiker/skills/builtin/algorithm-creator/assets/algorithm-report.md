# [Problem in one line]

Copy this file and fill it in. The order matters: each section is only
answerable once the one above it is settled, so a section you cannot fill in is
telling you the work is not finished rather than that the template is wrong.

## Problem

- **Input** — types, ranges, size (`n ≤ ?`), sorted / unique / streamed?
- **Output** — exact shape, and what "correct" means when several answers qualify.
- **Constraints** — time budget, memory ceiling, latency, stability, determinism.
- **Edge cases** — empty, single element, all-equal, duplicates, negatives,
  overflow, unsorted, adversarial.

**Assumed, not given:** [anything above that you decided rather than were told.
Leave the heading in and write "nothing" if that is true — a reader has to be
able to tell the difference between "no assumptions" and "did not check".]

## Approach

**Chosen:** [name the shape, then the specific variant.]

**Why:** [what makes it right *for these constraints* — not why it is a good
algorithm in general.]

**Rejected:** [the second candidate, and the concrete reason it lost. "Needs
O(n) extra memory and n is 10⁷" is a reason. "Less standard" is not.]

## Invariant

[One sentence: true before the loop, true after every iteration, and implying
the result when the loop ends. For recursion: what the call returns for its
subproblem, and why the base case terminates.]

## Complexity

- **Time:** O(?) average, O(?) worst. [Say where the worst case comes from.]
- **Space:** O(?). [Say whether that is the output itself.]

Derived by: [count the work — nested loops multiply, phases add, `log` where
something halves. Include sorts, hashes, copies, and allocations inside loops.]

## Implementation

```
[the code]
```

## Check

```
[the assertions and/or the brute-force oracle]
```

**Result:** [what happened when you ran it. Not "should pass" — what it printed.]

## Known limits

[Inputs where this degrades or does not apply, and what to reach for instead.]
