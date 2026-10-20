# RAIKER SQLCipher memory decision

## Status

**Accepted architecture and delivery contract.** This document consolidates the
SQLCipher storage posture with the product-memory rules. It is grounded in the
current implementation and its focused tests; it does not claim work that is
not present.

Raiker is a personal autonomous agent. Its memory is useful only when the owner
can understand, govern, correct, export and remove it. Memory is context, never
authority: a recalled record cannot enable a capability, approve an action,
change policy, or instruct the runtime to take an effect.

## Decision

Raiker will keep **SQLCipher-encrypted SQLite as the local, authoritative
memory store**. Human-readable exports, vector indexes, graph indexes, and any
future external memory service are derived views or adapters, never a second
authority.

Durable memory follows this path:

```text
event / owner input / imported source
  -> observation metadata or memory proposal
  -> owner review
  -> approved encrypted durable record
  -> policy-filtered lexical / semantic / graph recall
  -> provenance-labelled context
```

The owner may directly write a memory, but model-inferred memories and
relationships remain proposals until approved. Secret-like and credential-like
content is denied before a durable-memory approval is created.

## What is already implemented

| Area | Current Raiker evidence |
|---|---|
| At-rest database encryption | The storage layer uses `sqlcipher3`; the memory database does not have the plaintext SQLite header and a standard SQLite connection cannot read approved-memory records. |
| Search within the encrypted store | The shipped SQLCipher build is verified to provide FTS5; the encrypted `approved_memory_fts` projection is rebuilt from authoritative memory records. |
| Ownership and policy | Memory rows and vector/file-chunk reads are owner-scoped. Retrieval filters deleted, archived, superseded, expired, disabled-search and secret/credential-like records before returning content. |
| Write governance | `/memory-store` and `/memory-forget` are brokered approval-required requests. Durable writes emit audit events. |
| Lifecycle | Archive/restore, forget tombstones, exact-ID human-confirmed purge, derived-index reconciliation and backup-disposition recording are specified and implemented as owner-started operations. |
| Recall transparency | The Memory UI distinguishes observations, proposals, approved records, recalled records and archived/expired state; recalled content carries provenance and is not presented as an instruction. |
| Key-page handling | SQLCipher `cipher_memory_security` is set explicitly on every keyed connection. Raiker bounds keyed connection caching globally and reports the requested and in-force posture. |

### Important precision

SQLCipher database encryption and `PRAGMA cipher_memory_security` are
different protections.

- **Database encryption** protects the database contents at rest.
- **Memory security** asks SQLCipher to lock/wipe pages containing key material.
  It has a substantial measured cost and can exhaust the host's locked-memory
  allowance, causing a store-open failure.

The latter is therefore owner-configurable through
`RAIKER_SQLCIPHER_MEMORY_SECURITY`. Auto mode enables it only after a
disposable child-process probe succeeds; an explicit `on` request fails
closed if the host cannot honour it. Because the underlying pragma can latch
on for the life of a process, health must report the actual in-force state, not
only the requested setting. Changing this posture requires a process restart.

## Comparative findings and Raiker response

A reference personal-agent implementation uses two very small Markdown memories
injected as a frozen session-start snapshot, automatically persists its
conversation history in SQLite FTS5, and offers an optional external memory
provider ecosystem. Its useful design lessons are adopted below without
weakening Raiker's security model.

| Finding | Raiker decision |
|---|---|
| A compact, always-present memory layer makes durable preferences reliably available without searching every time. | Add a **bounded Memory Brief** to context assembly: owner-approved, high-confidence, active records only; deterministic priority; source IDs and a strict token budget. It is a projection of encrypted records, not a free-form file or a second store. |
| Session search solves “we discussed this before” better than stuffing old conversation into prompt memory. | Keep transcripts/session history distinct from durable memory. Provide owner-scoped, policy-filtered history search and bounded source windows. Search results must remain labelled untrusted context and must not silently promote themselves to memory. |
| Automatic background learning is convenient but can preserve a mistaken preference. | Retain Raiker's **proposal and owner-approval default**. Background analysis may prepare a candidate and explain why, but may not write an approved memory or alter a relationship without the owner decision. |
| Configurable recall avoids every memory being injected on every turn. | Expose three explicit per-workspace modes: **Off** (no ambient recall), **Brief only** (bounded approved Memory Brief), and **Search when relevant** (Brief plus governed retrieval). Incognito overrides all ambient recall; direct owner-requested inspection remains available. |
| External memory providers can add semantic capability but introduce data-egress, provenance and deletion problems. | Do not add a generic provider as a direct memory authority. A future `MemoryAdapter` must be disabled by default, use an explicit outbound data classification/approval, carry stable source IDs and deletion receipts, preserve owner and project scope, and never receive a full transcript or tool output by default. Local SQLCipher remains the source of truth. |
| Multiple agent profiles must not accidentally share mutable memory. | Every reader and writer must require owner identity and explicit scope. Separate profiles/workspaces receive separate stores or explicit, owner-approved shared-memory records; no implicit cross-profile merge or concurrent uncoordinated writer model is allowed. |
| Fixed capacity forces intentional curation. | Apply capacity/budget limits to the **Memory Brief** and retrieval context, not to the encrypted archive. The archive retains lifecycle controls; selection/ranking keeps prompts bounded without silently dropping stored history. |

