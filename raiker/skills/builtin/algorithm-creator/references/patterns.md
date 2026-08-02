# Problem shapes, state definitions, and structure selection

Read this from `SKILL.md` step 2 when the short table there does not obviously
match the problem, or when the shape is clear but the state or data structure is
not.

## Contents

- [Full shape catalogue](#full-shape-catalogue)
- [Defining a dynamic-programming state](#defining-a-dynamic-programming-state)
- [Choosing a data structure](#choosing-a-data-structure)
- [Complexity of the operations you will reach for](#complexity-of-the-operations-you-will-reach-for)
- [Recognising a problem that is harder than it looks](#recognising-a-problem-that-is-harder-than-it-looks)

## Full shape catalogue

| Signal in the problem | Shape | Typical cost |
|---|---|---|
| "shortest path", unweighted | BFS | O(V + E) |
| "shortest path", non-negative weights | Dijkstra with a heap | O((V + E) log V) |
| "shortest path", negative weights | Bellman-Ford | O(V·E) |
| "shortest path between every pair" | Floyd-Warshall | O(V³) |
| "cheapest set of edges connecting everything" | Kruskal or Prim | O(E log V) |
| "best over overlapping subproblems" | Dynamic programming | depends on state |
| "best local choice is provably global" | Greedy + exchange argument | usually O(n log n) |
| "try everything, prune early" | Backtracking with bounds | exponential, bounded |
| "k-th smallest / largest" | Quickselect | O(n) average |
| "top-k of a stream" | Bounded min-heap | O(n log k) |
| "running median" | Two heaps | O(log n) per element |
| "contiguous subarray with property" | Sliding window | O(n) |
| "pair/triple summing to target" | Sort + two pointers, or hash map | O(n log n) / O(n) |
| "does X exist among many" | Hash set, or sorted + binary search | O(1) / O(log n) |
| "prefix or range sums, many queries" | Prefix sums (static), Fenwick/segment tree (updates) | O(1) / O(log n) |
| "group things that connect" | Union-find | near O(1) amortised |
| "order respecting dependencies" | Topological sort (Kahn or DFS) | O(V + E) |
| "detect a cycle" | DFS colouring, or union-find | O(V + E) |
| "match A to B, one-to-one" | Bipartite matching (Hopcroft-Karp), or stable matching | O(E√V) |
| "string occurs inside string" | KMP, Rabin-Karp, or the language's built-in | O(n + m) |
| "many strings, shared prefixes" | Trie | O(length) per op |
| "intervals overlapping" | Sort by start, sweep | O(n log n) |
| "closest pair / nearest neighbour" | Divide and conquer, or spatial index | O(n log n) |

## Defining a dynamic-programming state

DP fails far more often at the state definition than at the implementation. Work
in this order:

1. **Write the state as a sentence.** "`dp[i][w]` is the best value using the
   first `i` items within weight `w`." If the sentence needs an "and also"
   clause, the state is missing a dimension.
2. **Write the transition.** How does `dp[i]` follow from strictly earlier
   states? If it depends on a later state, the ordering is wrong.
3. **Write the base case**, and check it is reachable from the transition.
4. **Write the answer** — which cell (or which max over cells) is the result.
   Being unable to name it usually means the state describes the wrong thing.
5. **Count the cost**: states × work per transition. That is the complexity; if
   it is too large, the state needs fewer dimensions or coarser values.

Only then consider memoised recursion versus a bottom-up table. Memoisation is
easier to get right and easier to read; bottom-up avoids recursion limits and
allows dropping to a rolling array when only the previous row is needed.

## Choosing a data structure

Pick from what the operation mix actually is, not from what feels sophisticated:

| Need | Structure | Note |
|---|---|---|
| Membership, no order | Hash set | O(1) average; worst case is O(n) under collisions |
| Key → value, no order | Hash map | Same caveat |
| Sorted order + range queries | Balanced BST / sorted array | Array wins when static |
| Min or max repeatedly | Binary heap | Not searchable — only the extreme is cheap |
| Both ends | Deque | Sliding-window maxima live here |
| Merge groups, ask "same group?" | Union-find | Path compression + union by rank |
| Prefix strings | Trie | Memory-hungry; worth it for many shared prefixes |
| Range sum/min with updates | Fenwick (sums) / segment tree (general) | Fenwick is smaller and simpler |
| Fixed small universe | Bit set | Enormous constant-factor win |

## Complexity of the operations you will reach for

Costs that hide inside a loop and quietly change the answer:

- Sorting: O(n log n). Sorting *inside* a loop over n is O(n² log n).
- Slicing/copying a list: O(k) in the size of the slice, not O(1).
- `list.insert(0, x)` / `list.pop(0)`: O(n). Use a deque.
- `x in list`: O(n). `x in set`: O(1) average.
- String concatenation in a loop: O(n²) in most languages. Build a list, join once.
- Dictionary/set rehash: amortised O(1), but the amortisation assumes many ops.

## Recognising a problem that is harder than it looks

Some problems have no known efficient exact solution. Recognising one early
saves hours and changes what you should deliver:

- Subset-sum, knapsack with real-valued weights, bin packing.
- Travelling salesman, longest path, graph colouring, maximum clique.
- Anything asking for the optimum over all subsets or all orderings, where the
  count is 2ⁿ or n!.

When the problem is one of these, say so, then offer what is actually available:
an exact algorithm for small `n` (with the `n` at which it stops being viable), a
pseudo-polynomial DP when the values are bounded integers, or an approximation
or heuristic with its guarantee stated. Silently shipping a heuristic as though
it were exact is the failure to avoid here.
