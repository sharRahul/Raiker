# Threat model — external memory adapter contract (`MemoryAdapter`)

**No adapter ships and none is enabled.** This document is the precondition the
[SQLCipher memory decision](../architecture/MEMORY_AND_CONTEXT_STRATEGY.md#sqlcipher-memory-decision)
requires before any external memory provider is integrated. The contract it
reviews is code today — `raiker/memory/adapter.py` — so a future integration
inherits the controls instead of re-arguing them.

Local SQLCipher-encrypted memory stays the source of truth. An adapter is a
derived view: it may help find a record Raiker already holds, and nothing more.

## What the contract does

| Step | Function | Behaviour |
|---|---|---|
| Decide what may leave | `prepare_adapter_payload` | Refuses everything unless the owner's `MemoryAdapterPolicy` is enabled and names an adapter; then sends only approved, active, owner-held records in an allowed scope and sensitivity class, redacted, with only the fields in `ADAPTER_PAYLOAD_FIELDS` |
| Ask for recall | `query_with_local_fallback` | Checks the pinned version, bounds the limit, keeps only returned ids that were sent, and answers with the local result on any fault (`degraded`) |
| Forward a forget or purge | `reconcile_deletions` | Confirms a deletion only on an explicit `{"memory_id", "deleted": true}` receipt for an id that was asked about; everything else stays `pending` and is reported |
| Record what happened | `AdapterAudit` | Operation, adapter, version, owner reference, ids and refusal counts — never memory text |

## Assets

| Asset | Why it matters |
|---|---|
| Approved memory text | Personal facts the owner approved for local recall, not for a third party |
| Owner and scope | What stops one account's or one project's memory reaching another |
| Deletion state | "Forgotten" has to mean forgotten everywhere a copy went |
| The workspace key | Derives the database key; must never leave in any form |

## Trust boundaries

1. **Encrypted store → adapter payload.** The only crossing. Everything else in
   Raiker (transcripts, tool output, files, provenance) stays on the local side.
2. **Adapter answer → recall.** The answer is untrusted input. It can reorder or
   omit records Raiker sent; it cannot add one.
3. **Adapter receipts → deletion state.** A receipt is a claim to verify, not a
   fact.

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| An adapter is enabled by default or by a model | `MemoryAdapterPolicy()` is disabled; a disabled policy refuses before any record is read; no route, tool or setting builds an enabled one | `raiker/memory/adapter.py` |
| A credential or secret leaves the machine | Secret- and credential-like records are refused whatever the policy allows, and the text is re-classified so a stale label cannot lower it; remaining text is redacted | `prepare_adapter_payload`, `raiker/memory/policy.py`, `raiker/context/redaction.py` |
| A whole transcript or tool output is sent "for context" | The payload carries exactly six fields; no transcript, tool output, file chunk or provenance block is among them | `ADAPTER_PAYLOAD_FIELDS` |
| Another owner's or another project's memory is sent | Each record must match the owner and an explicitly allowed scope; the owner and scope travel with every item and query | `prepare_adapter_payload`, `query_with_local_fallback` |
| The adapter returns a memory Raiker does not hold (poisoning) | Returned ids outside the set that was sent are dropped | `query_with_local_fallback` |
| An adapter outage breaks or widens recall | Any exception or malformed answer returns the local result, labelled `degraded` | `query_with_local_fallback` |
| An updated adapter changes behaviour silently | The reported version must equal the pinned one, or the call degrades / deletion stays pending | `_check_version` |
| A forgotten memory survives at the provider | Deletion is confirmed only by an explicit receipt; anything else is `pending` and reported | `reconcile_deletions` |
| Audit records become a second copy of memory | The audit holds ids and counts only | `AdapterAudit` |
| The key is sent | Payload items are built from record fields only; the test suite checks the key appears in no payload | `tests/test_memory_key_never_leaves.py` |

## Residual risk, stated plainly

- **Text that passes is still text.** A public or personal sentence the owner
  allowed out is readable by the provider. The contract narrows what leaves; it
  cannot make what leaves private.
- **Classification is a fixed pattern set.** The same limit as
  [durable memory write](memory-write.md): a secret in an unrecognised shape is
  treated as ordinary text, which is why secret-like and credential-like refusal
  is joined by redaction and by the owner choosing scopes and classes.
- **A receipt can lie.** An adapter that says `deleted: true` and keeps the copy
  cannot be caught from Raiker's side. The contract records the claim and its
  time; it does not prove erasure.
- **No integration exists to audit.** Rate limits, provider authentication,
  regional storage and retention terms belong to a specific provider's review,
  which must extend this document before that provider is enabled.

## Evidence

- `raiker/memory/adapter.py`
- `tests/test_memory_adapter_contract.py` — egress denial, redaction, outage,
  pinned version, id introduction and deletion reconciliation
- `tests/test_memory_key_never_leaves.py`
