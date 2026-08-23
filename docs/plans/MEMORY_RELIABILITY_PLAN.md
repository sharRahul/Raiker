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

`MEM-01` and `MEM-02` are closed by the 2026-08-11 change and kept here with
their evidence. `MEM-03` and `MEM-05` are closed by the 2026-08-17 change
(FIXED-230 and FIXED-231) and likewise kept with theirs, as is `MEM-04`
(FIXED-237) by the second pass of the same day; MEM-06 is closed by FIXED-241.

| ID | Severity | Area | Status |
|---|---|---|---|
| [MEM-01](#mem-01--the-model-had-no-way-to-read-a-past-conversation) | **Critical** | Recall / tools | Fixed 2026-08-11 |
| [MEM-02](#mem-02--ambient-recall-offered-the-eight-most-recent-chats-whatever-the-turn-was-about) | High | Context assembly | Fixed 2026-08-11 |
| [MEM-03](#mem-03--the-vector-leg-of-hybrid-retrieval-is-lexical-so-a-paraphrase-recalls-nothing) | High | Retrieval quality | Fixed 2026-08-17 |
| [MEM-04](#mem-04--eidetic-capture-is-never-invoked-by-the-runtime) | High | Eidetic / Stage C | Fixed 2026-08-17 |
| [MEM-05](#mem-05--lexical-ranking-is-recency-order-so-the-oldest-exact-answer-is-the-first-one-dropped) | High | Retrieval quality | Fixed 2026-08-17 |
| [MEM-06](#mem-06--the-entity-graph-has-no-extractor-so-nothing-ever-populates-it) | Medium | Graph projection | **Fixed 2026-08-21** |
| [MEM-07](#mem-07--nothing-expires-because-no-retention-sweep-is-ever-started) | Medium | Retention | Open |
| [MEM-08](#mem-08--a-recalled-answer-cannot-be-opened-at-the-turn-it-came-from) | Medium | Chat / Observability | Open |
| [MEM-09](#mem-09--conversation-index-integrity-is-not-covered-by-the-integrity-report) | Low | Reliability | Open |
| [MEM-10](#mem-10--semantic-recall-is-selectable-but-a-default-install-has-nothing-to-select) | Medium | Retrieval quality | Open — raised 2026-08-17 |
| [MEM-11](#mem-11--the-agents-own-memory-search-and-the-runtimes-recall-disagreed) | High | Retrieval consistency | Fixed 2026-08-17 |
| [MEM-12](#mem-12--the-graph-leg-was-gated-on-an-anchor-no-caller-ever-supplied) | High | Retrieval quality | Fixed 2026-08-17 |
| [MEM-13](#mem-13--the-knowledge-graph-was-drawn-for-a-person-and-unreachable-from-a-turn) | Medium | Agent reach | Fixed 2026-08-17 |
| [MEM-14](#mem-14--the-citation-ledger-could-only-be-read-forwards) | Medium | Agent reach | Fixed 2026-08-17 |

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

**Evidence.** `tests/test_conversation_recall.py`; the memory recall round of
2026-08-11 in [`LIVE_TEST_ROUNDS.md`](LIVE_TEST_ROUNDS.md). The procedure that
re-proves it is
[the manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) §10.5.

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

**Severity: High. Area: retrieval quality. Status: fixed 2026-08-17.**

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

**Fixed 2026-08-17.** The fix is not a better hash — it is making the embedding
an owner-selected space that **names itself**, which is what turns a silent
wrong answer into a visible one.

*The resolver.* `raiker/vector/backends.py` resolves one `EmbeddingBackend` per
search: the owner's explicit selection, else any semantic space this workspace
actually holds vectors in, else the labelled lexical fallback. Resolution is
**evidence-led, not configuration-led** — `list_embedding_spaces` reads the
spaces from the vectors themselves, so a space is selectable exactly when
searching it would return something, and a stored selection that has gone empty
resolves to the fallback carrying
`embedding_backend_selected_has_no_vectors:<model>` rather than answering from a
corpus the owner did not choose.

*One space, or none.* `retrieve_hybrid_memory` embeds the query with the resolved
backend and reads only that backend's vectors. When the stored vectors are
semantic and no governed embedder is available to match them, the vector leg is
**dropped**. That is the deliberate part: the alternative is to hash the query
and compare two unrelated spaces, and a cosine between different coordinate
systems is not a weaker signal but a meaningless one. A missing leg is a smaller
lie than a meaningless one.

*The egress stays where the gate is.* This module never calls a provider. A
`query_embedder` is injected by the caller that already holds the capability
check, so the retrieval path cannot acquire egress by being called.

*What every surface now says.* `HybridMemoryResult` carries `vector_backend` and
`vector_backend_semantic`. `semantic_memory_status()` reports
`retrieval_embedding_backend`, `retrieval_embedding_kind` and
`retrieval_is_semantic` **separately from the write gate** — the old single
`embedding_backend: "disabled"` was true of writes and silent about reads while
the vector leg ran on every search. Memory → **Recall backend** names the model
in force and says in one sentence whether a paraphrase can recall anything at
all. Selecting a space that holds no vectors is refused with
`embedding_backend_unknown` rather than quietly downgraded.

*What is still true.* Semantic recall is available but **off on a default
install**, because the honest options are a model download or accepted provider
egress and both are the owner's decision. The remaining work — a bundled local
sentence-embedding model served through the existing llama.cpp runtime — is a
model-acquisition task, not a retrieval one. `raiker-local-hash-v1` remains the
labelled fallback and is no longer describable as semantics.

*Evidence.* `tests/test_memory_embedding_backend.py` — seven cases, including
the two that state the defect directly: a semantic corpus with no embedder
answers lexically-only rather than from the wrong space, and the same corpus
with a matching embedder recalls a query that **shares no token** with the
memory.

**Required user-interface outcome.** Models → the memory section names the
embedding backend in force, and Memory states which of the two postures the
owner is in. A hybrid result names the leg each hit came from — it already
carries `sources` — so "found lexically" and "found semantically" are
distinguishable rather than both being called hybrid.

---

## MEM-04 — Eidetic capture is never invoked by the runtime

**Severity: High. Area: eidetic / Stage C. Status: fixed 2026-08-17 as
[FIXED-237](FIXED_ITEMS.md).**

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

**What was built.** `raiker/memory/capture.py` is the call the orchestrator
never had, and it is a policy module rather than three lines in the broker
because three decisions have to be made in one place and be readable afterwards:
**never the payload** (summary, checksum, byte count, retention class and an
artifact reference where one exists — the row has no column that could hold the
material), **a refusal is a row** (credential- and secret-like material is not
captured and *that* is recorded, with no digest and no byte count either, since
a SHA-256 of a credential is still a fact about it), and **outside material is
never promotable** (web, connector and MCP results are observable and can never
become a memory candidate). Retention is chosen by what produced the material —
seven days for outside material and command output, thirty for workspace
material — and the expiry date is stored, so the owner reads a date. A gist is
proposed only from a conclusion, never from each file read, and lands
`pending_review`.

The interface outcome is met in full: Memory → **Observations** lists every row
with its kind, retention, expiry, sensitivity and checksum; filters by kind, by
refusal and by pending gist; deletes per row; discards a proposed gist; reads
**Not captured** with its reason for a refusal; and says *observation capture is
not reporting* when the read itself fails, rather than rendering that as
"captured nothing".

---

## MEM-05 — Lexical ranking is recency order, so the oldest exact answer is the first one dropped

**Severity: High. Area: retrieval quality. Status: fixed 2026-08-17.**

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

**Fixed 2026-08-17 — and the stated root cause was false.** "The SQLCipher
distribution Raiker ships provides FTS4, not FTS5" was written down, carried
forward through several rounds, and never checked. It is wrong:
`sqlcipher3-wheels` compiles with `ENABLE_FTS5`, and so does CPython's bundled
SQLite on every platform Raiker targets. A whole workaround was designed around
a constraint that did not exist.

So the fix is the one the constraint had ruled out. RAIKER-2025 migrates both
full-text indexes to FTS5 — safe precisely because each is a **rebuildable
projection** of a governed table, never a second source of truth — and both
searches now order by `bm25()` before recency. `search_approved_memory` weights
the approved sentence above its tags (`0.0, 1.0, 0.4`); `search_conversation_turns`
weights only its one indexed column. Ordering is relevance first, recency only
to break ties.

The engine is still **probed rather than declared**: a temporary `fts5` virtual
table is created and dropped, because a build can advertise `ENABLE_FTS5` and
still refuse the module, and a build genuinely without it keeps FTS4 and keeps
working. `snippet()` takes its six arguments in a different order on each engine
— and on FTS4 the wrong order returns NULL rather than raising — so the order is
derived from that probe. `memory_evaluation_runs.backend_version` is written from
it too, so an FTS4 measurement and an FTS5 one are never compared as though they
were the same thing.

*Evidence.* `tests/test_text_search_fts5.py` — including the case this entry
describes: the best answer is the **oldest** row, five newer rows mention the
term once each, and it ranks first at `limit=2` instead of being dropped. The
FTS4→FTS5 conversion is driven from a real FTS4 index and asserted to answer the
same query afterwards.

**Required user-interface outcome.** Search Chat and Memory results are ordered
by relevance with the date shown, and a result set that was truncated says so
rather than presenting the first page as the whole answer.

---

## MEM-06 — The entity graph has no extractor, so nothing ever populates it

**Severity: Medium. Area: graph projection.**

**Status: fixed 2026-08-21 (FIXED-241).** Approved memories, imports and
accepted conversation evidence now produce deterministic owner-scoped entity
and relationship proposals. Every candidate carries evidence metadata and an
idempotency key; review is atomic, rejection is durable, and accepted edges are
the only ones projected into graph recall. Memory and Brain expose scan,
accept/reject and provenance controls without presenting parser inference as
fact. MEM-11/MEM-12 regressions continue to prove one hybrid retrieval path and
query-resolved graph anchors.

**Observed.** `GRAPH_MEMORY_AND_CODEMAP_SPEC.md` specifies typed nodes and edges
for people, projects, decisions and documents. The storage is real and
lifecycle-aware — `list_memory_entity_neighborhood` is queried by
`retrieve_hybrid_memory` whenever an `entity_id` is supplied — but nothing
extracts an entity from an approved memory, so the table is empty and the graph
leg of hybrid retrieval contributes zero on every workspace.

**Root cause.** Stage G's extraction slice is explicitly pending. The gap is that
the retrieval path already advertises the leg.

**Proposed fix.** Extract candidate entities and relationships from approved
memories and from raw conversation, require evidence IDs and a
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

---

## MEM-10 — Semantic recall is selectable, but a default install has nothing to select

**Severity: Medium. Area: retrieval quality. Raised 2026-08-17 while closing
MEM-03.**

**Observed.** Memory → **Recall backend** offers **Automatic** and nothing else
on a workspace that has never been configured, and states plainly that
`raiker-local-hash-v1` "matches words, not meaning". That sentence is true and
it is the honest thing to say — but it is also the whole story for every owner
who has not accepted provider egress. The paraphrase case MEM-03 opened with,
"where should backups go" recalling "the owner prefers the encrypted NAS
target", still does not work out of the box.

**Reproduce.** Install fresh, approve a memory, search it with a synonym-only
query. The lexical leg misses; the vector leg is the labelled fallback and
misses identically. The interface says why, which is the MEM-03 fix — but the
recall does not happen.

**Root cause.** MEM-03 built the *selection* mechanism, not a thing to select.
`resolve_embedding_backend` is evidence-led: a space is offered exactly when
the workspace holds vectors in it, and a default install holds none. Producing
them needs an embedding model, and the two honest ways to get one — a download,
or a provider call — are both owner decisions rather than defaults. Making
either the default would be the thing this codebase does not do.

**Proposed fix.** Serve a small sentence-embedding model through the local
runtime Raiker already manages. `raiker/models/providers/llama_cpp_server.py`
speaks the OpenAI-compatible `/v1/embeddings` shape and
`raiker/models/gguf.py` already handles revision-pinned, dry-run-capable
downloads, so the missing pieces are a curated GGUF embedding model in the
library, a Memory-page action that offers the download with its size stated
before anything is fetched, and a governed backfill that projects existing
approved memories into the new space. Record model, revision and dimension on
every vector — the columns exist and `list_embedding_spaces` already reads them
— and keep `raiker-local-hash-v1` as the labelled fallback for an owner who
declines.

**Required user-interface outcome.** The Recall backend card offers the
download as an owner choice with its cost stated, never fetches on its own, and
after a backfill says which space is in force and how many memories are
reachable in it. An owner who declines sees exactly what they see today,
including the sentence about what the fallback cannot do.


---

## MEM-11 — The agent's own memory search and the runtime's recall disagreed

**Severity: High. Area: retrieval consistency. Status: fixed 2026-08-17.**

**Observed.** In one turn, two different answers to the same question reached
the model. The context gatherer injected "Recalled owner context" built by
`retrieve_hybrid_memory` — lexical, vector and graph. The `memory_search` tool
the model could actually call ran `search_memory`, which is the lexical index
and nothing else. The weaker of the two was the half the model could steer.

The second half of the defect was worse, because it made an interface untrue:
choosing a **Recall backend** on the Memory page (MEM-03/FIXED-230) changed the
injected context and left `memory_search` exactly as it was. The page described
a choice that did not apply to the search the assistant ran.

**Reproduce (before).** Approve a memory, project a vector for it, then compare
`memory_search("…")` against `retrieve_hybrid_memory(query="…")` for the same
query. The tool returns a subset, ordered differently, with no vector hits.

**Root cause.** Two call sites for one concept, added at different times.
`memory_tools.memory_search` predates hybrid retrieval and was never revisited
when the gatherer adopted it, and nothing compared the two — a test of each in
isolation passes.

**Fix.** `memory_search` calls `retrieve_hybrid_memory`. The reply names the
strategy, the legs, the embedding space and whether that space is semantic;
every hit names the legs that found *it*, so a lexical-only match cannot read as
corroborated by three independent signals. `created_at`, `tags` and `source` —
which the lexical shape returned — are carried on `HybridMemoryResult` from the
row it was already built from, so routing through hybrid retrieval costs the
caller nothing it had.

**User-interface outcome.** The Recall backend card states that the setting
governs both the memories Raiker recalls on its own and the ones the assistant
looks up while it works. It could not honestly say that before.

**Evidence.** `tests/test_model_facing_memory_graph.py` — the first test asserts
the tool and the gatherer's own call return the same memories in the same order,
which is the property that was false.

---

## MEM-12 — The graph leg was gated on an anchor no caller ever supplied

**Severity: High. Area: retrieval quality. Status: fixed 2026-08-17.**

**Observed.** `retrieve_hybrid_memory` presents three legs. The graph leg is
inside `if entity_id:`, and the only production caller — the context gatherer —
calls it as `retrieve_hybrid_memory(store=…, query=…, limit=6,
owner_principal_id=…)`, with no `entity_id`. The leg never ran on a real turn.
The only caller that ever passed one was the evaluation harness, which is why
the strategy measured as working.

**Reproduce (before).** Approve a memory whose text shares no token with a
query, link it to an entity the query names, and search. Nothing returns: the
lexical leg cannot match, the hashing vector leg cannot match, and the graph leg
is skipped.

**Root cause.** The signature required knowledge the caller does not have. A
turn has the owner's words; it does not have an `entity_id`. Nothing resolved
one from the other, so the parameter was unfillable in practice.

**Fix.** Anchors are resolved from the query. `match_memory_entities` matches
whole normalized terms — and whole multi-word names inside the query — against
`memory_entities.normalized_name`, using the same case-folding and whitespace
collapse `upsert_memory_entity` applies. An explicit `entity_id` still wins,
because a caller that names one is asking about that entity rather than about
the words.

Three deliberate bounds:

* **At most three anchors.** Each is a separate neighborhood query, and a query
  naming five entities is a broad question the lexical leg answers better.
* **Whole-term matching, never substring.** `LIKE '%nas%'` would anchor on
  "nasty business", and a traversal seeded from a coincidence is worse than no
  traversal: it puts unrelated memories into a turn's context labelled
  "recalled". The containment check pads both sides with spaces so only a whole
  term can match. The first implementation got this wrong and a test caught it.
* **`max`, not sum, when two anchors reach one memory.** Two paths to one fact
  are one fact. Summing would let a densely connected entity outrank an exact
  lexical hit on nothing more than how many edges point at it.

**Evidence.** `tests/test_model_facing_memory_graph.py` — including the case
this entry describes: an evidence memory sharing **no token** with the query,
reachable only by traversal, returned with `sources == ("graph",)`.

**2026-08-21 follow-through.** MEM-06 now populates this leg through reviewed,
evidence-bound proposals. The max-not-sum rule remains unchanged: accepted graph
topology can make evidence reachable, never multiply the weight of one fact.

---

## MEM-13 — The knowledge graph was drawn for a person and unreachable from a turn

**Severity: Medium. Area: agent reach. Status: fixed 2026-08-17.**

**Observed.** Raiker stores a governed knowledge graph: entities, typed
relationships, and the approved memory that evidences each edge. It was rendered
on the Knowledge Map page for a person to look at, and consumed internally by
the graph leg of retrieval. No model-exposed tool could traverse it. A turn
could search memory and never ask *what is related to this, and how*.

**Reproduce (before).** Ask a Chat or Build turn what a stored entity is related
to. The model can only find memories whose text mentions it; the relationships
are invisible.

**Root cause.** `brain_view` is a dashboard method serving the web UI, and the
graph tables had no tool wrapper. The capability `graph_indexing_runtime`
governed *building* the graph and nothing read it on the model's behalf.

**Fix.** `knowledge_graph`, gated on the same `graph_indexing_runtime` so one
owner switch covers reading and writing. Two actions, because they answer two
questions: `entities` discovers by name and returns ids; `neighbors` walks one
entity's relationships and accepts a name to resolve, so the model needs no
protocol. Bounded at 25 entities and 50 edges — a graph read is a context
contribution, not a report.

Every edge carries the **approved memory that evidences it**, its confidence and
its direction. That is the governance property worth stating: a claim reached
through the graph is traceable to a sentence the owner approved rather than
asserted from a topology, and archiving that memory removes the edge. Without
it the graph would be a back door around memory governance — a forgotten fact
still readable through its shape.

**Deliberately not built.** The Knowledge Map *page* stays a human surface. It
visualises sessions, tasks, approvals, memories and backups, all of which the
model already reaches through other tools; a second path to the same facts is
exactly what MEM-11 was.

**User-interface outcome.** None required — this is an agent-facing capability,
and its results appear in the transcript under the memory tool family like any
other recalled material, labelled untrusted.

**Evidence.** `tests/test_model_facing_memory_graph.py` — the discover-then-walk
sequence, name resolution, and the test that archiving the evidence removes the
edge.

---

## MEM-14 — The citation ledger could only be read forwards

**Severity: Medium. Area: agent reach. Status: fixed 2026-08-17.**

**Observed.** MEM-13 gave a model a graph of **claims**. A model working in an
unfamiliar workspace also needs the graph of **material**: which work used which
source, what was used beside it, and what that source said at the time. Raiker
recorded all three and read none of them back.

`turn_sources` holds one row per source a turn used — the target's `locator`,
the tool that fetched it, and `passage`, the bounded text that really reached
the model. It was read in exactly one direction, `load_turn_sources(session_id,
…)`, for the citation chips under a single answer.

**Reproduce (before).** In a workspace with a dozen conversations behind it, ask
a turn what other work has touched `docs/runbook.md` and what it said. Every
available path re-reads the file from disk. The earlier conversations are
unreachable, and so is the version of the passage those conversations saw.

**Root cause.** No missing data and no bug — a table read from one end. Every
fact was stored, indexed only by the turn that wrote it, so reading by target
meant a full scan and nobody had written the read.

**Reference model.** `obsidianmd/obsidian-developer-docs`, reviewed at the
owner's suggestion. Obsidian's `MetadataCache` names the reading Raiker was not
doing: `resolvedLinks` as *source → target → count*, `unresolvedLinks` as its
equally first-class other half, `getBacklinksForFile()` for the inverse, and
block references that resolve to a paragraph rather than a document. Three
properties were taken deliberately — a link carries a count, an unresolved link
is reported rather than dropped, and a reference resolves to text.

**Fix.** Four owner-scoped reads (`list_source_backlinks`,
`list_source_outlinks`, `list_co_cited_sources`, `list_source_passages`), a
`(locator, principal_id)` index, and two `knowledge_graph` actions over them:
`references`, anchored on a locator or a session, and `passages`. Each target is
marked `resolved`, `unresolved`, `external` or `attachment` — four states, not
two, because calling a web page unresolved for not being on this disk would be a
claim about the internet.

**Deliberately not built.** Co-citation edges are **not** fed into retrieval
scoring. They say some work needed both of two things, which is far weaker than
an authored link, and letting that reorder a search would put topology above
evidence — the failure MEM-12's `max`-not-sum rule already exists to prevent.

**User-interface outcome.** The Knowledge Map draws the unresolved half. A cited
file that no longer exists renders hollow with a dashed outline, reads
**Missing** in the inspector, and is searchable as `status:missing`; it used to
be indistinguishable from a file still on disk.

**Evidence.** `tests/test_reference_graph.py`, including the cross-account
passage read — the one case here that would be a disclosure rather than a wrong
answer — and the unresolved-citation case in
`tests/test_knowledge_map_graph.py`.


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
