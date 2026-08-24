---
name: algorithm-creator
description: Design, specify, and verify an algorithm before writing production code. Use this whenever the task needs a correct procedure rather than glue — sorting, searching, scheduling, graph or tree traversal, dynamic programming, matching, dedup, ranking, pathfinding, numeric or geometric routines — or whenever someone says code is "too slow", "times out", "runs out of memory", "O(n²)", "needs optimizing", or "what's the efficient way to do X". Use it too when an implementation is suspected of being wrong on edge cases, when a data structure has to be chosen, or when a coding-interview-style problem shows up. Reach for this even if the request just describes a computation in plain words and never uses the word "algorithm".
metadata:
  version: 1.1.0
---

# Algorithm creator

Produce an algorithm you can defend: a stated problem, a chosen approach with a
reason, a complexity claim, and a check that would actually fail if the logic
were wrong.

Most wrong algorithms are not wrong because the author lacked knowledge. They
are wrong because the author committed to the first approach that came to mind
before pinning down what the problem actually was. The sequence below exists to
make that failure expensive to reach.

## When this applies

Use it when the hard part is *the procedure*. Skip it when the hard part is
plumbing — wiring a call, renaming a field, moving a file. If the current code
is already fast enough, say so and stop; an optimization nobody needs is a
liability, not a contribution.

## 1. State the problem precisely

Write these four lines before considering any approach:

- **Input** — types, ranges, size (`n ≤ ?`), and whether it is sorted, unique, streamed.
- **Output** — exact shape, and what "correct" means when several answers qualify.
- **Constraints** — time budget, memory ceiling, latency, stability, determinism.
- **Edge cases** — empty, single element, all-equal, duplicates, negatives, overflow, unsorted input, adversarial input.

If any of the four is a guess, mark it as a guess in the final report. An
unstated assumption is how you end up with an algorithm that is perfectly
correct about a problem nobody has.

## 2. Name the shape

Most problems are a known shape wearing different vocabulary, and recognising
the shape is worth more than cleverness. A few of the highest-frequency ones:

| Signal in the problem | Shape to try first |
|---|---|
| "shortest / cheapest path" | BFS (unweighted), Dijkstra (non-negative), Bellman-Ford (negatives) |
| "best over overlapping subproblems" | Dynamic programming — define the state first |
| "k-th / top-k / running median" | Heap, quickselect, or two heaps |
| "contiguous window" or "pair summing to" | Sliding window or two pointers |
| "order with dependencies" | Topological sort |
| "group things that connect" | Union-find |

The full catalogue, with the state-definition recipe for dynamic programming and
the data-structure selection table, is in `references/patterns.md`. Read it when
the table above does not obviously match, or when the shape is right but the
state or the structure is not clear.

If nothing matches, brute force *is* an answer. State it, give its complexity,
and only then argue for something faster.

## 3. Generate a second approach before committing

Always produce a second candidate. This is the single highest-value step here,
because the first idea arrives with unearned confidence and nothing else in the
process tests it. One candidate is enough only when the second is obviously
worse and you can say why in a line.

Compare on:

- time and space complexity, average **and** worst case;
- behaviour at the actual `n`, not asymptotically — an O(n log n) with a heavy
  constant loses to O(n²) at n = 50, and pretending otherwise is a real bug;
- how hard it is to implement correctly, and how it fails when it isn't.

State the pick and the rejected alternative. "Chose X over Y because Y needs
O(n) extra memory and n is 10⁷" is a justification. "X is standard" is not.

## 4. Write the invariant

One sentence that is true before the loop, true after every iteration, and
implies the result when the loop ends. For recursion, write the equivalent: what
the call returns for its subproblem, and why the base case terminates.

If you cannot write it, you do not yet understand the algorithm well enough to
implement it — go back to step 3. This sentence is also what makes the code
reviewable by someone who did not design it.

## 5. Derive the complexity

Count the work rather than recalling a familiar figure: nested loops multiply,
sequential phases add, a `log` appears only where something halves or a balanced
structure is touched. Include the cost of any sort, hash, copy, or allocation
*inside* a loop — that is where claimed and real complexity usually diverge.

Report both time and space. If the space is the output itself, say so, because
it changes whether the number is a problem.

## 6. Implement, then leave a check behind

Write the smallest implementation that satisfies the invariant, then leave one
runnable check — the smallest thing that fails if the logic breaks:

- assertions over the edge cases from step 1; and
- for anything non-obvious, a **brute-force oracle**: implement the naive
  version, run both over randomized inputs, assert they agree. This finds the
  class of bug hand-picked tests never do, because you are no longer the one
  choosing the inputs.

Rather than rewriting that harness each time, use the bundled
`scripts/oracle_check.py`. It generates inputs, compares the two
implementations, and *shrinks* a failure to the smallest input that still
disagrees — which is usually the whole diagnosis:

```python
from oracle_check import check, ints

check(fast=my_median, oracle=lambda xs: sorted(xs)[len(xs) // 2], generate=ints())
```

Run it directly (`python oracle_check.py`) to see it verify itself. Read the
file when the input is not a list of integers — the generator is a plain
callable and the docstring shows how to supply your own.

An algorithm that has not been executed is a proposal, not a result.

## Report

Fill in `assets/algorithm-report.md` — copy it and work down the sections.
The order is the point: each one is only answerable once the one above it is
settled, so a section you cannot complete is telling you the work is not done.

It covers problem statement, chosen approach and rejected alternative,
invariant, complexity, implementation, check and *what the check actually
printed*. Assumed constraints get their own line there rather than being buried
in a comment, because the reader has to be able to see which part of the spec
you invented.

## Where this usually goes wrong

- **Optimising something already fast enough.** Ask what the real budget is first.
- **Boundaries.** `n = 0` and `n = 1` break more algorithms than large inputs do.
- **Overflow and precision.** Fixed-width integers wrap; floats do not compare
  exactly. Name which applies in the target language.
- **A worst case that never gets mentioned.** Quicksort on sorted input, hash
  tables under collision attack. Average-case is the sales pitch; state the
  worst case next to it.
