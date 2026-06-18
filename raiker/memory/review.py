from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.memory.candidates import MemoryCandidate
from raiker.memory.policy import (
    MemorySensitivity,
    classify_memory_sensitivity,
    semantic_write_policy_decision,
)
from raiker.storage.sqlite import SQLiteStore

VALID_DECISIONS = {"approved_for_later", "denied", "needs_user_review"}


@dataclass(frozen=True)
class MemoryReviewItem:
    candidate_id: str
    source_event_id: str
    proposed_text: str
    scope: str
    sensitivity: str
    decision: str
    reasons: list[str]
    created_at: str
    reviewed_at: str | None
    reviewer: str | None
    can_write_semantic_memory: bool
    semantic_write_enabled: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "source_event_id": self.source_event_id,
            "proposed_text": self.proposed_text,
            "scope": self.scope,
            "sensitivity": self.sensitivity,
            "decision": self.decision,
            "reasons": self.reasons,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "reviewer": self.reviewer,
            "can_write_semantic_memory": self.can_write_semantic_memory,
            "semantic_write_enabled": self.semantic_write_enabled,
        }


def review_item_from_candidate(candidate: dict[str, Any]) -> MemoryReviewItem:
    sensitivity = classify_memory_sensitivity(str(candidate["text"])).value
    can_write, reasons = semantic_write_policy_decision(sensitivity)
    decision = str(candidate.get("decision") or "needs_user_review")
    if sensitivity in {MemorySensitivity.SECRET_LIKE.value, MemorySensitivity.CREDENTIAL_LIKE.value}:
        decision = "denied" if decision in {"deferred", "needs_user_review"} else decision
    return MemoryReviewItem(
        candidate_id=str(candidate["candidate_id"]),
        source_event_id=str(candidate["source_event_id"]),
        proposed_text=str(candidate["text"]),
        scope=str(candidate["scope"]),
        sensitivity=sensitivity,
        decision=decision,
        reasons=reasons,
        created_at=str(candidate["created_at"]),
        reviewed_at=candidate.get("resolved_at"),
        reviewer=None,
        can_write_semantic_memory=can_write,
        semantic_write_enabled=False,
    )


class MemoryReviewQueue:
    def __init__(self, workspace_root: str | Path = ".") -> None:
        self.store = SQLiteStore(workspace_root)

    def add_candidate(self, text: str, *, source_event_id: str | None = None, scope: str = "project") -> MemoryReviewItem:
        sensitivity = classify_memory_sensitivity(text).value
        decision = "denied" if sensitivity in {"secret_like", "credential_like"} else "needs_user_review"
        candidate = MemoryCandidate(
            candidate_id=new_id("memcand_"),
            source_event_id=source_event_id or new_id("evt_"),
            memory_type="project",
            scope=scope,
            text=text,
            sensitivity=sensitivity,
            confidence=0.5,
            decision=decision,
            created_at=utc_now(),
        )
        self.store.insert_memory_candidate(candidate)
        return review_item_from_candidate(self.store.list_memory_candidates()[0])

    def list_candidates(self) -> list[MemoryReviewItem]:
        return [review_item_from_candidate(row) for row in self.store.list_memory_candidates()]

    def get_candidate(self, candidate_id: str) -> MemoryReviewItem | None:
        for item in self.list_candidates():
            if item.candidate_id == candidate_id:
                return item
        return None

    def mark(self, candidate_id: str, decision: str, *, reviewer: str = "local_user") -> MemoryReviewItem:
        if decision not in VALID_DECISIONS:
            raise ValueError(f"invalid_memory_review_decision:{decision}")
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE memory_candidates SET decision = ?, resolved_at = ? WHERE candidate_id = ?",
                (decision, utc_now(), candidate_id),
            )
        item = self.get_candidate(candidate_id)
        if item is None:
            raise ValueError(f"unknown_memory_candidate:{candidate_id}")
        return MemoryReviewItem(**{**item.__dict__, "reviewer": reviewer})

    def export_summary(self) -> dict[str, object]:
        items = self.list_candidates()
        return {
            "semantic_writes_enabled": False,
            "candidate_count": len(items),
            "needs_review_count": sum(1 for item in items if item.decision in {"deferred", "needs_user_review"}),
            "denied_secret_like_count": sum(1 for item in items if item.decision == "denied" and item.sensitivity in {"secret_like", "credential_like"}),
            "approved_for_later_count": sum(1 for item in items if item.decision == "approved_for_later"),
            "memory_governance_mode": "review_queue_only_no_semantic_writes",
            "embedding_records_written": 0,
            "vector_records_written": 0,
        }
