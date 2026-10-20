"""MEM-ADAPTER-04 — the contract an external memory adapter must satisfy.

**No provider is enabled here, and none ships.** This module is the interface
and the fail-closed preparation every future adapter call must go through, so
the decision's rules are code before any provider is integrated:

* **Disabled by default.** :class:`MemoryAdapterPolicy` starts disabled; a
  disabled policy refuses every payload before any record is read.
* **Opt-in egress, field by field.** Only approved, active, owner-held
  records in an allowed scope and an allowed sensitivity class leave, and only
  the fields named in :data:`ADAPTER_PAYLOAD_FIELDS`. Secret- and
  credential-like text never leaves, whatever the policy says.
* **Redaction.** Text that passes is still run through the context redactor.
* **Local provenance mapping.** Every payload item carries the local
  ``memory_id``; an adapter result that names an id the payload did not send is
  dropped, so an adapter can never introduce a memory Raiker does not hold.
* **Scope propagation.** The owner and scope travel with every item and every
  query; nothing is sent without both.
* **Degradation to local recall.** An adapter outage or malformed answer
  returns the local result, labelled ``degraded``; it never fails the turn and
  never widens recall.
* **Deletion reconciliation.** Forget and purge produce a deletion request per
  id, and the adapter's receipts are reconciled: an id without a confirmed
  receipt stays ``pending`` and is reported, never assumed gone.
* **Pinned versions and audit.** The policy names an exact adapter version; a
  different reported version refuses. Every prepare, query and deletion returns
  an audit record holding ids and counts — never memory text.

Local SQLCipher remains the source of truth: nothing an adapter returns is
written into the encrypted store by this module.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from raiker.context.redaction import redact_text
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity

MEMORY_ADAPTER_CONTRACT_VERSION = "memory-adapter-contract-v1"

#: The only fields that may leave the machine. A transcript, a tool output, a
#: file chunk or a provenance block is never among them.
ADAPTER_PAYLOAD_FIELDS = ("memory_id", "owner_ref", "scope", "text", "sensitivity", "updated_at")

_NEVER_EGRESS = {
    MemorySensitivity.SECRET_LIKE.value,
    MemorySensitivity.CREDENTIAL_LIKE.value,
}


class MemoryAdapterError(Exception):
    """An adapter refused, failed or answered outside the contract."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class MemoryAdapterPolicy:
    """The owner's explicit opt-in for one adapter. Disabled unless built otherwise."""

    adapter_id: str = ""
    pinned_version: str = ""
    enabled: bool = False
    #: Sensitivity classes the owner allowed out. Secret- and credential-like
    #: are refused even when listed here.
    allowed_sensitivity: frozenset[str] = frozenset({MemorySensitivity.PUBLIC.value})
    #: Scopes the owner allowed out. Empty means none.
    allowed_scopes: frozenset[str] = frozenset()
    max_items: int = 50


@dataclass(frozen=True)
class AdapterPayloadItem:
    memory_id: str
    owner_ref: str
    scope: str
    text: str
    sensitivity: str
    updated_at: str
    redacted: bool = False

    def wire(self) -> dict[str, str]:
        """Exactly :data:`ADAPTER_PAYLOAD_FIELDS`, nothing else."""
        return {name: str(getattr(self, name)) for name in ADAPTER_PAYLOAD_FIELDS}


@dataclass(frozen=True)
class AdapterAudit:
    """What an adapter operation did, as ids and counts. Never memory text."""

    operation: str
    adapter_id: str
    adapter_version: str
    owner_ref: str
    sent_ids: tuple[str, ...] = ()
    refused: dict[str, int] = field(default_factory=dict)
    outcome: str = "ok"


@dataclass(frozen=True)
class AdapterPayload:
    items: tuple[AdapterPayloadItem, ...]
    audit: AdapterAudit


