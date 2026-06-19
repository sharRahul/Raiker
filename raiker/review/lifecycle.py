from __future__ import annotations

import json
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.contracts.models import ClientMetadata
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.review.models import (
    PROPOSAL_LIFECYCLE_STATUSES,
    ProposalLifecycleRecord,
    ReviewActionProposal,
)
from raiker.storage.sqlite import SQLiteStore

_LIFECYCLE_SOURCE = "review_propose_fixes_save"


def _lifecycle_client() -> ClientMetadata:
    return ClientMetadata(type="cli", name="raiker-proposal-lifecycle", version="0.0.0")


class ProposalLifecycleError(ValueError):
    """Raised when a proposal lifecycle record is constructed or transitioned invalidly."""


def record_from_proposal(
    proposal: ReviewActionProposal, *, review_id: str, created_at: str | None = None
) -> ProposalLifecycleRecord:
    """Build a metadata-only lifecycle record from an in-memory proposal.

    The record is proposal-only and metadata-only; it never carries raw diff, file
    contents, secrets, prompt text, reasoning, or patch content. Status defaults to
    ``proposed``.
    """

    now = created_at or utc_now()
    return ProposalLifecycleRecord(
        proposal_id=proposal.proposal_id,
        review_id=review_id,
        finding_id=proposal.finding_id,
        title=proposal.title,
        action_type=proposal.action_type,
        risk_level=proposal.risk_level,
        requires_approval=proposal.requires_approval,
        would_modify_files=proposal.would_modify_files,
        status="proposed",
        files=list(proposal.files),
        summary=proposal.summary,
        created_at=now,
        updated_at=now,
        source=_LIFECYCLE_SOURCE,
    )


