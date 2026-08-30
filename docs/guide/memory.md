# How Raiker memory works

Raiker memory is an owner-governed way to carry useful facts between
conversations and tasks. It is separate from the transcript of a conversation:
a transcript records what was said, while durable memory contains only facts
that passed the memory review path.

Open **Knowledge → Memory** to review proposals, inspect approved memories,
control recall, and manage retention. Open **Knowledge → Knowledge Map** to see
approved relationships between governed records.

## The memory path

```text
conversation, tool result, or event
  → observation metadata
  → proposed memory or relationship
  → owner review
  → approved durable memory
  → policy-filtered recall with provenance
```

The stages deliberately have different authority:

- An **observation** records that Raiker encountered something. Current
  observations keep a checksum, source/provenance metadata, sensitivity, and a
  retention class—not a second hidden copy of the source material.
- A **proposal** is a review item. It does not enter normal recall or the
  Knowledge Map merely because the agent suggested it.
- An **approved memory** is eligible for recall. Eligibility still depends on
  scope, sensitivity, lifecycle state, Incognito, and the active retrieval
  budget.
- An **approved relationship** may appear in relationship recall and the
  Knowledge Map. A guessed link remains a proposal until you approve it.

## Reviewing what Raiker proposes

The **Pending review** section shows the proposed text, scope, sensitivity, and
why it was proposed. You can:

- **Approve** the proposal as written;
- **Edit & approve** to correct or narrow the durable fact before it enters
  recall; or
- **Reject** it so the proposal does not become memory.

Relationship review is separate. **Scan approved memories** can prepare
candidate links, but only **Approve relationship** makes a link eligible for
relationship retrieval. Rejection does not delete the underlying memories.

Approval is not a blanket instruction to the agent. Recalled text is supplied
as labelled evidence and cannot increase permissions, replace the current
prompt, or bypass an approval gate.

## What enters a turn

Raiker builds context in layers. The current prompt, task, conversation history,
and explicit project context come first. It then retrieves eligible approved
memory within a bounded budget. Policy filtering happens before ranking, so a
high-scoring record cannot bypass scope or privacy rules.

Recall can happen in two ways:

1. Raiker automatically attaches a small number of relevant, approved memories
   while assembling a turn.
2. The assistant can use governed memory or conversation-recall tools when the
   task needs a more explicit search.

Both paths use the same eligibility rules. A recalled result carries source and
trust information so the answer can say where it came from. Use **View source**
on a memory, or inspect the source chips on a reply, to check the evidence.

The first path leaves nothing to click, because it is not a tool call — so a
settled answer in Chat carries a collapsed **Remembered *n*** strip naming the
memories that turn was actually given. **Correct** and **Forget** on a row are
the same governed actions this page offers; the strip adds no authority. The
sentences are read live, so a memory corrected since the turn ran reads as it is
now, and a forgotten one stops appearing. An answer that used no memory shows no
strip.

