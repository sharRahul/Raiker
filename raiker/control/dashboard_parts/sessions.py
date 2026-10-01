# mypy: disable-error-code="misc"
"""Sessions, turns, events, checkpoints and the Threads work index (GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import contextlib
import json
import re
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id, utc_now
from raiker.control.dtos import ControlResult
from raiker.control.views.security import AuthError, AuthSessionView
from raiker.control.views.sessions import (
    CheckpointView,
    EventView,
    SessionDetailView,
    SessionView,
    TurnDetailView,
    TurnView,
    _stored_content_parts,
)
from raiker.control.views.threads import (
    WORK_THREAD_MAX_PAGE_LIMIT,
    WORK_THREAD_PAGE_LIMIT,
    WORK_THREAD_SCAN_LIMIT,
    WorkThreadFacet,
    WorkThreadPage,
    WorkThreadView,
    _work_thread_scope,
    decode_work_thread_cursor,
    encode_work_thread_cursor,
)
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import PrincipalType

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


#: REM-THREAD-03 — what an untitled thread of each kind is called on the work
#: board. Separate from ``SESSION_LABELS`` because that table describes a node
#: on the knowledge map, and a board row and a graph node are read differently.
WORK_THREAD_ORIGIN_NOUNS: dict[str, str] = {
    "chat": "chat",
    "build": "build session",
    "design": "design session",
}


class SessionService:

    def list_sessions(
        self: DashboardService,
        limit: int = 50,
        project_id: str | None = None,
        user_id: str | None = None,
        include_archived: bool = False,
        origin: str | None = None,
    ) -> list[SessionView]:
        """List the caller's sessions, newest first.

        ``origin`` filters by provenance (BUG-10): ``"chat"`` is the owner's own
        conversations, which is what a "recent chats" list means. Omitting it
        lists every session, so Sessions still shows task runs.
        """
        return [
            self._session_view(row)
            for row in self.store.list_sessions(
                limit=limit,
                project_id=project_id,
                user_id=user_id,
                include_archived=include_archived,
                origin=origin,
            )
        ]

    def get_session(self: DashboardService, session_id: str, user_id: str | None = None) -> SessionDetailView | None:
        row = self.store.load_session(session_id)
        if row is None:
            return None
        # Isolation: an account cannot read another account's session. Legacy
        # sessions (no owner) remain visible to any authenticated account.
        owner = row.get("user_id")
        if user_id is not None and owner is not None and str(owner) != user_id:
            return None
        turns = tuple(self._turn_view(t) for t in self.store.list_turns(session_id))
        return SessionDetailView(session=self._session_view(row), turns=turns)


    def build_session_transcript(
        self: DashboardService,
        session_id: str,
        *,
        user_id: str | None,
        principal_id: str | None,
    ) -> Any | None:
        """A redacted, scoped transcript ready to render, or None if not visible.

        Visibility is the existing session boundary — this reads through
        ``get_session``, so an export can never reach a conversation the caller
        could not already open. Attachment metadata is folded in so the review
        step can name every file the transcript will list.
        """
        from raiker.sessions.transcript import build_transcript

        detail = self.get_session(session_id, user_id=user_id)
        if detail is None:
            return None
        files: list[Any] = []
        if principal_id:
            with contextlib.suppress(Exception):
                from raiker.runtime.attachment_preview import AttachmentPreviewService

                files = list(
                    AttachmentPreviewService(self.store).list_session_files(
                        session_id, principal_id
                    )
                )
        sources_by_turn: dict[str, list[dict[str, Any]]] = {}
        if principal_id:
            with contextlib.suppress(Exception):
                for source in self.store.load_turn_sources(session_id, principal_id):
                    sources_by_turn.setdefault(str(source.get("turn_id", "")), []).append(source)
        return build_transcript(
            session_id=session_id,
            title=detail.session.title or "Untitled conversation",
            created_at=detail.session.created_at,
            turns=detail.turns,
            files=files,
            sources_by_turn=sources_by_turn,
        )

    def record_transcript_export(
        self: DashboardService,
        session_id: str,
        *,
        acting_principal_id: str,
        export_format: str,
        message_count: int,
        file_count: int,
        byte_size: int,
    ) -> None:
        """Audit that a transcript left the runtime. Metadata only, never text."""
        from raiker.contracts.models import AgentEvent
        from raiker.sessions.transcript import REDACTION_POLICY

        with contextlib.suppress(Exception):
            EventLogWriter(self.store).append(
                AgentEvent(
                    event_id=new_id("evt_"),
                    timestamp=utc_now(),
                    session_id=session_id,
                    turn_id=None,
                    event_type="session_transcript_exported",
                    actor=acting_principal_id,
                    payload={
                        "format": export_format,
                        "message_count": message_count,
                        "file_count": file_count,
                        "byte_size": byte_size,
                        "redaction_policy": REDACTION_POLICY,
                    },
                )
            )

    def search_sessions(self: DashboardService, query: str, user_id: str | None = None) -> list[SessionView]:
        return [
            self._session_view(row) for row in self.store.search_sessions(query.strip(), user_id)
        ]

    def get_turn(self: DashboardService, turn_id: str, user_id: str | None = None) -> TurnDetailView | None:
        row = self.store.load_turn(turn_id)
        if row is None:
            return None
        session = self.store.load_session(str(row["session_id"]))
        if session is None:
            return None
        owner = session.get("user_id")
        if user_id is not None and owner is not None and str(owner) != user_id:
            return None
        events = tuple(
            self._event_view(e) for e in self.store.list_event_index(turn_id=turn_id, limit=500)
        )
        return TurnDetailView(turn=self._turn_view(row), events=events)

    # These are organizing actions, governance-neutral like projects: pinning
    # or deleting a session grants nothing and changes no gate, policy, or
    # authority. Deletion is human-only and respects the same user/session
    # visibility boundary as every governed read — an account cannot delete
    # another account's session, and legacy unattributed sessions remain
    # deletable by any authenticated human.

    def set_session_pinned(
        self: DashboardService,
        session_id: str,
        pinned: bool,
        acting_principal_id: str | None,
    ) -> ControlResult:
        """Pin (or unpin) a session for the authenticated local human.

        Pinned sessions surface first in the Sessions list. Pinning is an
        organizing label only — it grants nothing.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        if not self.store.set_session_pinned(session_id, pinned, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        return ControlResult(ok=True, data={"session_id": session_id, "pinned": pinned})

    # Renaming and archiving are organizing actions only — they grant nothing
    # and change no gate, policy, or authority. Both are human-only and respect
    # the same user/session visibility boundary as set_session_pinned: an
    # account cannot rename or archive another account's session. Archiving is
    # reversible and never deletes transcripts, events, checkpoints, or
    # permissions; deletion remains a separate, confirmed, destructive path.

    _TITLE_MAX_LEN = 200

    def _normalize_title(self: DashboardService, title: str) -> tuple[str | None, str | None]:
        """Return (normalized_title, reason_code). reason_code is None when the
        title is acceptable. Trim, collapse internal whitespace (so control
        characters and newlines cannot smuggle into a display label), reject
        empty, and cap length."""
        if not isinstance(title, str):
            return None, "invalid_title:not_a_string"
        normalized = re.sub(r"\s+", " ", title.strip())
        if not normalized:
            return None, "invalid_title:empty"
        if len(normalized) > self._TITLE_MAX_LEN:
            return None, f"invalid_title:too_long:{len(normalized)}"
        return normalized, None

    def rename_session(
        self: DashboardService, session_id: str, title: str, acting_principal_id: str | None
    ) -> ControlResult:
        """Rename one session (human-only).

        The title is normalized (trim, collapse whitespace, length cap) and
        rejected with ``invalid_title:*`` when empty or too long. Renaming is an
        organizing label only — it grants nothing. Respects user/session
        visibility: an account cannot rename another account's session.
        """
        normalized, reason = self._normalize_title(title)
        if reason is not None or normalized is None:
            return ControlResult(ok=False, reason_code=reason)
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        session = self.store.load_session(session_id)
        previous_title = str(session["title"]) if session and session.get("title") else None
        if not self.store.rename_session(session_id, normalized, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        from raiker.events.types import make_event

        EventLogWriter(self.store).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type="session_renamed",
                actor="dashboard_service",
                payload={
                    "session_id": session_id,
                    "from_title": previous_title,
                    "to_title": normalized,
                },
            )
        )
        return ControlResult(ok=True, data={"session_id": session_id, "title": normalized})

    def set_session_archived(
        self: DashboardService, session_id: str, archived: bool, acting_principal_id: str | None
    ) -> ControlResult:
        """Archive or restore one session (human-only).

        Archiving moves a chat out of the default active list and is fully
        reversible; it never deletes transcripts, events, checkpoints, or
        permissions. Respects user/session visibility: an account cannot
        archive another account's session.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        if not self.store.set_session_archived(session_id, archived, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        from raiker.events.types import make_event

        EventLogWriter(self.store).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type="session_archived" if archived else "session_unarchived",
                actor="dashboard_service",
                payload={"session_id": session_id, "archived": archived},
            )
        )
        if archived:
            self._dispatch_session_end_hook(session_id, "archived")
        return ControlResult(ok=True, data={"session_id": session_id, "archived": archived})

    def delete_session(self: DashboardService, session_id: str, acting_principal_id: str | None) -> ControlResult:
        """Permanently delete one session and its cascaded rows (human-only).

        Respects user/session visibility: an account cannot delete another
        account's session. The per-session events transcript file is removed.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        # Before the row goes, so a handler can still read what it is told about.
        self._dispatch_session_end_hook(session_id, "deleted")
        if not self.store.delete_session(session_id, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        return ControlResult(ok=True, data={"session_id": session_id})

    def delete_sessions(
        self: DashboardService, session_ids: list[str], acting_principal_id: str | None
    ) -> ControlResult:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        for session_id in session_ids:
            self._dispatch_session_end_hook(session_id, "deleted")
        if not self.store.delete_sessions(session_ids, user_id=principal.delegated_by_user_id):
            return ControlResult(ok=False, reason_code="unknown_or_unauthorized_session")
        return ControlResult(ok=True, data={"session_ids": session_ids})

    def set_session_project(
        self: DashboardService, session_id: str, project_id: str | None, acting_principal_id: str | None
    ) -> ControlResult:
        """Move one chat into a project, or out of every project (human-only).

        A project is an organizing scope: the move grants nothing and changes
        no gate, policy, or authority. It changes only the bounded context the
        chat receives — project instructions, shared attachments, and the
        opt-in approved-memory boundary. Moving out (``project_id=None``)
        removes all of it from the next turn's context. Respects user/session
        visibility: an account cannot move another account's chat.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = self.store.principal_user_id(principal.principal_id)
        if project_id is not None and self.store.load_project(project_id, user_id=user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        session = self.store.load_session(session_id)
        previous_project_id = (
            str(session["project_id"]) if session and session.get("project_id") else None
        )
        if not self.store.set_session_project(session_id, project_id, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        from raiker.events.types import make_event

        EventLogWriter(self.store).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type="session_project_changed",
                actor="dashboard_service",
                payload={
                    "session_id": session_id,
                    "from_project_id": previous_project_id,
                    "to_project_id": project_id,
                },
            )
        )
        return ControlResult(ok=True, data={"session_id": session_id, "project_id": project_id})

    # A tag is an organizing label only (like the per-session `pinned` flag
    # and the `projects` table) — it grants nothing and changes no gate,
    # policy, or authority. Mutations are human-only and respect the same
    # user/session visibility boundary as set_session_pinned / delete_session
    # — an account cannot retag another account's session. Normalization is
    # applied here so the storage layer never sees an unvalidated tag: trim,
    # collapse internal whitespace, lowercase, allow `[a-z0-9][a-z0-9 _-]*`,
    # 1..32 chars each, max 12 tags per session, dedupe, drop empties.

    _TAG_MAX_LEN = 32
    _TAG_MAX_COUNT = 12
    _TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9 &._-]*$")

    def _normalize_tags(self: DashboardService, tags: list[str]) -> tuple[tuple[str, ...], str | None]:
        """Return (normalized, reason_code). reason_code is None when the
        tag set is acceptable."""
        seen: set[str] = set()
        out: list[str] = []
        for raw in tags:
            if not isinstance(raw, str):
                return (), "invalid_tag:not_a_string"
            tag = re.sub(r"\s+", " ", raw.strip()).lower()
            if not tag:
                continue
            if len(tag) > self._TAG_MAX_LEN:
                return (), f"invalid_tag:too_long:{tag[:16]}"
            if not self._TAG_PATTERN.match(tag):
                return (), f"invalid_tag:bad_chars:{tag[:16]}"
            if tag not in seen:
                seen.add(tag)
                out.append(tag)
        if len(out) > self._TAG_MAX_COUNT:
            return (), f"invalid_tag:too_many:{len(out)}"
        return tuple(out), None

    def set_session_tags(
        self: DashboardService,
        session_id: str,
        tags: list[str],
        acting_principal_id: str | None,
    ) -> ControlResult:
        """Replace the tag set for one session (human-only).

        Tags are organizing labels only — they grant nothing. The supplied
        list is normalized (trim, lowercase, dedupe, length/count caps) and
        stored as the session's full tag set. Respects user/session
        visibility: an account cannot retag another account's session.
        """
        normalized, reason = self._normalize_tags(tags)
        if reason is not None:
            return ControlResult(ok=False, reason_code=reason)
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        if not self.store.set_session_tags(session_id, list(normalized), user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        return ControlResult(
            ok=True,
            data={"session_id": session_id, "tags": list(normalized)},
        )

    def list_events(
        self: DashboardService,
        session_id: str | None = None,
        turn_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        user_id: str | None = None,
    ) -> list[EventView]:
        rows = self.store.list_event_index(
            session_id=session_id, turn_id=turn_id, event_type=event_type, limit=limit
        )
        if user_id is None:
            return [self._event_view(r) for r in rows]
        # Archiving a session never hides its events (archive is not delete), so
        # the visibility set spans the owner's active and archived sessions.
        visible_session_ids = {
            str(session["session_id"])
            for session in self.store.list_sessions(
                limit=10_000, user_id=user_id, include_archived=True
            )
        }
        # BUG-87 — the audit log is account-scoped, not conversation-scoped.
        # Governed steps taken outside any conversation — connecting a
        # credential, pinning a model, resolving a principal — are recorded on
        # runtime channels (`terminal-local`, `authz`) that are not sessions at
        # all. Filtering on the owner's session set alone dropped every one of
        # them, so the page an owner opens to confirm those exact steps showed
        # "No events match" with no filters set.
        #
        # A row is visible when it belongs to one of the owner's own sessions,
        # or to no session record at all. The second clause cannot leak another
        # user's conversation: their sessions are session records, so they fail
        # it and stay filtered.
        conversation_ids = self.store.all_session_ids()
        return [
            self._event_view(row)
            for row in rows
            if str(row.get("session_id")) in visible_session_ids
            or str(row.get("session_id")) not in conversation_ids
        ]

    def list_checkpoints(
        self: DashboardService,
        session_id: str | None = None,
        limit: int = 50,
        project_id: str | None = None,
        user_id: str | None = None,
    ) -> list[CheckpointView]:
        return [
            self._checkpoint_view(r)
            for r in self.store.list_checkpoints(session_id, limit=limit, project_id=project_id)
            if (session := self.store.load_session(str(r["session_id"]))) is not None
            and (user_id is None or session.get("user_id") == user_id)
        ]

    def get_checkpoint(
        self: DashboardService, checkpoint_id: str, user_id: str | None = None
    ) -> CheckpointView | None:
        row = self.store.load_checkpoint_by_id(checkpoint_id)
        if row is None:
            return None
        session = self.store.load_session(str(row["session_id"]))
        if session is None or (user_id is not None and session.get("user_id") != user_id):
            return None
        return self._checkpoint_view(row)

    def get_session_context(self: DashboardService, session_id: str) -> dict:
        """Return the session's effective project context (ancestors merged in).

        This is the same merge the live context gatherer applies, so what the
        dashboard shows is what the model sees.
        """
        session = self.store.load_session(session_id)
        if session is None:
            return {}
        project_id = session.get("project_id")
        if not project_id:
            return {}
        return self.store.load_effective_project_context(str(project_id))

    def list_work_threads(
        self: DashboardService,
        *,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkThreadView]:
        """The unfiltered first page, kept for callers that want exactly that.

        Home reads this: it wants the newest few threads to offer as somewhere
        to continue, and has no filters to apply. :meth:`work_thread_page` is
        the index behind Threads.
        """
        return self.work_thread_page(user_id=user_id, limit=limit).threads

    def _all_work_threads(
        self: DashboardService, *, user_id: str | None, include_archived: bool = False
    ) -> tuple[list[WorkThreadView], bool]:
        """Every thread of this owner's work, newest first (GAP-CHAT C18).

        Two kinds, in one list, because the owner has one head:

        * **Chats** they started, with the project each sits in — which is the
          "cross-project view" the gap named. It was absent not because projects
          were unknown but because nothing joined them to the conversation list.
        * **Routine threads** a task is advancing (C11). Before those existed
          there was nothing to resume: a routine's cycles ran in a hidden Inbox
          transcript. Now each routine owns a conversation, and this is where an
          owner finds it without going through Tasks first.

        ``waiting_on`` states only a blocker the runtime is actually holding —
        an approval a task is parked on. A thread nobody is waiting on says so by
        saying nothing, rather than by having a staleness heuristic invented for
        it.
        """
        projects = {
            project.project_id: project.name
            for project in self.list_projects(user_id=user_id).projects
        }
        threads: list[WorkThreadView] = []
        # REM-THREAD-03 — every conversation the owner started, on whichever
        # surface they started it: naming `chat` would drop Build and Design from
        # the one board that claims to show all the work. The complement of the
        # server-owned sessions a task run executes in, which arrive below as
        # routine threads.
        # BUG-303 — archived threads are listable here, because a control whose
        # effect the owner cannot see or undo from the same surface is worse than
        # none; which of the two scopes is shown is `work_thread_page`'s decision.
        owner_sessions = self.store.list_sessions(
            limit=WORK_THREAD_SCAN_LIMIT,
            user_id=user_id,
            include_archived=include_archived,
            exclude_origin="task",
        )
        # Found 2026-09-18 while proving REM-THREAD-03: every chat row on the
        # board said "0 turns". `list_sessions` selects the session row, which
        # has no turn count in it, so `session.get("turn_count")` had always
        # been `None` and every conversation was reported as empty — beside
        # routine rows that had a real count, because those were counted. One
        # query for the whole page, exactly as the routine half already does.
        session_ids = [str(session.get("session_id", "")) for session in owner_sessions]
        session_turns = self.store.count_turns_by_session(session_ids)
        # One query for the page's tags, not one per row: the library controls
        # draw a tag editor on every thread (BUG-303).
        session_tags = self.store.list_session_tags_by_session(session_ids)
        for session in owner_sessions:
            session_id = str(session.get("session_id", ""))
            project_id = session.get("project_id")
            origin = str(session.get("origin") or "chat").lower()
            threads.append(
                WorkThreadView(
                    session_id=session_id,
                    title=str(session.get("title") or "").strip()
                    or f"Untitled {WORK_THREAD_ORIGIN_NOUNS.get(origin, 'chat')}",
                    kind="chat",
                    updated_at=str(session.get("updated_at", "")),
                    turn_count=session_turns.get(session_id, 0),
                    project_id=project_id,
                    project_name=projects.get(str(project_id)) if project_id else None,
                    origin=origin,
                    pinned=bool(session.get("pinned")),
                    archived=bool(session.get("archived")),
                    tags=tuple(session_tags.get(session_id, ())),
                )
            )
        # A routine thread's identity comes from its task, not from its session:
        # the task is what carries the cadence, the status and the next slot, and
        # it is what the owner recognises the thread by.
        tasks = [
            task
            for task in self.store.list_tasks(user_id=user_id)
            if task.thread_session_id and not getattr(task, "parent_turn_id", None)
        ]
        turns = self.store.count_turns_by_session(
            [str(task.thread_session_id) for task in tasks]
        )
        for task in tasks:
            session_id = str(task.thread_session_id)
            count = turns.get(session_id, 0)
            if count == 0:
                # A routine that has not run has no thread to resume. Listing it
                # would put a link to an empty transcript in a list whose whole
                # promise is that every row is somewhere to continue.
                continue
            threads.append(
                WorkThreadView(
                    session_id=session_id,
                    title=task.title,
                    kind="routine",
                    updated_at=task.updated_at,
                    turn_count=count,
                    project_id=task.project_id,
                    project_name=(
                        projects.get(str(task.project_id)) if task.project_id else None
                    ),
                    task_id=task.task_id,
                    task_status=task.status,
                    cadence=task.recurrence,
                    next_run_at=task.scheduled_at,
                    # REM-THREAD-03 — a routine's thread is resumed on the
                    # surface the routine works on. The task has recorded that
                    # since it was filed; its session cannot say so, because
                    # every task session's origin is `task` by construction.
                    origin=(task.surface or "chat").lower(),
                    waiting_on=(
                        "Waiting for your approval"
                        if task.status == "waiting_for_approval"
                        else None
                    ),
                )
            )
        # Pinned first, then newest. BUG-303 — a pin that does not change where
        # a thread appears is a label, not a pin, and the library control being
        # moved here is the one Sessions had: "keep this where I can find it".
        #
        # Stable, with a tie-breaker: two threads touched in the same second
        # must not swap places between pages, or a cursor would skip one and
        # repeat the other.
        threads.sort(
            key=lambda thread: (thread.pinned, thread.updated_at, thread.session_id),
            reverse=True,
        )
        return threads, len(threads) >= WORK_THREAD_SCAN_LIMIT

    def work_thread_page(
        self: DashboardService,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
        kind: str | None = None,
        query: str = "",
        cursor: str | None = None,
        limit: int = WORK_THREAD_PAGE_LIMIT,
        archived: bool = False,
    ) -> WorkThreadPage:
        """One page of the owner's work, with the filters that produced it.

        NEW-THREAD-01. The order is the whole point and it is the order Threads
        could not perform in a browser: **filter, then facet over everything
        that matched, then page.** Facets computed over a page can only ever
        offer what is already on screen, which is how a project whose newest
        thread fell outside the first hundred rows stopped existing as a filter.

        A blank ``query`` is not a filter. A query *with* a project selected
        keeps the project — narrowing something down must not widen it, which is
        what an unscoped search on the first keystroke did.

        BUG-303 — ``archived`` is a *scope*, not a filter, which is why it sits
        outside the facets: the two sets do not overlap, and every other filter
        applies within whichever one is being read. Both counts come back either
        way, so archiving a thread from this page leaves somewhere visible to
        go and get it back from.

        One scan covers both scopes rather than two, because the counts have to
        agree with each other and with what is on screen. The cost is that
        ``WORK_THREAD_SCAN_LIMIT`` is now shared: a workspace with thousands of
        archived threads sees fewer active ones considered. Sessions are scanned
        newest-first and an archived thread is by definition one the owner has
        finished with, so they sit at the tail of that order — and when the
        bound does bind, ``scan_truncated`` says so rather than letting the
        counts read as an inventory.
        """
        size = max(1, min(int(limit or WORK_THREAD_PAGE_LIMIT), WORK_THREAD_MAX_PAGE_LIMIT))
        needle = (query or "").strip().casefold()
        every, truncated = self._all_work_threads(user_id=user_id, include_archived=True)
        archived_count = sum(1 for thread in every if thread.archived)
        active_count = len(every) - archived_count
        every = [thread for thread in every if thread.archived == archived]

        def matches(
            thread: WorkThreadView, *, ignore_project: bool = False, ignore_kind: bool = False
        ) -> bool:
            if not ignore_project and project_id is not None and thread.project_id != project_id:
                return False
            if not ignore_kind and kind is not None and thread.kind != kind:
                return False
            return not (needle and needle not in thread.title.casefold())

        # Each facet is computed with its own filter lifted, so every choice
        # stays reachable from every other. A project facet that respected the
        # project filter would offer exactly one project: the one already on.
        project_counts: dict[str, int] = {}
        project_labels: dict[str, str] = {}
        kind_counts: dict[str, int] = {}
        for thread in every:
            if matches(thread, ignore_project=True) and thread.project_id:
                key = str(thread.project_id)
                project_counts[key] = project_counts.get(key, 0) + 1
                project_labels.setdefault(key, thread.project_name or key)
            if matches(thread, ignore_kind=True):
                kind_counts[thread.kind] = kind_counts.get(thread.kind, 0) + 1

        matched = [thread for thread in every if matches(thread)]
        scope = _work_thread_scope(user_id, project_id, kind, needle, archived)
        start = 0
        if cursor:
            after = decode_work_thread_cursor(cursor, scope)
            if after is not None:
                for index, thread in enumerate(matched):
                    if (thread.updated_at, thread.session_id) == after:
                        start = index + 1
                        break
        page = matched[start : start + size]
        more = start + size < len(matched)
        return WorkThreadPage(
            threads=page,
            next_cursor=encode_work_thread_cursor(page[-1], scope) if page and more else None,
            total=len(matched),
            projects=[
                WorkThreadFacet(value=key, label=project_labels[key], count=count)
                for key, count in sorted(
                    project_counts.items(), key=lambda item: (-item[1], project_labels[item[0]])
                )
            ],
            kinds=[
                WorkThreadFacet(value=key, label=key, count=count)
                for key, count in sorted(kind_counts.items())
            ],
            archived_count=archived_count,
            active_count=active_count,
            scan_truncated=truncated,
        )

    def mint_owner_session(self: DashboardService, as_principal: str | None = None) -> AuthSessionView | AuthError:
        from raiker.api.sessions import ApiSessionStore
        from raiker.cli.principal_resolver import resolve_local_principal

        principal, error = resolve_local_principal(self.workspace_root, as_principal)
        if principal is None:
            return AuthError(reason_code="no_local_owner", message=error)
        if principal.principal_type != PrincipalType.HUMAN:
            return AuthError(
                reason_code="ai_principal_not_allowed",
                message="AI principals cannot mint a session.",
            )
        raw_token, session = ApiSessionStore(self.workspace_root).create_session(
            principal.principal_id
        )
        return AuthSessionView(
            token=raw_token,
            session_id=session.session_id,
            principal_id=principal.principal_id,
            expires_at=session.expires_at,
        )

    def _session_view(self: DashboardService, row: dict[str, Any]) -> SessionView:
        session_id = str(row["session_id"])
        return SessionView(
            session_id=session_id,
            title=row.get("title"),
            status=str(row.get("status", "")),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
            turn_count=len(self.store.list_turns(session_id, limit=1000)),
            pinned=bool(row.get("pinned", 0)),
            tags=tuple(self.store.list_session_tags(session_id)),
            project_id=row.get("project_id"),
            archived=bool(row.get("archived", 0)),
            archived_at=row.get("archived_at"),
            origin=str(row.get("origin") or "chat"),
            match_snippet=str(row.get("match_snippet") or ""),
            match_turn_id=str(row.get("match_turn_id") or ""),
        )

    def _turn_view(self: DashboardService, row: dict[str, Any]) -> TurnView:
        return TurnView(
            turn_id=str(row["turn_id"]),
            session_id=str(row["session_id"]),
            turn_type=str(row.get("turn_type", "")),
            status=str(row.get("status", "")),
            prompt_text=row.get("prompt_text"),
            created_at=str(row.get("created_at", "")),
            completed_at=row.get("completed_at"),
            summary=row.get("summary"),
            reasoning_chars=int(row.get("reasoning_chars") or 0),
            reasoning=row.get("reasoning_text"),
            tool_rows=self._turn_tool_rows(str(row["session_id"]), str(row.get("turn_id") or "")),
            content_parts=_stored_content_parts(row.get("summary")),
        )

    #: How a stored action's status reads as a transcript row. `proposed` is a
    #: call that never settled - the live view shows the same fact as a row that
    #: never stopped running, and a reload should not invent a different answer.
    _STORED_ROW_STATES = {
        "success": "success",
        "failed": "failed",
        "denied": "denied",
        "approval_required": "waiting",
        "proposed": "running",
    }

    def _turn_tool_rows(self: DashboardService, session_id: str, turn_id: str) -> tuple[dict[str, Any], ...]:
        """Backlog #25 - the turn's tool calls, as the transcript showed them.

        Read from ``tool_actions``, whose arguments were already redacted by the
        broker before they were stored, and rendered through the same
        :func:`raiker.tools.presentation.tool_row` the live stream uses. Two
        consequences worth stating: the reloaded row carries exactly the family,
        label and action phrase the live one did, and it cannot carry more,
        because it is the same function over an already-redacted record.
        """
        from raiker.tools.presentation import tool_row

        rows: list[dict[str, Any]] = []
        for stored in self.store.list_turn_tool_actions(session_id, turn_id):
            try:
                arguments = json.loads(str(stored.get("arguments_json") or "{}"))
            except (TypeError, ValueError):  # pragma: no cover - unreadable row
                arguments = {}
            tool_name = str(stored.get("tool_name") or "")
            if not tool_name:
                continue
            rows.append(
                {
                    "action_id": str(stored.get("action_id") or ""),
                    **tool_row(
                        tool_name, arguments if isinstance(arguments, dict) else {}
                    ).to_payload(),
                    "status": self._STORED_ROW_STATES.get(
                        str(stored.get("status") or ""), "running"
                    ),
                }
            )
        return tuple(rows)

    @staticmethod
    def _event_view(row: dict[str, Any]) -> EventView:
        from raiker.control.dashboard import DashboardService

        machine_identity = (
            DashboardService._proposal_identity(row) if row.get("proposed_by") else None
        )
        return EventView(
            event_id=str(row["event_id"]),
            session_id=str(row.get("session_id", "")),
            turn_id=row.get("turn_id"),
            event_type=str(row.get("event_type", "")),
            actor=str(row.get("actor", "")),
            timestamp=str(row.get("timestamp", "")),
            risk_level=row.get("risk_level"),
            summary=row.get("summary"),
            machine_identity=machine_identity,
        )

    @staticmethod
    def _checkpoint_view(row: dict[str, Any]) -> CheckpointView:
        return CheckpointView(
            checkpoint_id=str(row["checkpoint_id"]),
            session_id=str(row.get("session_id", "")),
            turn_id=row.get("turn_id"),
            task_id=row.get("task_id"),
            checkpoint_type=str(row.get("checkpoint_type", "")),
            created_at=str(row.get("created_at", "")),
            summary=row.get("summary"),
            last_event_id=row.get("last_event_id"),
            can_restore_state=bool(row.get("can_restore_state", 0)),
            can_restore_files=bool(row.get("can_restore_files", 0)),
        )
