# mypy: disable-error-code="misc"
"""Memory review and control: proposals, lifecycle, import and export, integrity,
observations and the embedding engine (GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Literal, cast

from raiker.contracts.ids import new_id, utc_now
from raiker.control.dtos import ControlResult
from raiker.control.views.memory import (
    EmbeddingProviderView,
    EmbeddingSpaceView,
    MemoryControlView,
    MemorySettingsView,
    ObservationView,
)
from raiker.memory.store import get_memory, list_memory
from raiker.runtime.authority.models import PrincipalType
from raiker.storage.internal_paths import display_path, internal_io_path

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


class MemoryService:

    # The user-facing surface over the EXISTING governed memory store — list
    # with provenance/scope/sensitivity, pin (organizing label only), forget
    # (human-only, reuses the governed forget path), and an incognito opt-out
    # boundary that withholds approved project memory from the turn context.
    # No second memory system is created; these read/control the same store
    # the memory_write/memory_forget tools already use.

    def list_memories(
        self: DashboardService, scope: str | None = None, *, acting_principal_id: str | None = None
    ) -> list[MemoryControlView]:
        """List approved memories with their governance metadata + pin state."""
        pinned_ids = self.store.list_pinned_memory_ids()
        entries = list_memory(
            workspace_root=self.workspace_root,
            scope=scope,
            limit=200,
            store=self.store,
            include_search_disabled=True,
            owner_principal_id=acting_principal_id,
        )
        histories = {
            e.memory_id: self.store.list_memory_lifecycle_events(
                e.memory_id, owner_principal_id=e.owner_principal_id
            )
            for e in entries
        }
        views = [
            MemoryControlView(
                memory_id=e.memory_id,
                text=e.text,
                scope=e.scope,
                sensitivity=e.sensitivity,
                memory_type=e.memory_type,
                created_at=e.created_at,
                tags=e.tags,
                source=e.source,
                provenance=e.provenance,
                confidence=e.confidence,
                trust_score=e.trust_score,
                retention=e.retention,
                approval_state=e.approval_state,
                pinned=e.memory_id in pinned_ids,
                search_enabled=e.search_enabled,
                expires_at=e.expires_at,
                archived_at=e.archived_at,
                source_event_id=e.source_event_id,
                created_by=e.created_by,
                valid_from=e.valid_from,
                valid_until=e.valid_until,
                supersedes_memory_id=e.supersedes_memory_id,
                remembered_reason=e.remembered_reason,
                updated_at=e.updated_at,
                last_used_at=next(
                    (
                        event["created_at"]
                        for event in histories[e.memory_id]
                        if event["action"] == "recall"
                    ),
                    None,
                ),
            )
            for e in entries
        ]
        if acting_principal_id:
            self.store.record_memory_lifecycle_event(
                "workspace_memory_control",
                "admin_access",
                acting_principal_id,
                {"operation": "list", "scope": scope, "memory_count": len(views)},
            )
        return views

    def set_memory_pinned(
        self: DashboardService, memory_id: str, pinned: bool, acting_principal_id: str | None
    ) -> ControlResult:
        """Pin (or unpin) a memory. Organizing label only — grants nothing."""
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if (
            get_memory(
                memory_id,
                workspace_root=self.workspace_root,
                owner_principal_id=principal.principal_id,
            )
            is None
        ):
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        self.store.set_memory_pinned(memory_id, pinned)
        self.store.record_memory_lifecycle_event(
            memory_id, "pin" if pinned else "unpin", principal.principal_id
        )
        return ControlResult(ok=True, data={"memory_id": memory_id, "pinned": pinned})

    def list_memory_proposals(self: DashboardService, acting_principal_id: str | None) -> list[dict[str, Any]]:
        if not self._is_human(acting_principal_id):
            return []
        return self.store.list_memory_candidates(
            decision="deferred", owner_principal_id=acting_principal_id
        )

    def list_memory_relationship_proposals(
        self: DashboardService, acting_principal_id: str | None
    ) -> list[dict[str, Any]]:
        if not self._is_human(acting_principal_id):
            return []
        return self.store.list_memory_relationship_candidates(acting_principal_id or "")

    def scan_memory_relationships(self: DashboardService, acting_principal_id: str | None) -> ControlResult:
        """Owner-started, idempotent backfill over currently approved memory."""
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.entity_extraction import propose_memory_relationships

        scanned = proposed = skipped = already_present = 0
        for memory in self.store.list_approved_memory(
            limit=10_000,
            include_search_disabled=False,
            owner_principal_id=acting_principal_id,
        ):
            summary = propose_memory_relationships(
                self.store, str(memory["memory_id"]), acting_principal_id or ""
            )
            scanned += summary.scanned
            proposed += summary.proposed
            skipped += summary.skipped
            already_present += summary.already_present
        return ControlResult(
            ok=True,
            data={
                "scanned": scanned,
                "proposed": proposed,
                "skipped": skipped,
                "already_present": already_present,
            },
        )

    def decide_memory_relationship_proposal(
        self: DashboardService,
        candidate_id: str,
        *,
        decision: str,
        expected_decision: str,
        acting_principal_id: str | None,
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if decision not in {"approved", "denied"}:
            return ControlResult(ok=False, reason_code="invalid_memory_relationship_decision")
        try:
            relationship_id = self.store.resolve_memory_relationship_candidate_atomic(
                candidate_id,
                owner_principal_id=acting_principal_id or "",
                decision=decision,
                reviewer_id=acting_principal_id or "",
                expected_decision=expected_decision,
            )
        except ValueError as exc:
            if str(exc) == "stale_memory_relationship_candidate":
                return ControlResult(ok=False, reason_code="stale_memory_relationship_proposal")
            raise
        return ControlResult(
            ok=True,
            data={
                "candidate_id": candidate_id,
                "decision": decision,
                "relationship_id": relationship_id or None,
            },
        )

    def reject_memory_relationship(
        self: DashboardService,
        relationship_id: str,
        *,
        reason: str,
        expected_active: bool,
        acting_principal_id: str | None,
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if not reason.strip():
            return ControlResult(
                ok=False, reason_code="memory_relationship_rejection_reason_required"
            )
        if not self.store.reject_memory_relationship(
            relationship_id,
            owner_principal_id=acting_principal_id or "",
            expected_active=expected_active,
        ):
            return ControlResult(ok=False, reason_code="stale_memory_relationship")
        self.store.record_memory_lifecycle_event(
            relationship_id,
            "reject",
            acting_principal_id or "",
            {"kind": "entity_relationship", "reason": reason.strip()},
        )
        return ControlResult(
            ok=True,
            data={"relationship_id": relationship_id, "active": False},
        )

    def decide_memory_proposal(
        self: DashboardService,
        candidate_id: str,
        *,
        decision: str,
        edited_text: str | None,
        reason: str | None,
        expected_decision: str,
        acting_principal_id: str | None,
    ) -> ControlResult:
        """Human-only, stale-safe approval/rejection for durable memory proposals."""
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if decision not in {"approved", "rejected"}:
            return ControlResult(ok=False, reason_code="invalid_memory_proposal_decision")
        candidate = self.store.get_memory_candidate(
            candidate_id, owner_principal_id=acting_principal_id or ""
        )
        if candidate is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory_proposal:{candidate_id}")
        if candidate["decision"] != expected_decision:
            return ControlResult(ok=False, reason_code="stale_memory_proposal")
        text = (edited_text if edited_text is not None else str(candidate["text"])).strip()
        if decision == "approved" and not text:
            return ControlResult(ok=False, reason_code="empty_memory_text")
        from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity

        sensitivity = classify_memory_sensitivity(text)
        if decision == "approved" and sensitivity in {
            MemorySensitivity.SECRET_LIKE,
            MemorySensitivity.CREDENTIAL_LIKE,
        }:
            return ControlResult(ok=False, reason_code="secret_like_memory_blocked")
        if not self.store.resolve_memory_candidate(
            candidate_id,
            owner_principal_id=acting_principal_id or "",
            expected_decision=expected_decision,
            decision=decision,
            reason=reason,
            resolved_at=utc_now(),
        ):
            return ControlResult(ok=False, reason_code="stale_memory_proposal")
        if decision == "rejected":
            self.store.record_memory_lifecycle_event(
                candidate_id,
                "reject",
                acting_principal_id or "",
                {"reason": reason or "", "source_event_id": candidate["source_event_id"]},
            )
            return ControlResult(ok=True, data={"candidate_id": candidate_id, "decision": decision})

        from raiker.memory.entity_extraction import propose_memory_relationships
        from raiker.memory.store import MemoryGovernance, write_memory

        entry = write_memory(
            text,
            workspace_root=self.workspace_root,
            scope=str(candidate["scope"]),
            memory_type=str(candidate["memory_type"]),
            source="human_approved_proposal",
            store=self.store,
            owner_principal_id=acting_principal_id,
            governance=MemoryGovernance(
                source_event_id=str(candidate["source_event_id"]),
                source_session_id="",
                source_turn_id=None,
                source_type="memory_proposal",
                confidence=float(candidate["confidence"]),
                trust_score=1.0,
                retention="until_forget",
                approval_state="approved",
                created_by=acting_principal_id or "",
            ),
        )
        self.store.record_memory_lifecycle_event(
            entry.memory_id,
            "approve",
            acting_principal_id or "",
            {
                "candidate_id": candidate_id,
                "edited": edited_text is not None and edited_text != candidate["text"],
                "reason": reason or "",
            },
        )
        extraction = propose_memory_relationships(
            self.store, entry.memory_id, acting_principal_id or ""
        )
        return ControlResult(
            ok=True,
            data={
                "candidate_id": candidate_id,
                "decision": decision,
                "memory_id": entry.memory_id,
                "relationship_proposals": extraction.proposed,
            },
        )

    def memory_history(self: DashboardService, memory_id: str, acting_principal_id: str | None) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        events = self.store.list_memory_lifecycle_events(
            memory_id, owner_principal_id=acting_principal_id or ""
        )
        if not events:
            memory = get_memory(
                memory_id,
                workspace_root=self.workspace_root,
                include_expired=True,
                include_archived=True,
                owner_principal_id=acting_principal_id,
            )
            if memory is None:
                return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        return ControlResult(ok=True, data={"memory_id": memory_id, "events": events})

    def change_memory_scope(
        self: DashboardService,
        memory_id: str,
        scope: str,
        expected_updated_at: str | None,
        reason: str,
        acting_principal_id: str | None,
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        normalized = scope.strip()
        if not normalized or not (
            normalized in {"account", "project", "session"}
            or normalized.startswith(("project:", "session:"))
        ):
            return ControlResult(ok=False, reason_code="invalid_memory_scope")
        current = get_memory(
            memory_id,
            workspace_root=self.workspace_root,
            include_expired=True,
            include_archived=True,
            owner_principal_id=acting_principal_id,
        )
        if current is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        if current.updated_at != expected_updated_at:
            return ControlResult(ok=False, reason_code="stale_memory_scope_change")
        from raiker.memory.store import update_memory

        updated = update_memory(
            memory_id,
            workspace_root=self.workspace_root,
            scope=normalized,
            store=self.store,
            owner_principal_id=acting_principal_id,
        )
        if updated is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        self.store.record_memory_lifecycle_event(
            memory_id,
            "scope_change",
            acting_principal_id or "",
            {"from": current.scope, "to": normalized, "reason": reason.strip()},
        )
        return ControlResult(
            ok=True,
            data={"memory_id": memory_id, "scope": normalized, "updated_at": updated.updated_at},
        )

    def forget_memory_controlled(
        self: DashboardService, memory_id: str, acting_principal_id: str | None
    ) -> ControlResult:
        """Forget a memory through the governed path (human-only).

        Reuses the existing ``forget_memory`` store function which writes a
        tombstone and marks the db row forgotten. No new authority is
        granted — the human owner may always forget their own memories.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.store import MemoryForgetGovernance, forget_memory

        governance = MemoryForgetGovernance(
            source_event_id=new_id("evt_"),
            source_session_id="",
            source_turn_id=None,
            source_type="user_ui",
            deleted_by=principal.principal_id,
        )
        ok = forget_memory(
            memory_id,
            workspace_root=self.workspace_root,
            store=self.store,
            governance=governance,
            owner_principal_id=principal.principal_id,
        )
        if not ok:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        self.store.record_memory_lifecycle_event(memory_id, "forget", principal.principal_id)
        return ControlResult(ok=True, data={"memory_id": memory_id})

    def set_memory_archived(
        self: DashboardService, memory_id: str, archived: bool, acting_principal_id: str | None
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.store import set_memory_archived

        entry = set_memory_archived(
            memory_id,
            archived=archived,
            workspace_root=self.workspace_root,
            store=self.store,
            owner_principal_id=acting_principal_id,
        )
        if entry is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        self.store.record_memory_lifecycle_event(
            memory_id, "archive" if archived else "restore", acting_principal_id or ""
        )
        return ControlResult(ok=True, data={"memory_id": memory_id, "archived": archived})

    def preview_memory_purge(
        self: DashboardService, memory_id: str, acting_principal_id: str | None
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.store import get_memory

        memory = get_memory(
            memory_id,
            workspace_root=self.workspace_root,
            include_expired=True,
            include_archived=True,
            owner_principal_id=acting_principal_id,
        )
        if memory is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        memory_path = internal_io_path(
            self.workspace_root / ".raiker" / "memory" / f"{memory_id}.md"
        )
        return ControlResult(
            ok=True,
            data={
                "memory_id": memory_id,
                "artifacts": [display_path(memory_path)],
                "backup_disposition": "retained backups are not immediately erased",
                "requires_confirmation": memory_id,
            },
        )

    def purge_memory(
        self: DashboardService, memory_id: str, confirmation: str | None, acting_principal_id: str | None
    ) -> ControlResult:
        preview = self.preview_memory_purge(memory_id, acting_principal_id)
        if not preview.ok:
            return preview
        if confirmation != memory_id:
            return ControlResult(ok=False, reason_code="memory_purge_confirmation_required")
        from raiker.contracts.ids import utc_now

        path = internal_io_path(self.workspace_root / ".raiker" / "memory" / f"{memory_id}.md")
        path.unlink(missing_ok=True)
        projections = self.store.list_memory_projections(memory_id)
        self.store.deactivate_memory_projections(memory_id)
        self.store.delete_approved_memory(memory_id, owner_principal_id=acting_principal_id)
        disposition = {
            **preview.data,
            "projections": projections,
            "completed_storage_locations": [
                "markdown_export",
                "sqlite_approved_memory",
                "sqlite_fts",
                "projection_mappings",
            ],
        }
        self.store.create_memory_purge_record(
            new_id("pur_"), memory_id, acting_principal_id or "", utc_now(), disposition
        )
        self.store.record_memory_lifecycle_event(
            memory_id, "purge", acting_principal_id or "", disposition
        )
        return ControlResult(
            ok=True,
            data={
                "memory_id": memory_id,
                "purged": True,
                "backup_disposition": preview.data["backup_disposition"],
            },
        )

    def edit_memory_controlled(
        self: DashboardService, memory_id: str, text: str, acting_principal_id: str | None
    ) -> ControlResult:
        return self._update_memory_controlled(
            memory_id, text=text, search_enabled=None, acting_principal_id=acting_principal_id
        )

    def correct_memory_controlled(
        self: DashboardService, memory_id: str, text: str, reason: str, acting_principal_id: str | None
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.store import MemoryGovernance, correct_memory

        replacement = correct_memory(
            memory_id,
            text,
            workspace_root=self.workspace_root,
            store=self.store,
            remembered_reason=reason,
            owner_principal_id=self.store.account_scope(acting_principal_id),
            governance=MemoryGovernance(
                source_event_id=new_id("evt_"),
                source_session_id="",
                source_turn_id=None,
                source_type="human_correction",
                confidence=1.0,
                trust_score=1.0,
                retention="until_forget",
                approval_state="approved",
                created_by=acting_principal_id or "",
            ),
        )
        if replacement is None:
            return ControlResult(ok=False, reason_code="invalid_memory_correction")
        self.store.record_memory_lifecycle_event(
            memory_id,
            "correct",
            acting_principal_id or "",
            {"replacement_memory_id": replacement.memory_id, "reason": reason},
        )
        return ControlResult(
            ok=True, data={"memory_id": replacement.memory_id, "supersedes_memory_id": memory_id}
        )

    def set_memory_search_enabled(
        self: DashboardService, memory_id: str, search_enabled: bool, acting_principal_id: str | None
    ) -> ControlResult:
        return self._update_memory_controlled(
            memory_id,
            text=None,
            search_enabled=search_enabled,
            acting_principal_id=acting_principal_id,
        )

    def set_memory_expiry(
        self: DashboardService, memory_id: str, expires_at: str | None, acting_principal_id: str | None
    ) -> ControlResult:
        return self._update_memory_controlled(
            memory_id,
            text=None,
            search_enabled=None,
            expires_at=expires_at,
            update_expires_at=True,
            acting_principal_id=acting_principal_id,
        )

    def export_memories(self: DashboardService, acting_principal_id: str | None) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        memories = [
            m.to_dict() for m in self.list_memories(acting_principal_id=acting_principal_id)
        ]
        self.store.record_memory_lifecycle_event(
            "workspace_memory_export",
            "export",
            acting_principal_id or "",
            {"memory_count": len(memories)},
        )
        return ControlResult(ok=True, data={"memories": memories})

    @staticmethod
    def _import_scope(item: dict[str, Any]) -> str:
        """The scope an imported record would be written at, resolved once.

        ``write_memory``'s own default is ``project``; reading it here rather
        than in two places is what keeps the preview's answer and the import's
        behaviour from being able to disagree about which record is a duplicate.
        """
        return str(item.get("scope", "project"))

    def preview_memory_import(
        self: DashboardService, memories: list[dict[str, Any]], acting_principal_id: str | None
    ) -> ControlResult:
        """BUG-244 — how many of these records the workspace already holds.

        A read, and only a read: it writes nothing, proposes nothing, and is
        safe to call as often as a file is chosen. The owner sees the answer
        *before* deciding, which is the difference between an import that says
        "4 records" and one that says "1 new, 3 already stored".
        """
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        stored = self.store.stored_memory_checksums(owner_principal_id=acting_principal_id)
        duplicates: list[dict[str, Any]] = []
        # A file that repeats a record inside itself is the same defect arriving
        # by a different route, so the run is deduplicated against itself too.
        seen: set[tuple[str, str]] = set()
        new_count = 0
        for index, item in enumerate(memories):
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            key = (hashlib.sha256(text.encode()).hexdigest(), self._import_scope(item))
            existing = stored.get(key)
            if existing is not None or key in seen:
                duplicates.append(
                    {
                        "index": index,
                        "text": text[:200],
                        "scope": key[1],
                        # Absent when the duplicate is inside the file itself,
                        # which is a different thing from one already stored.
                        "memory_id": existing or "",
                    }
                )
                continue
            seen.add(key)
            new_count += 1
        return ControlResult(
            ok=True,
            data={
                "total": len(memories),
                "new_count": new_count,
                "duplicate_count": len(duplicates),
                "duplicates": duplicates[:50],
            },
        )

    def import_memories(
        self: DashboardService,
        memories: list[dict[str, Any]],
        acting_principal_id: str | None,
        *,
        skip_duplicates: bool = True,
    ) -> ControlResult:
        """Write reviewed records, skipping ones the workspace already holds.

        BUG-244 — the skip is the default rather than the only behaviour. An
        owner who means to store the same sentence at a second scope is doing
        something legitimate, and the record they would be duplicating is named
        in the preview, so ``skip_duplicates=False`` is an informed choice
        rather than a way around a rule.
        """
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.entity_extraction import propose_memory_relationships
        from raiker.memory.store import MemoryGovernance, update_memory, write_memory

        stored = (
            self.store.stored_memory_checksums(owner_principal_id=acting_principal_id)
            if skip_duplicates
            else {}
        )
        written: set[tuple[str, str]] = set()
        relationship_proposals = 0
        imported = 0
        skipped = 0
        for item in memories:
            text = str(item.get("text", "")).strip()
            if not text:
                return ControlResult(ok=False, reason_code="empty_memory_text")
            key = (hashlib.sha256(text.encode()).hexdigest(), self._import_scope(item))
            if skip_duplicates and (key in stored or key in written):
                skipped += 1
                continue
            written.add(key)
            entry = write_memory(
                text,
                workspace_root=self.workspace_root,
                scope=str(item.get("scope", "project")),
                store=self.store,
                governance=MemoryGovernance(
                    new_id("evt_"),
                    "",
                    None,
                    "user_import",
                    1.0,
                    1.0,
                    str(item.get("retention", "until_forget")),
                    "approved",
                    acting_principal_id or "",
                ),
                owner_principal_id=acting_principal_id,
            )
            update_memory(
                entry.memory_id,
                workspace_root=self.workspace_root,
                search_enabled=bool(item.get("search_enabled", True)),
                expires_at=item.get("expires_at"),
                update_expires_at="expires_at" in item,
                store=self.store,
                owner_principal_id=acting_principal_id,
            )
            self.store.record_memory_lifecycle_event(
                entry.memory_id, "import", acting_principal_id or "", {"source": "user_import"}
            )
            relationship_proposals += propose_memory_relationships(
                self.store, entry.memory_id, acting_principal_id or ""
            ).proposed
            imported += 1
        return ControlResult(
            ok=True,
            data={
                # `count` is what actually changed, not how many records were
                # offered. An import that reported four and wrote one was the
                # half of BUG-244 a reader could not see.
                "count": imported,
                "reviewed": len(memories),
                "imported": imported,
                "skipped_duplicates": skipped,
                "relationship_proposals": relationship_proposals,
            },
        )

    def reconcile_memory_indexes(self: DashboardService, acting_principal_id: str | None) -> ControlResult:
        """Owner-started repair; never runs as an autonomous background worker."""
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        return ControlResult(
            ok=True,
            data=self.store.reconcile_memory_projections(owner_principal_id=acting_principal_id),
        )

    def session_recall(
        self: DashboardService, session_id: str, *, turn_id: str | None, acting_principal_id: str
    ) -> ControlResult:
        """C17 — the memories a conversation's turns were actually given.

        Read live from the memory store rather than from a copy taken at recall
        time, so a memory corrected since the turn ran reads as it is now, and
        one that has been forgotten simply stops appearing. That is what makes
        "forget" from the transcript mean the same thing as "forget" from the
        Memory page: there is one record, and this is a view of it.

        Owner-scoped by the same rule as the citation ledger: a row is keyed by
        the principal, so another account's conversation is an empty list rather
        than a refusal that would confirm the conversation exists.
        """
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.store import get_memory

        rows = self.store.load_turn_recall(session_id, acting_principal_id, turn_id)
        pinned = self.store.list_pinned_memory_ids()
        memories = []
        for row in rows:
            memory_id = str(row["memory_id"])
            entry = get_memory(
                memory_id,
                workspace_root=self.workspace_root,
                owner_principal_id=acting_principal_id,
            )
            if entry is None:
                # Forgotten, expired or archived since the turn ran. Omitted
                # rather than shown as a tombstone: the transcript is saying
                # what Raiker knows now, not what it knew then.
                continue
            memories.append({
                "memory_id": memory_id,
                "turn_id": str(row["turn_id"]),
                "text": entry.text,
                "scope": entry.scope,
                "pinned": memory_id in pinned,
            })
        return ControlResult(ok=True, data={"session_id": session_id, "memories": memories})

    def memory_integrity(self: DashboardService, acting_principal_id: str | None) -> ControlResult:
        """MEM-09 — the integrity report, on request, where the owner can read it.

        The check itself has existed since the memory audit; nothing called it.
        A report that is computed and never displayed answers the first half of
        a reliability question and none of the second, so this is deliberately a
        read the owner starts and a page renders — not a background sweep whose
        findings live in a log.

        Read-only. It repairs nothing; the repairs are separate, named actions.
        """
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.integrity import inspect_memory_integrity

        report = inspect_memory_integrity(store=self.store, workspace_root=self.workspace_root)
        return ControlResult(ok=True, data={**asdict(report), "clean": report.clean})

    def rebuild_conversation_index(self: DashboardService, acting_principal_id: str | None) -> ControlResult:
        """MEM-09's stated repair for a drifted `conversation_fts`.

        Owner-started, and safe to run at any time: the index is a projection of
        `turns`, so rebuilding it recomputes every row from the table that owns
        the content and can lose nothing.
        """
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        return ControlResult(ok=True, data={"indexed_rows": self.store.rebuild_conversation_fts()})

    def list_observations(self: DashboardService, acting_principal_id: str | None) -> ControlResult:
        """MEM-04 — what the runtime captured, and what it refused to.

        The counters are part of the answer, not a convenience: an owner looking
        at an empty list needs to know whether nothing was produced or
        everything was refused, and a page that can only count what it received
        cannot tell them.
        """
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.eidetic import list_observations

        owner = self.store.account_scope(acting_principal_id) or (acting_principal_id or "")
        observations = list_observations(store=self.store, owner_principal_id=owner)
        with self.store.connect() as connection:
            gists = {
                str(row["observation_id"]): (
                    str(row["gist_id"]),
                    str(row["status"]),
                    str(row["summary"]),
                )
                for row in connection.execute(
                    "SELECT gist_id, observation_id, status, summary FROM gist_memories"
                ).fetchall()
            }
        views = []
        for item in observations:
            gist = gists.get(item.observation_id)
            views.append(
                ObservationView(
                    observation_id=item.observation_id,
                    session_id=item.session_id,
                    turn_id=item.turn_id,
                    tool_name=item.tool_name,
                    source_type=item.source_type,
                    summary=item.summary,
                    sensitivity=item.sensitivity,
                    retention=item.retention,
                    capture_status=cast(Literal["captured", "skipped"], item.capture_status),
                    skip_reason=item.skip_reason,
                    promotable_to_memory=item.promotable_to_memory,
                    content_sha256=item.content_sha256,
                    content_bytes=item.content_bytes,
                    artifact_ref=item.artifact_ref,
                    source_event_id=item.source_event_id,
                    created_at=item.created_at,
                    expires_at=item.expires_at,
                    gist_id=gist[0] if gist else "",
                    gist_status=gist[1] if gist else "",
                    gist_summary=gist[2] if gist else "",
                )
            )
        # MEM-07 - the retention class of every row was already stated and
        # nothing ever acted on it, so `turn_only` and `short_term_7_days`
        # records were kept forever. The sweep is still owner-confirmed rather
        # than automatic; what was missing was being *shown* what is due.
        from raiker.memory.eidetic import expiry_preview

        due = set(expiry_preview(store=self.store, now=utc_now(), owner_principal_id=owner))
        return ControlResult(
            ok=True,
            data={
                "observations": [view.to_dict() for view in views],
                "captured": sum(1 for view in views if view.capture_status == "captured"),
                "skipped": sum(1 for view in views if view.capture_status == "skipped"),
                "gists_pending": sum(1 for view in views if view.gist_status == "pending_review"),
                "due_for_expiry": sorted(due),
            },
        )

    def delete_observations(
        self: DashboardService, observation_ids: set[str], acting_principal_id: str | None
    ) -> ControlResult:
        """The same delete control the rest of memory has, for observations."""
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.eidetic import delete_observations

        owner = self.store.account_scope(acting_principal_id) or (acting_principal_id or "")
        try:
            deleted = delete_observations(
                store=self.store, owner_principal_id=owner, observation_ids=observation_ids
            )
        except ValueError as error:
            return ControlResult(ok=False, reason_code=str(error))
        if not deleted:
            return ControlResult(ok=False, reason_code="unknown_observation")
        return ControlResult(ok=True, data={"deleted_observation_ids": deleted})

    def discard_gist(self: DashboardService, gist_id: str, acting_principal_id: str | None) -> ControlResult:
        """Reject a proposed gist without touching the observation it came from.

        A gist is a candidate; discarding one is a review decision, and the
        observation it summarised remains its own record with its own retention.
        """
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        owner = self.store.account_scope(acting_principal_id) or (acting_principal_id or "")
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT observation_id FROM gist_memories WHERE gist_id = ?", (gist_id,)
            ).fetchone()
            if row is None:
                return ControlResult(ok=False, reason_code="unknown_gist")
            owned = connection.execute(
                "SELECT 1 FROM eidetic_observations"
                " WHERE observation_id = ? AND owner_principal_id = ?",
                (str(row["observation_id"]), owner),
            ).fetchone()
            if owned is None:
                return ControlResult(ok=False, reason_code="unknown_gist")
            connection.execute("DELETE FROM gist_memories WHERE gist_id = ?", (gist_id,))
        return ControlResult(ok=True, data={"gist_id": gist_id, "discarded": True})

    def cleanup_expired_observations(
        self: DashboardService, observation_ids: set[str], now: str, acting_principal_id: str | None
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.eidetic import cleanup_expired_observations

        owner = self.store.account_scope(acting_principal_id) or (acting_principal_id or "")
        try:
            deleted = cleanup_expired_observations(
                store=self.store,
                now=now,
                confirmed_ids=observation_ids,
                owner_principal_id=owner,
            )
        except PermissionError as error:
            return ControlResult(ok=False, reason_code=str(error))
        return ControlResult(ok=True, data={"deleted_observation_ids": deleted})

    def _update_memory_controlled(
        self: DashboardService,
        memory_id: str,
        *,
        text: str | None,
        search_enabled: bool | None,
        acting_principal_id: str | None,
        expires_at: str | None = None,
        update_expires_at: bool = False,
    ) -> ControlResult:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if text is not None and not text.strip():
            return ControlResult(ok=False, reason_code="empty_memory_text")
        from raiker.memory.store import update_memory

        updated = update_memory(
            memory_id,
            workspace_root=self.workspace_root,
            text=text,
            search_enabled=search_enabled,
            expires_at=expires_at,
            update_expires_at=update_expires_at,
            store=self.store,
            owner_principal_id=acting_principal_id,
        )
        if updated is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        if text is not None:
            self.store.record_memory_lifecycle_event(
                memory_id, "edit", acting_principal_id or "", {"text_changed": True}
            )
        if update_expires_at:
            self.store.record_memory_lifecycle_event(
                memory_id,
                "expiry_change",
                acting_principal_id or "",
                {"expires_at": updated.expires_at},
            )
        return ControlResult(
            ok=True,
            data={
                "memory_id": memory_id,
                "search_enabled": updated.search_enabled,
                "expires_at": updated.expires_at,
            },
        )

    def get_memory_settings(self: DashboardService, acting_principal_id: str | None = None) -> MemorySettingsView:
        from raiker.memory.query_embedding import query_embedding_available
        from raiker.vector.backends import (
            MAX_MEMORY_INDEX_BATCH,
            embedding_capable_profiles,
            list_embedding_spaces,
            resolve_embedding_backend,
        )

        owner = self.store.account_scope(acting_principal_id) if acting_principal_id else None
        active = resolve_embedding_backend(self.store, owner_principal_id=owner)
        providers: list[dict[str, Any]] = []
        for offered in embedding_capable_profiles():
            item = dict(offered)
            model = str(item["space"])
            pending_memories = len(
                self.store.list_memories_missing_embedding(
                    model,
                    owner_principal_id=owner,
                    limit=MAX_MEMORY_INDEX_BATCH,
                )
            )
            remaining = max(0, MAX_MEMORY_INDEX_BATCH - pending_memories)
            pending_files = (
                len(
                    self.store.list_managed_file_chunks_missing_embedding(
                        model,
                        owner_principal_id=owner,
                        limit=remaining,
                    )
                )
                if owner and remaining
                else 0
            )
            item["unindexed_memories"] = pending_memories
            item["unindexed_file_chunks"] = pending_files
            item["pending_count"] = pending_memories + pending_files
            providers.append(item)
        return MemorySettingsView(
            incognito=self.store.is_memory_incognito(acting_principal_id),
            embedding_backend=self.store.get_memory_embedding_backend(owner),
            # A semantic *space* and semantic *recall* are two claims, and only
            # the first one is true today: the question is not embedded into the
            # space, so the vector leg is dropped and matching is still lexical.
            # The card has to say which it has, or it repeats the exact defect
            # MEM-03 was raised to remove.
            retrieval=cast(
                EmbeddingSpaceView,
                {
                    **active.describe(),
                    "query_embeddable": query_embedding_available(self.store, owner, active),
                },
            ),
            # `auto` is always offered and always resolvable; the rest are the
            # spaces that really hold vectors, so a selection can never name a
            # corpus that would answer with nothing.
            spaces=tuple(
                cast(EmbeddingSpaceView, space.describe())
                for space in list_embedding_spaces(self.store, owner_principal_id=owner)
            ),
            # Pending counts belong to a vector space, not to the current
            # recall selection. Keeping them on each offered profile means a
            # newly added memory or file remains indexable after semantic
            # recall is already active, and changing the target cannot show a
            # count for the wrong model.
            embedding_providers=tuple(cast(EmbeddingProviderView, item) for item in providers),
            # The cache rebuilds on a durable SQLite eligibility revision. This
            # names the strategy, not a live cache hit, so a fresh process never
            # presents a warm-cache performance claim it has not earned yet.
            vector_search_strategy="exact_then_approximate",
            vector_search_exact_limit=512,
            unindexed_memories=len(
                self.store.list_memories_missing_embedding(
                    active.model_label if active.semantic else None,
                    owner_principal_id=owner,
                    limit=MAX_MEMORY_INDEX_BATCH,
                )
            ),
            unindexed_file_chunks=(
                len(
                    self.store.list_managed_file_chunks_missing_embedding(
                        active.model_label if active.semantic else "__no_semantic_space__",
                        owner_principal_id=owner,
                        limit=MAX_MEMORY_INDEX_BATCH,
                    )
                )
                if owner
                else 0
            ),
        )

    def build_memory_embedding_index(
        self: DashboardService, provider: str, model: str, acting_principal_id: str | None
    ) -> ControlResult:
        """MEM-10 - embed the approved memories into a real semantic space.

        Delegated for the same reason ``create_mcp_server`` is: the capability
        gate, the policy review and the audit event live on the governed path,
        and a REST mutation that reached the executor directly would produce the
        same vectors while proving nothing about how they got there.
        """
        return self.control.build_memory_embedding_index(acting_principal_id, provider, model)

    def set_memory_embedding_backend(
        self: DashboardService, backend: str, acting_principal_id: str | None
    ) -> ControlResult:
        """Choose the embedding space recall searches (MEM-03, human-only).

        Refused rather than coerced when the named space holds no vectors: a
        selection silently downgraded to the fallback is exactly the kind of
        quiet substitution this change exists to remove.
        """
        from raiker.vector.backends import DEFAULT_SELECTION, list_embedding_spaces

        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        owner = self.store.account_scope(principal.principal_id)
        if backend != DEFAULT_SELECTION:
            known = {
                space.model_label
                for space in list_embedding_spaces(self.store, owner_principal_id=owner)
            }
            if backend not in known:
                return ControlResult(ok=False, reason_code="embedding_backend_unknown")
        self.store.set_memory_embedding_backend(backend, owner)
        return ControlResult(ok=True, data={"embedding_backend": backend})

    def set_memory_incognito(
        self: DashboardService, incognito: bool, acting_principal_id: str | None
    ) -> ControlResult:
        """Toggle the incognito opt-out boundary (human-only).

        When on, the context gatherer withholds approved project memory from
        the turn context even if a project opted in. The memory is not
        deleted — only excluded from the model's view.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        self.store.set_memory_incognito(incognito, principal.principal_id)
        return ControlResult(ok=True, data={"incognito": incognito})