Conversation recall is related but distinct. It searches completed exchanges
from your earlier conversations. Durable memory searches approved facts. Raiker
labels the source so an old message is treated as historical data, not as a new
instruction. See [Working in Chat](working-in-chat.md#recalling-an-older-conversation).

## Scope, privacy, and sensitivity

Memory is filtered before ranking:

- Project memory can be **enabled**, **disabled**, or inherited from the nearest
  parent project with an explicit setting. A sibling project does not inherit
  another sibling's memory.
- Archived, forgotten, expired, out-of-scope, or policy-withheld records do not
  enter normal retrieval.
- Sensitivity rules can withhold a memory even when its words match perfectly.
- **Incognito session** disables approved-memory and cross-conversation recall
  for new conversations and tasks. It does not delete stored records.
- Secret-like and credential-like memories are never sent to an embedding
  provider when building an index.

The model has no permanent-purge tool. A model may help identify a target or
prepare a preview, but only a human can confirm permanent deletion.

## Recall backend and token budget

The default lexical fallback, `raiker-local-hash-v1`, works offline and matches shared
words. It is lexical rather than meaning-based, so paraphrases may not match.

**Build a meaning-based index** can create provider- or local-model embeddings
for approved, non-sensitive memories. This is a governed write operation: the
confirmation names the destination and number of memories before text leaves
the machine. Re-running it indexes only eligible approved memories not already
represented in that space.

Current boundary: storing learned vectors is implemented, but embedding every
new question against that provider space is not yet connected. Until that read
path has its own governed permission, the Memory page states that recall still
matches words. Raiker does not claim semantic recall when only the stored side
of the index exists.

Every retrieval caller supplies a budget. The current assembler limits how much
memory reaches a prompt and preserves provenance labels. Post-Stage-J work will
add a shared `RetrievalBudget`, deterministic graph ranking/truncation, and a
versioned graph-to-prompt serialization format; these are plans, not current
product claims.

## Correcting and controlling an approved memory

Each approved memory provides owner controls:

- **View source** opens the evidence attached to the record.
- **Edit** creates the governed correction history instead of silently changing
  what was previously used.
- **Edit scope** changes where the memory may be considered.
- **Review expiry** changes its lifecycle timing through the governed control.
- **Pin / Unpin** marks owner importance; it does not override privacy filters.
- **View history** shows corrections and lifecycle decisions.
- **Forget** removes the memory from every retrieval path and leaves a tombstone
  so projections can be reconciled safely.
- **Delete permanently** is the advanced, human-confirmed purge path.

If a fact changes, edit/correct it rather than adding a contradictory duplicate.
Corrections and supersession links let retrieval prefer the valid record while
preserving an auditable history.

## Archive, forget, and purge

These actions are intentionally different:

| Action | Recall | Stored state | Reversible |
|---|---|---|---|
| Archive | Excluded from normal active recall | Record and evidence retained | Yes, by restore |
| Forget | Excluded from all recall | Tombstone and purge work retained | Not as ordinary active memory |
| Purge | Unavailable | Primary data and projections removed; disposition recorded | No |

Purge is not a plain row deletion. Its preview and exact-target confirmation
cover the primary record, text index, vectors, graph edges, artifacts, exports,
and known backups. A completed purge can still report a backup as pending its
own retention/erasure process; Raiker must not claim that copy vanished early.

## Exporting and importing

**Memory → Advanced memory management** exports every approved memory as JSON and
takes one back.

An import is not a second way into the store: each record goes through the same
governed write path a proposal does, and is recorded as a lifecycle event with
`source: user_import`. What it will not do is store the same sentence twice.
Choosing a file asks the workspace what it already holds and says so before
anything is written — *"1 new of 4 · 3 already stored, and will be skipped"* —
and the button names what it is about to do. Afterwards the notice reports what
actually changed, not how many records the file had.

Two details worth knowing:

- **Scope is part of the comparison.** The same sentence at project scope and at
  global scope is two records, and importing the second is not a duplicate.
- **The skip is a default, not a rule.** The review step names the record a
  duplicate would copy, and **Import anyway** stores the second copy when that
  is what you meant.

A memory you have forgotten is gone, so re-importing it is how you bring it
back — it does not count as something the workspace already holds.

## Retention and observations

Observation retention classes are visible under **Observations**:

| Class | Intended lifetime |
|---|---|
| `turn_only` | This turn |
| `short_term_7_days` | Seven days |
| `short_term_30_days` | Thirty days |
| `project_lifetime` | While the project is retained |
| `until_forget` | Until you forget or purge it |
| `legal_hold` | No automatic expiry |

Raiker currently runs no unattended cleanup daemon. The Observations view shows
what is past retention and lets the owner run cleanup explicitly. The result
reports exactly what was removed.

## Future architecture after Stage J

The [hybrid memory implementation plan](../architecture/HYBRID_MEMORY_IMPLEMENTATION_PLAN.md#future-improvements--post-stage-j-expansion)
defines four later tracks:

- hot (0–90 day epimemory), warm semantic generalizations, and cold core/ADR
  history with lifecycle propagation across every tier;
- cross-language linker rules and evidence-labelled polymorphic resolution;
- deterministic ranking, truncation, and serialization under token budgets; and
- snapshot-isolated indexing with atomic generation swaps and rollback.

These tracks do not weaken approval, provenance, correction, scope, sensitivity,
forget, or purge rules. They are future improvements until their acceptance
evidence is complete.

## Checking the indexes

Memory keeps rebuildable indexes and projections beside the records that own the
content — a text index over approved memory, one over your conversations, vector
projections, and graph edges. A divergence between a record and its index has no
symptom you would notice: search simply stops finding something it found last
week.

**Observability → Diagnostics → Memory integrity** compares each one against the
table that owns it. It reports `clean`, or names only the findings that are not
zero, and **Rescan** runs it again on request — nothing sweeps in the background.
When the conversation index has drifted, and only then, the card offers **Rebuild
conversation index**: that index is a projection of your turns, so rebuilding it
recomputes every row and can lose nothing.

## Maintenance contract

This guide is part of the memory feature, not a one-time explanation. Any change
to memory capture, candidate approval, automatic or tool-driven retrieval,
ranking, correction, retention, temporal tiering, archive, forget, purge,
projection behavior, scope, sensitivity, Incognito, or privacy must update this
file in the same change.
