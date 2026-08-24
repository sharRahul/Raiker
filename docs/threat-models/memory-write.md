# Threat model — durable memory write (`memory_write_execution`)

`memory_write_execution` is the capability behind the `memory_write` tool. It is
one of the twelve in
[`EXECUTABLE_ON_APPROVAL`](../../raiker/approvals/execution.py), so **approving a
memory write really stores the record** — this is not a decision-only approval.
The gate ships **off**.

Read this before opening the gate. The step-up asks you to acknowledge a threat
model; this is it.

## What the capability does

`raiker/runtime/executors/tier1_memory.py` → `MemoryWriteExecutor` calls
`raiker.memory.store.write_memory`, which writes:

- one Markdown entry with a frontmatter block under the workspace memory
  directory, and
- one row in the SQLCipher-encrypted approved-memory table, scoped to the
  acting principal's account (`store.account_scope(...)`).

The record carries provenance the owner can audit later: the originating event,
session and turn ids, a `source_type`, a confidence and trust score, a retention
class, an approval state, and `created_by`.

## Assets

| Asset | Why it matters |
|---|---|
| The stored sentence | It is injected into future turns as context, so it shapes answers indefinitely |
| The account scope on the row | It is what stops one instance's owner reading another's memory |
| The provenance block | It is the only record of *which turn* asked for this and on whose authority |

## Trust boundaries

1. **Model → tool broker.** The proposed text is untrusted model output. It
   crosses into governance at `ToolBroker`.
2. **Tool broker → owner.** The approval preview carries the exact text, under
   redaction (`_redact_value`), so the decision is about the sentence rather than
   about a tool name.
3. **Approval → executor.** `ApprovalExecutionRelay` re-routes the approved
   action through `RuntimeAuthority`, so the capability gate, the decision mode,
   the PolicyEngine review and the approving session's posture are all re-checked
   at execution time.

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| A credential or key is persisted into durable storage | `classify_memory_sensitivity` runs **before the owner is asked**; `credential_like` and `secret_like` text is refused outright, so approving a credential is never offered as a choice | `raiker/tools/broker.py`, `raiker/memory/policy.py` |
| Fetched page text or a channel message instructs the agent to "remember" an attacker's claim | The write is a proposal the owner reads in full before deciding; external content never carries instruction authority, and a memory it asks for is a visible sentence rather than a silent side effect | `raiker/runtime/web_access.py`, Approvals view |
| The text changes between the owner reading it and the write landing (TOCTOU) | The relay verifies the arguments hash captured in the immutable intent snapshot and refuses a payload that drifted | `raiker/runtime/executors/tier1_approval.py` |
| An approval is replayed to write the record twice | Atomic `pending → executing → executed` claim in SQLite; the loser of the race stops | `store.claim_approval_for_execution` |
| A revoked session's approval is still executed | Posture check (A4) denies with `posture_degraded` | `raiker/runtime/authority/posture.py` |
| A memory is written into another account's scope | `owner_principal_id` is resolved from the acting principal, never from a model argument | `MemoryWriteExecutor.execute` |
| Poisoned context accumulates unnoticed | Every record is listed, filterable and individually removable in **Memory**; `memory_forget` removes exactly the record shown | `raiker/api/routes_memory.py` |

## Residual risk, stated plainly

- **The executor does not re-classify sensitivity.** The credential/secret
  refusal lives on the proposal path (broker and `GovernedMemoryService`), not in
  `MemoryWriteExecutor`. What makes it binding for a relayed approval is the
  arguments-hash check, not a second classification. A future caller that reached
  the executor without passing the broker would not get the refusal.
- **Classification is a fixed pattern set, not a classifier.** `CREDENTIAL_PATTERNS`
  and `SECRET_PATTERNS` catch PEM blocks, bearer tokens, `password=`, `api_key=`
  shapes, credentials in URLs, and long opaque strings. A secret in an
  unrecognised shape is stored as ordinary text. This is deliberate: a
  probabilistic filter would read as an assurance it cannot give.
- **A stored sentence is trusted context thereafter.** Raiker does not re-verify
  an approved memory against the world. A memory that was true when approved and
  is false now stays in context until the owner forgets it.

## Recovery

`memory_forget` (see [`memory-forget.md`](memory-forget.md)) tombstones the exact
record and deactivates its projections and graph edges. The forget is itself
governed and audited.

## Evidence

- `raiker/runtime/executors/tier1_memory.py`, `raiker/memory/store.py`,
  `raiker/memory/policy.py`, `raiker/memory/governance.py`
- Rules the write must satisfy: [`../MEMORY_GOVERNANCE_RULES.md`](../architecture/MEMORY_GOVERNANCE_RULES.md)
- What recall can actually do with it: [`../plans/MEMORY_RELIABILITY_PLAN.md`](../plans/MEMORY_RELIABILITY_PLAN.md)
- The relay's own model: [`approval-execution-relay.md`](approval-execution-relay.md)