@dataclass(frozen=True)
class AdapterRecallResult:
    memory_ids: tuple[str, ...]
    #: ``adapter`` when the adapter answered within the contract, ``degraded``
    #: when the local result was used instead.
    source: str
    audit: AdapterAudit


@dataclass(frozen=True)
class DeletionReconciliation:
    confirmed: tuple[str, ...]
    #: Ids the adapter has not confirmed deleting. Reported, never assumed gone.
    pending: tuple[str, ...]
    audit: AdapterAudit


@runtime_checkable
class MemoryAdapter(Protocol):
    """What an adapter implements. Every method receives only contract data."""

    adapter_id: str

    def version(self) -> str: ...

    def upsert(self, items: Sequence[dict[str, str]]) -> None: ...

    def query(self, *, owner_ref: str, scope: str, text: str, limit: int) -> Sequence[dict[str, Any]]: ...

    def delete(self, *, owner_ref: str, memory_ids: Sequence[str]) -> Sequence[dict[str, Any]]: ...


def _check_version(adapter: MemoryAdapter, policy: MemoryAdapterPolicy) -> str:
    reported = adapter.version()
    if not policy.pinned_version or reported != policy.pinned_version:
        raise MemoryAdapterError("adapter_version_not_pinned")
    return reported


def prepare_adapter_payload(
    records: Sequence[dict[str, Any]],
    *,
    owner_principal_id: str,
    policy: MemoryAdapterPolicy,
) -> AdapterPayload:
    """Decide, record by record, what may leave. Fail closed at every step."""
    if not policy.enabled or not policy.adapter_id:
        raise MemoryAdapterError("adapter_disabled")
    if not owner_principal_id:
        raise MemoryAdapterError("adapter_requires_owner")
    refused: dict[str, int] = {}

    def refuse(reason: str) -> None:
        refused[reason] = refused.get(reason, 0) + 1

    items: list[AdapterPayloadItem] = []
    for record in records:
        if len(items) >= policy.max_items:
            refuse("over_item_limit")
            continue
        if str(record.get("owner_principal_id") or "") != owner_principal_id:
            refuse("other_owner")
            continue
        if str(record.get("approval_state") or "") != "approved":
            refuse("not_approved")
            continue
        if record.get("deleted_at") or record.get("archived_at") or record.get("superseded_at"):
            refuse("inactive")
            continue
        scope = str(record.get("scope") or "")
        if not scope or scope not in policy.allowed_scopes:
            refuse("scope_not_allowed")
            continue
        text = " ".join(str(record.get("text") or "").split())
        labelled = str(record.get("sensitivity") or "")
        observed = classify_memory_sensitivity(text).value
        if labelled in _NEVER_EGRESS or observed in _NEVER_EGRESS:
            refuse("never_egress")
            continue
        # The label must be allowed, and the text must not read as a class the
        # owner did not allow (an email in a "public" record stays home).
        # Text the classifier cannot place adds no restriction of its own.
        readable = policy.allowed_sensitivity | {MemorySensitivity.UNKNOWN.value}
        if labelled not in policy.allowed_sensitivity or observed not in readable:
            refuse("sensitivity_not_allowed")
            continue
        clean, changed = redact_text(text)
        items.append(
            AdapterPayloadItem(
                memory_id=str(record["memory_id"]),
                owner_ref=owner_principal_id,
                scope=scope,
                text=clean,
                sensitivity=labelled,
                updated_at=str(record.get("updated_at") or record.get("created_at") or ""),
                redacted=changed,
            )
        )
    audit = AdapterAudit(
        operation="prepare",
        adapter_id=policy.adapter_id,
        adapter_version=policy.pinned_version,
        owner_ref=owner_principal_id,
        sent_ids=tuple(item.memory_id for item in items),
        refused=refused,
    )
    return AdapterPayload(items=tuple(items), audit=audit)


