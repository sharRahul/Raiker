"""Raiker remembers on its own; the owner undoes, rather than approves.

Every proposal used to wait for **Keep**. That made memory a chore: most
proposals were the owner's own words, and a review queue nobody reads is a
review queue that protects nothing. ChatGPT updates memory itself and says so
("Memory updated"); Cursor and Claude Code keep project memory the same way.
Raiker now does too, with the owner in charge through *visibility and undo*
instead of a click per fact:

* **Kept without asking:** the owner's own words, owner corrections, and
  lessons backed by the task's own records.
* **Still asked:** anything the model wrote (it may be invented, FIXED-1548),
  personal identifiers (email, phone, address), and a lesson that would change
  a project's declared check, and text that reads like an instruction to the
  agent or hides invisible characters — the "almost" in almost zero approvals.
* **Never kept:** secret- or credential-like text, and anything in Incognito or
  with memory off (the gateway files no proposal at all there).
* A proposal that repeats a memory Raiker already has is closed, not kept twice.

An owner who wants the old behaviour turns on *Ask before remembering*.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.storage.sqlite import SQLiteStore

#: Proposal sources whose words are trusted enough to keep without asking.
#: `vault_note` is a line added to the memory vault's Inbox: the owner's vault,
#: written by the owner or by an agent working for them, and still scanned.
AUTO_KEEP_ROLES = frozenset({"user", "owner_correction", "raiker_lesson", "vault_note"})
_ASK_SENSITIVITIES = frozenset({MemorySensitivity.PERSONAL})
_NEVER_SENSITIVITIES = frozenset({MemorySensitivity.SECRET_LIKE, MemorySensitivity.CREDENTIAL_LIKE})
AUTO_KEEP_REASON = "auto_kept"
DUPLICATE_REASON = "already_remembered"


@dataclass(frozen=True)
class AutoKeepSummary:
    kept: tuple[str, ...] = ()
    duplicates: int = 0
    asked: int = 0


def auto_keep_decision(candidate: dict[str, Any], *, asks_first: bool) -> str:
    """``keep``, ``ask`` or ``never`` for one deferred proposal."""
    sensitivity = classify_memory_sensitivity(str(candidate.get("text") or ""))
    if sensitivity in _NEVER_SENSITIVITIES:
        return "never"
    if asks_first or sensitivity in _ASK_SENSITIVITIES:
        return "ask"
    from raiker.security.injection_scan import scan_untrusted_text

    if scan_untrusted_text(str(candidate.get("text") or "")):
        # Hermes Agent blocks memory writes that read like an injection or carry
        # invisible characters. A kept memory reaches every later turn, so text
        # that reads like an instruction to the agent waits for the owner.
        return "ask"
    if str(candidate.get("memory_type") or "") == "check_fix":
        # Keep changes the project's declared checks: a settings change, asked.
        return "ask"
    return "keep" if str(candidate.get("source_role") or "") in AUTO_KEEP_ROLES else "ask"


def auto_keep_turn(
    store: SQLiteStore,
    *,
    workspace_root: str | Path,
    owner_principal_id: str,
    session_id: str,
    turn_id: str,
) -> AutoKeepSummary:
    """Keep this turn's trusted proposals now; leave the rest for the owner."""
    from raiker.memory.near_duplicate import nearest_approved
    from raiker.memory.store import MemoryGovernance, write_memory

    asks_first = store.asks_before_remembering(owner_principal_id)
    pending = [
        row
        for row in store.list_memory_candidates(decision="deferred", owner_principal_id=owner_principal_id)
        if row.get("source_turn_id") == turn_id
    ]
    if not pending:
        return AutoKeepSummary()
    approved = store.list_approved_memory(
        limit=2_000, include_search_disabled=True, owner_principal_id=owner_principal_id
    )
    kept: list[str] = []
    duplicates = asked = 0
    for row in pending:
        decision = auto_keep_decision(row, asks_first=asks_first)
        if decision != "keep":
            asked += int(decision == "ask")
            continue
        text = str(row.get("text") or "").strip()
        candidate_id = str(row["candidate_id"])
        if nearest_approved(text, approved) is not None:
            if store.resolve_memory_candidate(
                candidate_id,
                owner_principal_id=owner_principal_id,
                expected_decision="deferred",
                decision="rejected",
                reason=DUPLICATE_REASON,
                resolved_at=utc_now(),
            ):
                duplicates += 1
            continue
        if not store.resolve_memory_candidate(
            candidate_id,
            owner_principal_id=owner_principal_id,
            expected_decision="deferred",
            decision="approved",
            reason=AUTO_KEEP_REASON,
            resolved_at=utc_now(),
        ):
            continue
        entry = write_memory(
            text,
            workspace_root=workspace_root,
            scope=str(row.get("scope") or "project"),
            memory_type=str(row.get("memory_type") or "project"),
            source="auto_remembered",
            store=store,
            owner_principal_id=owner_principal_id,
            governance=MemoryGovernance(
                source_event_id=str(row.get("source_event_id") or ""),
                source_session_id=session_id,
                source_turn_id=turn_id,
                source_type="memory_proposal",
                confidence=float(row.get("confidence") or 0.8),
                trust_score=0.8,
                retention="until_forget",
                # Kept by the owner's standing choice, not a click: the summary
                # and recall treat it as approved; the record says how.
                approval_state="policy_allowed",
                created_by=owner_principal_id,
            ),
        )
        store.record_memory_lifecycle_event(
            entry.memory_id,
            "approve",
            owner_principal_id,
            {
                "auto": True,
                "candidate_id": candidate_id,
                "source_session_id": session_id,
                "source_turn_id": turn_id,
            },
        )
        approved.append({"memory_id": entry.memory_id, "text": text})
        kept.append(entry.memory_id)
    return AutoKeepSummary(kept=tuple(kept), duplicates=duplicates, asked=asked)


def remembered_in_session(
    store: SQLiteStore, *, workspace_root: str | Path, owner_principal_id: str, session_id: str
) -> list[dict[str, str]]:
    """What Raiker kept on its own in one conversation and still holds, for Undo."""
    from raiker.memory.store import get_memory

    with store.connect() as connection:
        rows = connection.execute(
            """SELECT a.memory_id, json_extract(a.details_json, '$.source_turn_id') AS turn_id
               FROM memory_lifecycle_audit a
               JOIN approved_memory m ON m.memory_id = a.memory_id
               WHERE a.action = 'approve' AND m.owner_principal_id = ?
                 AND json_extract(a.details_json, '$.auto') = 1
                 AND json_extract(a.details_json, '$.source_session_id') = ?
               ORDER BY a.created_at ASC""",
            (owner_principal_id, session_id),
        ).fetchall()
    remembered: list[dict[str, str]] = []
    for row in rows:
        entry = get_memory(
            str(row["memory_id"]), workspace_root=workspace_root, owner_principal_id=owner_principal_id
        )
        if entry is None or entry.deleted_at is not None or entry.archived_at is not None:
            continue
        remembered.append(
            {
                "memory_id": entry.memory_id,
                "text": entry.text,
                "memory_type": entry.memory_type,
                "source_turn_id": str(row["turn_id"] or ""),
            }
        )
    return remembered
