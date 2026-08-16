## Goal

Make Raiker's memory strong enough to be relied on: able to pick up a
conversation from three or four years ago, and able to quote the exact record
the answer rests on rather than paraphrasing a recollection.

This document is the memory counterpart of
[`TO_BE_FIXED.md`](TO_BE_FIXED.md) and is written to the same standard. Each
entry states what was observed, the reproduction, the root cause in code with
the file that proves it, the proposed fix, and the user-interface outcome that
has to be true before it can be called closed — so closing backend work cannot
leave an invisible or misleading product surface.

## Security posture (read before adding any restriction)

Raiker is **owner-authoritative and monitored, not prevention-by-restriction.**
Memory is the sharpest case of it: what Raiker remembers about its owner is the
owner's own record, so the answer to "should the agent be able to read this"
is *yes, and it should say where it came from* — not a gate that makes the
owner's own history unreachable. What stays governed is **mutation** (a turn
proposing a durable memory) and **egress** (anything that would send a memory
off the machine), never the owner reading their own transcript back. Full
statement: `docs/SECURITY_AND_POLICY.md` → "Security Philosophy".

# Memory reliability

Gaps found while auditing `raiker/memory`, `raiker/vector`, `raiker/graph` and
`raiker/context` against
[`HYBRID_MEMORY_IMPLEMENTATION_PLAN.md`](../HYBRID_MEMORY_IMPLEMENTATION_PLAN.md),
[`GRAPH_MEMORY_AND_CODEMAP_SPEC.md`](../GRAPH_MEMORY_AND_CODEMAP_SPEC.md),
[`EIDETIC_MEMORY_AND_LEARNING_SPEC.md`](../EIDETIC_MEMORY_AND_LEARNING_SPEC.md),
[`MEMORY_AND_CONTEXT_STRATEGY.md`](../MEMORY_AND_CONTEXT_STRATEGY.md) and
[`STORAGE_DATABASE_AND_SEARCH_SPEC.md`](../STORAGE_DATABASE_AND_SEARCH_SPEC.md)
on **2026-08-11**.

The audit's headline is narrower than the specs suggest. Phases A–E of the
hybrid plan are genuinely implemented: the lifecycle, the tombstones, the
human-confirmed purge, the projection bookkeeping and the FTS synchronisation
are all real and tested. What was missing is not a phase — it is the join
between them and a turn. **Durable memory answers "what was I told to
remember". Nothing answered "what did we actually say, and when"**, which is the
question a conversation from years ago is actually asked.

`MEM-01` and `MEM-02` are closed by this change and kept here with their
evidence; `MEM-03` onwards are open.

