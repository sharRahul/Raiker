# Threat model — semantic memory search (`semantic_memory_runtime`)

`semantic_memory_runtime` is a **read-only** capability over the owner's approved
memory store. It writes nothing, reaches no network and starts no process. It is
documented because a read of the owner's private memory is still a disclosure
boundary, and because what this capability is *called* promises more than what it
does.

## What the capability does

`raiker/runtime/executors/tier3_core.py` → `SemanticMemoryExecutor` requires a
`query` and calls `raiker.memory.store.search_memory`, scoped to
`store.account_scope(principal.principal_id)`. Artifacts are a **result count
only** — no memory text, no ids, no query, enters a runtime event.

The retrieval underneath is the same one `memory_search` and the runtime's
ambient recall use (`retrieve_hybrid_memory`), which is asserted by test (MEM-11)
so the model's search and the runtime's recall cannot diverge.

## The name is wider than the behaviour

This is the most important thing on the page, and it is a documentation duty
rather than a control:

- **Retrieval is lexical on both legs.** The lexical half is FTS5 ranked by
  `bm25()`; the "vector" half is a feature-hashing bag-of-tokens embedding
  computed with **no model** (`raiker/vector/__init__.py`). A memory that answers
  the question in different words scores zero.
- **The durable semantic/vector *write* path is disabled outright.**
  `semantic_write_policy_decision` (`raiker/memory/policy.py`, applied in
  `raiker/memory/review.py`) returns a refusal with
  `phase3_semantic_vector_writes_disabled`, and additionally flags
  `secret_or_credential_like_candidate_blocked` for sensitive candidates.
  `raiker/memory/semantic.py` reports what the *read* backend actually is, which
  is a separate question and is where the honest answer lives.
- Raiker states this rather than letting the word "semantic" imply otherwise:
  the Memory page names the embedding space in force and says whether a
  paraphrase can recall anything at all. Tracked as MEM-10 in
  [Known limits](../KNOWN_LIMITS.md).

## Assets

| Asset | Why it matters |
|---|---|
| The approved-memory corpus | It is the owner's accumulated private record |
| The account scope on every read | It is what stops one instance's owner reading another's memory |
| The query itself | It reveals what the agent was asked to look for |

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| Reading another account's memories | Every read is scoped by `store.account_scope(principal.principal_id)`; the scope is never a model argument | `tier3_core.py`, `raiker/storage/sqlite.py` |
| An empty query enumerating the whole store | `missing_argument:query` fails closed on an empty query | `tier3_core.py` |
| Memory text leaking into the audit log | Artifacts carry `result_count` only | `tier3_core.py` |
| Deleted or expired memories resurfacing | Rows with `deleted_at`, `archived_at`, or a past `expires_at` are excluded at read time | `raiker/memory/store.py` |
| The model's recall and the runtime's recall disagreeing | Both call `retrieve_hybrid_memory`; asserted by test | MEM-11 |
| Recalled text being treated as instruction | Retrieved material is injected as an **untrusted-data** block, never as a system instruction | `raiker/runtime/retrieval.py` |
| A credential reaching the store to be recalled later | Refused on the **write** side before the owner is asked — see [`memory-write.md`](memory-write.md) | `raiker/tools/broker.py` |

## Residual risk, stated plainly

- **Recall cost is linear and paid on every turn.** Retrieval loads all active
  vectors for the scope, rebuilds the index in memory and scores them in Python:
  ~30 ms at 200 memories, ~124 ms at 1 000, ~431 ms at 3 000. There is no
  approximate-nearest-neighbour index and no cache.
- **A natural-language question drops the lexical leg.** Terms shorter than three
  characters are discarded and the rest are combined with an implicit `AND`, so
  the longer the question, the likelier every term must appear in one memory.
- **The filesystem fallback is unscoped.** `search_memory` prefers the encrypted
  store; when called with `store=None` it walks the memory directory and does not
  apply the owner filter. Every product caller passes a store — this executor
  does — but the fallback exists and is the reason the account scope is asserted
  at the call site rather than assumed inside.
- **Nothing expires by itself.** `expires_at` is enforced at read time only; no
  retention sweep runs (MEM-07).

## Evidence

- `raiker/runtime/executors/tier3_core.py`, `raiker/memory/store.py`,
  `raiker/memory/semantic.py`, `raiker/vector/`
- [`../MEMORY_AND_CONTEXT_STRATEGY.md`](../MEMORY_AND_CONTEXT_STRATEGY.md)
- [`../plans/MEMORY_RELIABILITY_PLAN.md`](../plans/MEMORY_RELIABILITY_PLAN.md) — the full audit with reproductions
- [`vector-embedding.md`](vector-embedding.md) — the embedding capability it ranks with
