# Threat model — durable memory forget (`memory_forget_execution`)

`memory_forget_execution` is the capability behind the `memory_forget` tool. Like
its sibling it is in
[`EXECUTABLE_ON_APPROVAL`](../../raiker/approvals/execution.py), so **approving a
forget really removes the record**. The gate ships **off**.

Forgetting is the recovery path for
[`memory-write.md`](memory-write.md), which is precisely why it needs its own
analysis: a capability that deletes the owner's records is not made safe by the
fact that its sibling creates them.

## What the capability does

`raiker/runtime/executors/tier1_memory.py` → `MemoryForgetExecutor` calls
`raiker.memory.store.forget_memory`, which:

- rewrites the entry file as a **tombstone** — frontmatter retained, `text`
  emptied, `approval_state` set to `forgotten`, `deleted_at` stamped;
- marks the approved-memory row forgotten in the encrypted store; and
- deactivates that memory's projections, which is what removes the graph edges it
  evidenced.

It is a redaction rather than a shred: the provenance of *what was removed and
when* survives, and the content does not.

## Assets

| Asset | Why it matters |
|---|---|
| The owner's accumulated memory | Deleting the wrong one silently degrades every later turn |
| The tombstone | It is the audit record that a removal happened at all |
| Graph edges evidenced by the memory | They must not outlive the evidence that justified them |

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| The agent quietly clears the owner's memory | The gate ships off; with it on, the default decision mode is `ask`, and the approval preview resolves and shows **the record that would go** rather than only its id | `raiker/tools/broker.py` |
| A model names another account's memory id | `forget_memory` compares the entry's stored `owner_principal_id` against the acting principal's account scope and returns "not found" on mismatch — an id from another account is indistinguishable from a nonexistent one | `raiker/memory/store.py` |
| An ungoverned code path deletes a memory | `forget_memory` raises `memory_forget_requires_governed_path` when called without a `MemoryForgetGovernance` block — there is no convenience overload | `raiker/memory/store.py` |
| A stale graph edge keeps asserting a fact whose evidence is gone | `deactivate_memory_projections` runs in the same call | `raiker/memory/store.py` |
| The id drifts between approval and execution | Arguments-hash check in the relay | `tier1_approval.py` |
| One approval deletes several records | The tool takes exactly one `memory_id`; there is no bulk-forget tool and no wildcard | `raiker/models/tool_registry.py` |

## Residual risk, stated plainly

- **A forget is not reversible from the product.** The tombstone keeps the
  metadata; the sentence is gone. There is no undo, and the checkpoint store
  holds pre-images for *workspace files*, not for memory rows.
- **Fallback lookup scans the memory directory.** When the entry is not at its
  expected path, `forget_memory` scans `*.md` for one containing the id in its
  frontmatter. The match requires the exact `"memory_id": "<id>"` frontmatter
  form, so a mention of the id in a memory's *body* does not select it — but the
  scan does read every entry file in the directory to find one.
- **Archiving and forgetting are different operations.** `set_memory_archived`
  hides a record from recall without tombstoning it. Only `forget` removes the
  text.

## Evidence

- `raiker/runtime/executors/tier1_memory.py`, `raiker/memory/store.py`
- [`../MEMORY_GOVERNANCE_RULES.md`](../MEMORY_GOVERNANCE_RULES.md)
- [`approval-execution-relay.md`](approval-execution-relay.md)