| ID | Severity | Area | Status |
|---|---|---|---|
| [MEM-01](#mem-01--the-model-had-no-way-to-read-a-past-conversation) | **Critical** | Recall / tools | Fixed 2026-08-11 |
| [MEM-02](#mem-02--ambient-recall-offered-the-eight-most-recent-chats-whatever-the-turn-was-about) | High | Context assembly | Fixed 2026-08-11 |
| [MEM-03](#mem-03--the-vector-leg-of-hybrid-retrieval-is-lexical-so-a-paraphrase-recalls-nothing) | High | Retrieval quality | Open |
| [MEM-04](#mem-04--eidetic-capture-is-never-invoked-by-the-runtime) | High | Eidetic / Stage C | Open |
| [MEM-05](#mem-05--lexical-ranking-is-recency-order-so-the-oldest-exact-answer-is-the-first-one-dropped) | High | Retrieval quality | Open |
| [MEM-06](#mem-06--the-entity-graph-has-no-extractor-so-nothing-ever-populates-it) | Medium | Graph projection | Open |
| [MEM-07](#mem-07--nothing-expires-because-no-retention-sweep-is-ever-started) | Medium | Retention | Open |
| [MEM-08](#mem-08--a-recalled-answer-cannot-be-opened-at-the-turn-it-came-from) | Medium | Chat / Observability | Open |
| [MEM-09](#mem-09--conversation-index-integrity-is-not-covered-by-the-integrity-report) | Low | Reliability | Open |

---

## MEM-01 — The model had no way to read a past conversation

**Status: fixed in this change.**

**Observed.** Asked "what did we decide about the SQLCipher key rotation last
year", a turn answered from whatever was in its context window. It never
consulted the transcript, because it had no tool that could. The forty-one
model-exposed tools included `memory_search`, `memory_list` and `memory_get` —
all three scoped to **approved durable memory**, a store that is empty on a
default install because `memory_write_execution` ships off
(`raiker/memory/candidates.py`). Chat search existed, but only as a page the
human could open: `GET /api/chat-search` (`raiker/api/routes_dashboard.py`).

**Reproduce (before).** Hold a conversation, start a new one, ask about the
first by content. The reply reconstructs rather than quotes, and no tool call
appears in the turn's sources.

**Root cause.** Two separate gaps that read as one.

*No tool.* `raiker/tools/memory_tools.py` exposed only the durable-memory store.
Conversations were reachable from the API and the CLI, never from a turn.

*No index.* `SQLiteStore.search_sessions` ran
`LIKE '%term%'` across `sessions.title`, `turns.prompt_text` and `turns.summary`
with no index behind it — a full scan of every turn the owner had ever taken,
returning whole conversations with no indication of **which** exchange matched.
Workable for a week of history; not a foundation for four years of it.

**Fix.** `conversation_fts`, an FTS4 projection of the `turns` table with one row
per side of an exchange, migration `RAIKER-2020` in
`raiker/storage/migrations.py`. It is rebuilt from `turns` and never read as an
authority: `SQLiteStore.search_conversation_turns` carries every hit back to the
`turns`/`sessions` rows, so ownership is still decided by `sessions.user_id` and
the index narrows the candidate set rather than widening who may see one. New
turns keep themselves in sync through `_sync_conversation_fts`; a workspace that
predates the index is backfilled once on open rather than re-indexed on every
start, and `rebuild_conversation_fts()` is the owner-started repair.

`conversation_search` (`raiker/tools/conversation_tools.py`) is the tool. It is
read-shaped in the policy engine for the same reason `memory_search` is — it
returns records the owner already owns and can already open in Chat — and it is
delegable to a subagent, because a wide investigation is exactly what it is for.
`after` / `before` are the arguments that make an old conversation reachable at
all: any bounded result set is otherwise the recent one, so a question about
last year has to be able to say so.

**User-interface outcome.** Search Chat rows now carry the exchange that matched
(`match_snippet`), not just the conversation's title, so a result says *why* it
matched — the difference between finding a chat from years ago and recognising
it. A turn that used `conversation_search` records a `conversation` source, so
the transcript shows what the answer rested on.

**Evidence.** `tests/test_conversation_recall.py`; live round of
[the manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) §18.

---

## MEM-02 — Ambient recall offered the eight most recent chats, whatever the turn was about

**Status: fixed in this change. Found while fixing MEM-01.**

**Observed.** Every turn's context bundle carried a "Recall from memory, prior
chats, builds, and projects" item. Its prior-chat half was
`store.list_sessions(limit=8, …)` — the eight most recently *updated*
conversations, ranked by nothing to do with the prompt
(`raiker/context/gatherer.py::_memory_recall`). A conversation from three years
ago could therefore never be recalled, however exactly it answered the question,
and on a busy workspace the eight slots were spent on chats from this morning.

**Root cause.** The item was written when recall meant "remind the model that
other conversations exist". Relevance was not available to it: there was no
index to ask.

**Fix.** `_recalled_sessions` now asks `search_conversation_turns` with the
turn's own prompt first and fills the remaining slots with recent conversations,
so a prompt with no lexical match behaves exactly as it did. Each recalled row
carries the one line that matched. It stays **metadata plus one line** — the
full exchange stays behind `conversation_search`, so ambient context does not
grow with the owner's history.

**User-interface outcome.** The context meter's recall item names the matched
line, so the owner can see which old conversation the model was given and why.
Incognito remains an absolute read opt-out ahead of all of it.

**Evidence.** `tests/test_conversation_recall.py`.

---

## MEM-03 — The vector leg of hybrid retrieval is lexical, so a paraphrase recalls nothing

**Severity: High. Area: retrieval quality.**

**Observed.** `retrieve_hybrid_memory` combines a lexical, a vector and a graph
candidate list and presents the result as hybrid retrieval
(`raiker/memory/retrieval.py`). The vector leg calls `embed_text`
(`raiker/vector/__init__.py`), which is the hashing trick over lowercased
alphanumeric tokens — an honest, offline, reproducible embedding that captures
**lexical overlap and nothing else**, as its own docstring says. Two of the
three legs are therefore the same signal at different weights, and a memory
recorded as "the owner prefers the encrypted NAS target" is not retrieved by
"where should backups go".

**Reproduce.** Approve a memory, then search it with a synonym-only query. The
lexical leg misses, the vector leg misses identically, and the result is empty
while the Memory page shows the record plainly.

**Root cause.** A model-backed embedding needs either a downloaded local model or
an egress-gated provider call. Neither has been wired, so the placeholder stayed
and `semantic_memory_status()` (`raiker/memory/semantic.py`) hard-codes
`embedding_backend: "disabled"` — which is truthful about writes, but the
hashing embedding is used for **reads** regardless.

**Proposed fix.** Wire the existing `vector_embedding_runtime` capability to a
real embedding backend, owner-selected: a bundled local sentence embedding for
the offline case, or a configured provider for owners who already accepted that
egress. Record model, version and dimension on every stored vector (the
projection mapping already has the columns), and refuse to mix vectors from two
backends in one search. Keep `raiker-local-hash-v1` as the labelled fallback.

**Required user-interface outcome.** Models → the memory section names the
embedding backend in force, and Memory states which of the two postures the
owner is in. A hybrid result names the leg each hit came from — it already
carries `sources` — so "found lexically" and "found semantically" are
distinguishable rather than both being called hybrid.

---

## MEM-04 — Eidetic capture is never invoked by the runtime

**Severity: High. Area: eidetic / Stage C.**

**Observed.** `EIDETIC_MEMORY_AND_LEARNING_SPEC.md` specifies the flow *agent
event → classify sensitivity → eidetic observation → gist candidate → review →
durable memory*. `raiker/memory/eidetic.py` implements
`record_observation`, `propose_gist`, `expiry_preview` and
`cleanup_expired_observations` correctly, and the `eidetic_observations` and
`gist_memories` tables exist. **No runtime path calls any of them.** Every
caller in the repository is a test.

**Reproduce.** Run a turn that reads a file and produces an answer, then query
`SELECT COUNT(*) FROM eidetic_observations`. It is zero, on every workspace.

**Root cause.** Phase C was delivered as a library with its lifecycle proven in
isolation; the orchestrator was never given the call. The result is that the
high-fidelity half of "eidetic memory" is a capability the product has and never
exercises, which is worse than not having it: the docs describe a flow the
database can never show.

**Proposed fix.** Have the tool broker record one observation per governed tool
result that produced material — provenance, checksum, retention class, and an
artifact reference where one already exists — reusing the sensitivity classifier
that already refuses credential-like text. Never the raw payload in the row.
Then propose a gist only where the spec allows one, leaving it `pending_review`.

**Required user-interface outcome.** Memory gains an **Observations** view
showing what was captured, its retention class and its expiry, with the same
delete control the rest of memory has. A capture that was skipped for
sensitivity says so, so an empty list is distinguishable from a disabled one.

---

## MEM-05 — Lexical ranking is recency order, so the oldest exact answer is the first one dropped

**Severity: High. Area: retrieval quality.**

**Observed.** The SQLCipher distribution Raiker ships provides FTS4, not FTS5, so
there is no BM25 (`HYBRID_MEMORY_IMPLEMENTATION_PLAN.md`, Stage H). Both
`search_approved_memory` and the new `search_conversation_turns` therefore order
by `created_at DESC` and truncate at the limit. On a four-year workspace the
exact answer from 2023 is behind hundreds of newer partial matches, and is
dropped before it is ranked.

**Reproduce.** Index a corpus where the best match is the oldest record, search a
term that appears in many newer ones, and take the top ten. The best match is
absent.

**Root cause.** Ordering by time is the only deterministic order available
without a relevance score. `after`/`before` (MEM-01) make an old record
*reachable* when the caller knows the period; they do not make it *rank*.

**Proposed fix.** Compute a deterministic relevance score above the index —
matched-term count, term coverage over the record, and a field weight for a hit
in a prompt versus an answer — then order by score before recency and expose the
weights as data the way `HybridRetrievalWeights` already does. This needs no
FTS5 and no new dependency. Measure it on the `memory-eval-v1` corpus rather than
asserting the improvement.

**Required user-interface outcome.** Search Chat and Memory results are ordered
by relevance with the date shown, and a result set that was truncated says so
rather than presenting the first page as the whole answer.

---

## MEM-06 — The entity graph has no extractor, so nothing ever populates it

**Severity: Medium. Area: graph projection.**

**Observed.** `GRAPH_MEMORY_AND_CODEMAP_SPEC.md` specifies typed nodes and edges
for people, projects, decisions and documents. The storage is real and
lifecycle-aware — `list_memory_entity_neighborhood` is queried by
`retrieve_hybrid_memory` whenever an `entity_id` is supplied — but nothing
extracts an entity from an approved memory, so the table is empty and the graph
leg of hybrid retrieval contributes zero on every workspace.

**Root cause.** Stage G's extraction slice is explicitly pending. The gap is that
the retrieval path already advertises the leg.

**Proposed fix.** Extract candidate entities and relationships from approved
memories only (never from raw conversation), require evidence IDs and a
confidence on every edge, and route every inference through the human review
queue the plan already specifies — sensitive, uncertain or conflicting
inferences must never auto-promote.

**Required user-interface outcome.** Knowledge Map shows entity nodes with the
memories that evidence them and lets the owner reject an edge. Until an
extractor exists, hybrid results should not imply a graph leg that cannot
contribute.

---

## MEM-07 — Nothing expires, because no retention sweep is ever started

**Severity: Medium. Area: retention.**

**Observed.** Six retention classes are defined and stored, and
`expiry_preview` / `cleanup_expired_observations` implement the owner-confirmed
sweep correctly. Nothing schedules or offers the sweep, so `turn_only` and
`short_term_7_days` records are retained indefinitely on every workspace.

**Root cause.** "No automatic cleanup worker" is a deliberate non-goal, and
correctly so. But the deliberate alternative — the owner being *shown* what is
due and asked — was never built, so the honest boundary reads as an omission.

**Proposed fix.** Surface the existing preview: a Memory panel listing what is
due for expiry by class, with the owner-confirmed cleanup already implemented
behind it. No daemon, no automatic delete, and legal holds still override.

**Required user-interface outcome.** Memory states the retention class of every
record and lists what is due, with one control that runs the confirmed cleanup
and reports exactly what it removed.

---

## MEM-08 — A recalled answer cannot be opened at the turn it came from

**Severity: Medium. Area: Chat / Observability.**

**Observed.** `conversation_search` returns `session_id` and `turn_id`, and the
model can cite both. Neither is a link: nothing in the web app accepts a turn
coordinate and opens that conversation scrolled to that exchange.

**Root cause.** New surface — the coordinates did not exist before MEM-01.

**Proposed fix.** Accept a turn anchor on the Chat route and scroll the
transcript to it, and render a cited coordinate in an answer as a link.

**Required user-interface outcome.** "We settled this on 12 March 2023" is
clickable, and lands on the exchange itself. Verifying a recalled claim is one
click rather than a manual search.

---

## MEM-09 — Conversation index integrity is not covered by the integrity report

**Severity: Low. Area: reliability.**

**Observed.** The owner-started integrity report (`raiker/memory/integrity.py`)
detects stale FTS, projection and graph state for durable memory. It does not
know about `conversation_fts`, so a divergence between `turns` and its index —
an interrupted write, a restored backup — is invisible.

**Proposed fix.** Add a conversation-index check comparing indexed rows against
eligible `turns` rows and report the drift, with `rebuild_conversation_fts()` as
the stated repair.

**Required user-interface outcome.** Observability → Diagnostics names the drift
and offers the rebuild, rather than the owner discovering it as a search that
quietly stopped finding things.

**Re-scoped on 2026-08-16, and it is larger than this entry says.** Adding the
check is a few lines against `inspect_memory_integrity`. The blocker is that
**the report it would join is not reachable from the product at all**:
`run_one_memory_job` is the only caller of `inspect_memory_integrity`, and
nothing calls `run_one_memory_job` — there is no API route, no scheduler entry
and no Diagnostics panel. Adding a conversation-index count to a report nothing
displays would satisfy the first paragraph of this entry and none of the last
one, which is the invisible-surface failure this document exists to prevent. The
real work is therefore: surface the existing report (route + Diagnostics panel +
an owner-started rescan), *then* add the conversation-index check and
`rebuild_conversation_fts()` as its stated repair. Related and now closed:
[FIXED-222](FIXED_ITEMS.md) fixed the *audit* chain reporting a gap on an intact
log, which is the same class of defect one layer down.

---

## Verified working (no action needed)

Recorded so the entries above are read against the right baseline. Confirmed by
reading the code and its tests on **2026-08-11**:

the full durable-memory lifecycle — active, archived, forgotten with a
tombstone, and `purged` as a human-confirmed result that records what happened
to database rows, FTS rows, vectors, graph edges, artifacts, exports and
backups; the absence of any agent-reachable purge route; self-inclusive project
paths with deterministic nearest-ancestor context merge and tri-state
`memory_mode`; source-versioned `fts` / `vector` / `graph` projection mappings
that archive, restore, forget and purge fan out to; owner-started reconciliation
and a read-only integrity report; correction and supersession links with
valid-from / valid-until so a fact can be `was_true`, `currently_true` or
`superseded`, and an FTS record that excludes a superseded one; credential-like
text refused before the owner is ever asked to approve it; incognito as an
absolute read opt-out ahead of every recall path; per-principal ownership
enforced on every memory row and every retrieval; SQLCipher encryption of the
workspace database including the FTS and projection metadata; append-only
lifecycle audit rows; the `memory-eval-v1` corpus with CI enforcing zero policy
leaks; and idempotent maintenance jobs with leases, retry and dead-letter state.