## Required delivery items

1. **MEM-BRIEF-01 — bounded brief projection.** Implement a versioned
   `memory_brief` builder that selects only approved, active, permitted
   records. It must attach `memory_id`, provenance, trust label, freshness and
   truncation reason for every item.

2. **MEM-MODE-02 — explicit recall mode.** Persist the owner-selected
   `off | brief | search_when_relevant` setting. Incognito wins over this
   setting. UI copy must say exactly which mode and retrieval backend were used
   for the current turn.

3. **MEM-HISTORY-03 — session-history search boundary.** Verify/implement
   owner-scoped FTS search with deterministic windows, result budgets,
   sensitivity filtering and no automatic durable promotion. Do not use a
   history hit as authority.

4. **MEM-ADAPTER-04 — adapter contract, not provider integration.** Define the
   interface and threat model before integrating any provider. The contract
   requires opt-in egress, field-level classification/redaction, local
   provenance mapping, scope propagation, availability degradation to local
   recall, export/forget/purge reconciliation, pinned versions and audit
   events. No provider is enabled by this decision.

5. **MEM-KEY-05 — key and recovery runbook.** Document the database-key source,
   rotation/restore procedure, encrypted-backup verification, machine-loss
   recovery boundary, and how the `cipher_memory_security` health posture is
   diagnosed. A key must never be stored in the memory database, logs, exports
   or an external adapter payload.

6. **MEM-EVAL-06 — repeatable recall evaluation.** Maintain a small,
   synthetic, non-sensitive corpus covering preference recall, stale fact
   correction, contradictory memories, forgotten-memory non-resurrection,
   prompt-injection content, owner/project isolation, Incognito and
   retrieval-budget truncation. Score precision, provenance completeness and
   unsafe-recall rate; do not use production memories as the corpus.

## Acceptance evidence

No delivery item is complete without all applicable proof:

- encrypted-store and plaintext-open rejection tests;
- fresh-install and legacy plaintext migration tests proving no plaintext backup
  remains;
- owner/project/sensitivity/incognito filtering before ranking, including
  lexical, vector, graph and history paths;
- a test that a recalled memory cannot grant authority or override policy;
- candidate/reject/approve/edit/forget/purge audit and UI tests;
- Memory Brief ordering, budget, provenance and `off`/Incognito tests;
- adapter egress-denial, redaction, outage and deletion-reconciliation tests
  before any adapter ships;
- SQLCipher memory-security probe, connection-ceiling and health-posture tests;
- user-guide update in the same change as any memory behaviour change.

## Non-goals

This decision does not introduce automatic “remember everything” capture,
unbounded prompt injection, a cloud sync service, a shared multi-user memory
service, or an external provider. It also does not treat encrypted storage as a
substitute for memory governance, provenance, retention or owner control.

## Sources reviewed

- Raiker: `raiker/storage/sqlite.py`,
  `raiker/storage/stores/memory.py`,
  `raiker/storage/sqlcipher_probe.py`,
  `tests/test_memory_sqlcipher.py`,
  `tests/test_sqlcipher_memory_security.py`,
  `docs/architecture/MEMORY_AND_CONTEXT_STRATEGY.md`, and
  `docs/architecture/HYBRID_MEMORY_IMPLEMENTATION_PLAN.md`.
- Reference-agent: public persistent-memory and memory-provider documentation,
  reviewed 20 October 2026.