def query_with_local_fallback(
    adapter: MemoryAdapter,
    *,
    policy: MemoryAdapterPolicy,
    owner_principal_id: str,
    scope: str,
    text: str,
    local_ids: Sequence[str],
    known_ids: Sequence[str],
    limit: int = 10,
) -> AdapterRecallResult:
    """Ask the adapter; on any failure, answer with the local result.

    ``known_ids`` are the local ids that were sent to the adapter. A returned id
    outside that set is dropped: the adapter cannot introduce a memory.
    """

    def degraded(reason: str) -> AdapterRecallResult:
        return AdapterRecallResult(
            memory_ids=tuple(local_ids)[:limit],
            source="degraded",
            audit=AdapterAudit(
                operation="query",
                adapter_id=policy.adapter_id,
                adapter_version=policy.pinned_version,
                owner_ref=owner_principal_id,
                outcome=reason,
            ),
        )

    if not policy.enabled or not owner_principal_id or not scope:
        return degraded("adapter_disabled")
    if scope not in policy.allowed_scopes:
        return degraded("scope_not_allowed")
    try:
        _check_version(adapter, policy)
        answer = adapter.query(
            owner_ref=owner_principal_id, scope=scope, text=text, limit=max(1, min(limit, policy.max_items))
        )
    except MemoryAdapterError as exc:
        return degraded(exc.reason)
    except Exception:  # noqa: BLE001 - any adapter fault degrades to local recall
        return degraded("adapter_unavailable")
    allowed = set(known_ids)
    ids: list[str] = []
    for row in answer if isinstance(answer, (list, tuple)) else []:
        memory_id = str(row.get("memory_id") or "") if isinstance(row, dict) else ""
        if memory_id in allowed and memory_id not in ids:
            ids.append(memory_id)
    return AdapterRecallResult(
        memory_ids=tuple(ids[:limit]),
        source="adapter",
        audit=AdapterAudit(
            operation="query",
            adapter_id=policy.adapter_id,
            adapter_version=policy.pinned_version,
            owner_ref=owner_principal_id,
            sent_ids=tuple(ids[:limit]),
        ),
    )


def reconcile_deletions(
    adapter: MemoryAdapter,
    *,
    policy: MemoryAdapterPolicy,
    owner_principal_id: str,
    memory_ids: Sequence[str],
) -> DeletionReconciliation:
    """Forward a forget/purge and reconcile the receipts.

    Only an explicit ``{"memory_id": …, "deleted": True}`` receipt confirms a
    deletion. Anything else — an outage, a missing receipt, a receipt for an id
    that was not asked about — leaves the id ``pending``.
    """
    requested = tuple(dict.fromkeys(str(memory_id) for memory_id in memory_ids if memory_id))
    outcome = "ok"
    confirmed: list[str] = []
    try:
        _check_version(adapter, policy)
        receipts = adapter.delete(owner_ref=owner_principal_id, memory_ids=requested)
    except MemoryAdapterError as exc:
        receipts, outcome = [], exc.reason
    except Exception:  # noqa: BLE001 - an outage leaves every id pending
        receipts, outcome = [], "adapter_unavailable"
    asked = set(requested)
    for receipt in receipts if isinstance(receipts, (list, tuple)) else []:
        if not isinstance(receipt, dict):
            continue
        memory_id = str(receipt.get("memory_id") or "")
        if memory_id in asked and receipt.get("deleted") is True and memory_id not in confirmed:
            confirmed.append(memory_id)
    pending = tuple(memory_id for memory_id in requested if memory_id not in confirmed)
    if pending and outcome == "ok":
        outcome = "deletion_pending"
    return DeletionReconciliation(
        confirmed=tuple(confirmed),
        pending=pending,
        audit=AdapterAudit(
            operation="delete",
            adapter_id=policy.adapter_id,
            adapter_version=policy.pinned_version,
            owner_ref=owner_principal_id,
            sent_ids=requested,
            outcome=outcome,
        ),
    )