class ProposalLifecycleStore:
    """Metadata-only persistence for proposal lifecycle records.

    This store never executes, applies, mutates source files, stages/unstages the Git
    index, commits, runs tests, or calls shell/process/network. It only reads/writes
    lifecycle metadata rows in the local SQLite database and emits metadata-only events.
    """

    def __init__(self, store: SQLiteStore, *, emit_events: bool = True) -> None:
        self.store = store
        self.emit_events = emit_events
        self._writer = EventLogWriter(store) if emit_events else None
        self._session_id = "proposal-lifecycle"

    def save_proposals(
        self, proposals: list[ReviewActionProposal], *, review_id: str
    ) -> list[ProposalLifecycleRecord]:
        """Persist proposals as lifecycle records with status ``proposed``.

        Returns the saved records (empty list if no proposals). Existing proposal ids
        are upserted; re-saving a proposal resets its status to ``proposed`` only if it
        was previously ``proposed`` (status of an existing record is preserved otherwise
        so user markings survive re-runs). No raw diff/secret/content is stored.
        """

        if not proposals:
            return []
        now = utc_now()
        records: list[ProposalLifecycleRecord] = []
        pending_events: list[tuple[str, dict[str, object]]] = []
        with self.store.connect() as connection:
            for proposal in proposals:
                existing = connection.execute(
                    "SELECT status, created_at FROM proposal_lifecycle_records WHERE proposal_id = ?",
                    (proposal.proposal_id,),
                ).fetchone()
                status = str(existing["status"]) if existing is not None else "proposed"
                created_at = str(existing["created_at"]) if existing is not None else now
                record = ProposalLifecycleRecord(
                    proposal_id=proposal.proposal_id,
                    review_id=review_id,
                    finding_id=proposal.finding_id,
                    title=proposal.title,
                    action_type=proposal.action_type,
                    risk_level=proposal.risk_level,
                    requires_approval=proposal.requires_approval,
                    would_modify_files=proposal.would_modify_files,
                    status=status,
                    files=list(proposal.files),
                    summary=proposal.summary,
                    created_at=created_at,
                    updated_at=now,
                    source=_LIFECYCLE_SOURCE,
                )
                connection.execute(
                    """
                    INSERT OR REPLACE INTO proposal_lifecycle_records
                    (proposal_id, review_id, finding_id, title, action_type, risk_level,
                     requires_approval, would_modify_files, status, files_json, summary,
                     created_at, updated_at, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.proposal_id,
                        record.review_id,
                        record.finding_id,
                        record.title,
                        record.action_type,
                        record.risk_level,
                        int(record.requires_approval),
                        int(record.would_modify_files),
                        record.status,
                        json.dumps(record.files),
                        record.summary,
                        record.created_at,
                        record.updated_at,
                        record.source,
                    ),
                )
                records.append(record)
                pending_events.append(
                    (
                        "proposal_lifecycle_created",
                        {
                            "proposal_id": record.proposal_id,
                            "review_id": record.review_id,
                            "finding_id": record.finding_id,
                            "action_type": record.action_type,
                            "risk_level": record.risk_level,
                            "requires_approval": record.requires_approval,
                            "would_modify_files": record.would_modify_files,
                            "status": record.status,
                        },
                    )
                )
        for event_type, payload in pending_events:
            self._emit(event_type, payload)
        return records

    def list_records(
        self, *, status: str | None = None, limit: int = 20
    ) -> list[ProposalLifecycleRecord]:
        """List lifecycle records newest-first with optional status filter and limit."""

        query = "SELECT * FROM proposal_lifecycle_records"
        params: list[Any] = []
        if status is not None:
            if status not in PROPOSAL_LIFECYCLE_STATUSES:
                raise ProposalLifecycleError(f"invalid_lifecycle_status:{status}")
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(str(limit))
        with self.store.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        records = [_row_to_record(dict(row)) for row in rows]
        self._emit(
            "proposal_lifecycle_listed",
            {
                "status_filter": status,
                "limit": limit,
                "result_count": len(records),
            },
        )
        return records

    def get_record(self, proposal_id: str) -> ProposalLifecycleRecord | None:
        """Load one lifecycle record by proposal id."""

        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM proposal_lifecycle_records WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        record = _row_to_record(dict(row))
        self._emit(
            "proposal_lifecycle_viewed",
            {"proposal_id": record.proposal_id, "status": record.status},
        )
        return record

    def mark_status(
        self, proposal_id: str, *, new_status: str
    ) -> ProposalLifecycleRecord:
        """Transition a record's status (metadata only). Never executes or applies."""

        if new_status not in PROPOSAL_LIFECYCLE_STATUSES:
            raise ProposalLifecycleError(f"invalid_lifecycle_status:{new_status}")
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM proposal_lifecycle_records WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise ProposalLifecycleError(f"unknown_proposal_id:{proposal_id}")
            previous_status = str(row["status"])
            now = utc_now()
            connection.execute(
                "UPDATE proposal_lifecycle_records SET status = ?, updated_at = ? WHERE proposal_id = ?",
                (new_status, now, proposal_id),
            )
            updated_row = connection.execute(
                "SELECT * FROM proposal_lifecycle_records WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        record = _row_to_record(dict(updated_row))
        self._emit(
            "proposal_lifecycle_status_changed",
            {
                "proposal_id": record.proposal_id,
                "previous_status": previous_status,
                "new_status": new_status,
            },
        )
        return record

    def _emit(self, event_type: str, payload: dict[str, object]) -> None:
        if self._writer is None:
            return
        self._writer.append(
            make_event(
                session_id=self._session_id,
                turn_id=None,
                event_type=event_type,
                actor="proposal_lifecycle",
                payload=payload,
                client=_lifecycle_client(),
            )
        )


def _row_to_record(row: dict[str, Any]) -> ProposalLifecycleRecord:
    return ProposalLifecycleRecord(
        proposal_id=str(row["proposal_id"]),
        review_id=str(row["review_id"]),
        finding_id=str(row["finding_id"]),
        title=str(row["title"]),
        action_type=str(row["action_type"]),
        risk_level=str(row["risk_level"]),
        requires_approval=bool(row["requires_approval"]),
        would_modify_files=bool(row["would_modify_files"]),
        status=str(row["status"]),
        files=json.loads(str(row["files_json"])),
        summary=str(row["summary"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        source=str(row["source"]),
    )


def render_record_text(record: ProposalLifecycleRecord) -> str:
    lines = [
        f"Proposal: {record.proposal_id}",
        f"- Review: {record.review_id}",
        f"- Finding: {record.finding_id}",
        f"- Title: {record.title}",
        f"- Action type: {record.action_type}",
        f"- Risk: {record.risk_level}",
        f"- Requires approval: {record.requires_approval}",
        f"- Would modify files: {record.would_modify_files}",
        f"- Status: {record.status}",
        f"- Files: {', '.join(record.files) if record.files else '-'}",
        f"- Summary: {record.summary}",
        f"- Created: {record.created_at}",
        f"- Updated: {record.updated_at}",
        f"- Source: {record.source}",
        "Safety: metadata-only, proposal-only. No files were modified.",
    ]
    return "\n".join(lines)


def render_records_text(records: list[ProposalLifecycleRecord]) -> str:
    if not records:
        return "No saved proposals found."
    lines = ["Saved proposals:"]
    for index, record in enumerate(records, start=1):
        lines.append(
            f"{index}. {record.proposal_id} [{record.status}] {record.title} "
            f"(finding: {record.finding_id}, risk: {record.risk_level})"
        )
    lines.append("Safety: metadata-only, proposal-only. No files were modified.")
    return "\n".join(lines)


def records_to_json(records: list[ProposalLifecycleRecord]) -> str:
    return json.dumps([r.to_dict() for r in records], sort_keys=True, indent=2)


def record_to_json(record: ProposalLifecycleRecord) -> str:
    return json.dumps(record.to_dict(), sort_keys=True, indent=2)


__all__ = [
    "ProposalLifecycleError",
    "ProposalLifecycleRecord",
    "ProposalLifecycleStore",
    "record_from_proposal",
    "record_to_json",
    "records_to_json",
    "render_record_text",
    "render_records_text",
]
