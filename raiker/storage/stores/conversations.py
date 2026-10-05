# mypy: disable-error-code="misc"
"""Sessions, turns, the event index, tool actions and what a turn read and was
recalled — the persisted shape of a conversation (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import AgentEvent, PolicyDecision, ToolAction
from raiker.models.session_state import ModelSessionState
from raiker.storage.deletion_journal import SESSION_DELETE, record_deletion
from raiker.storage.migrations import TEXT_SEARCH_FTS5
from raiker.storage.sqlite import _SEARCH_STOPWORDS

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class ConversationStore:

    def create_session(
        self: SQLiteStore,
        session_id: str,
        project_root: str,
        title: str | None = None,
        user_id: str | None = None,
        origin: str = "chat",
    ) -> None:
        now = utc_now()
        # New sessions are stamped with the active project (if any) so project
        # scoping needs no caller changes — an organizing label, not authority.
        project_id = self.get_active_project(user_id)
        # `origin` records where the session came from ("chat" for a typed
        # conversation, "task" for the server-owned session a task runs in). A
        # provenance label only: it grants nothing and hides nothing, it just
        # lets a "recent conversations" list mean conversations (BUG-10).
        self._execute(
            """
            INSERT OR IGNORE INTO sessions
            (session_id, project_root, created_at, updated_at, status, title, user_id, project_id, origin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, project_root, now, now, "open", title, user_id, project_id, origin),
        )

    def set_session_origin(self: SQLiteStore, session_id: str, origin: str) -> None:
        """Stamp an existing session's provenance.

        ``create_session`` is an INSERT OR IGNORE, so a session that predates the
        origin column (or this caller) keeps the default 'chat'. Task creation
        calls this so an Inbox created before the fix stops reading as a
        conversation. Provenance only — no gate, policy, or visibility changes.
        """
        self._execute("UPDATE sessions SET origin = ? WHERE session_id = ?", (origin, session_id))

    def load_session(self: SQLiteStore, session_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        return dict(row) if row else None

    def list_sessions(
        self: SQLiteStore,
        limit: int = 10,
        project_id: str | None = None,
        user_id: str | None = None,
        include_archived: bool = False,
        origin: str | None = None,
        exclude_origin: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM sessions"
        params: list[Any] = []
        conditions: list[str] = []
        if origin is not None:
            # Provenance filter (BUG-10): "chat" is the owner's conversations.
            # Legacy rows written before the column existed default to 'chat'.
            conditions.append("origin = ?")
            params.append(origin)
        if exclude_origin is not None:
            # REM-THREAD-03 — the complement, for a caller that wants every
            # conversation the *owner* started whatever surface they started it
            # on. Naming one origin to leave out is honest about what it does;
            # naming `chat` to keep in silently dropped Build and Design once
            # sessions began recording which surface opened them.
            conditions.append("COALESCE(origin, 'chat') <> ?")
            params.append(exclude_origin)
        if not include_archived:
            # Default listing surfaces active sessions only; archived rows stay
            # retrievable by an explicit ``include_archived`` request.
            conditions.append("archived = 0")
        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)
        if user_id is not None:
            # An account sees its own sessions plus legacy/unattributed ones
            # (user_id IS NULL); another account's sessions stay hidden.
            conditions.append("(user_id = ? OR user_id IS NULL)")
            params.append(user_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def search_sessions(
        self: SQLiteStore, query: str, user_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Conversations matching *query*, each carrying the exchange that matched.

        RAIKER-2020: the title still matches on its own, but the message-body half
        now goes through ``conversation_fts`` instead of an unindexed
        ``LIKE '%term%'`` over every turn the owner has ever taken. The row keeps
        the shape it had and gains ``match_snippet`` / ``match_turn_id``, so the
        result list can say *why* a conversation matched rather than only that it
        did — which is the difference between finding a chat from years ago and
        recognising it.
        """
        stripped = query.strip()
        if not stripped:
            return []
        matched: dict[str, dict[str, Any]] = {}
        for hit in self.search_conversation_turns(stripped, user_id=user_id, limit=limit):
            matched.setdefault(
                str(hit["session_id"]),
                {"turn_id": str(hit["turn_id"]), "snippet": str(hit.get("snippet") or "")},
            )
        placeholders = ",".join("?" * len(matched)) if matched else "SELECT NULL"
        conditions = [f"(sessions.title LIKE ? OR sessions.session_id IN ({placeholders}))"]
        params: list[Any] = [f"%{stripped}%", *sorted(matched)]
        if user_id is not None:
            conditions.append("(sessions.user_id = ? OR sessions.user_id IS NULL)")
            params.append(user_id)
        rows = self._rows(
            "SELECT sessions.* FROM sessions WHERE "
            + " AND ".join(conditions)
            + " ORDER BY sessions.updated_at DESC LIMIT ?",
            [*params, limit],
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            hit = matched.get(str(record.get("session_id")), {})
            record["match_snippet"] = " ".join(str(hit.get("snippet", "")).split())[:300]
            record["match_turn_id"] = hit.get("turn_id", "")
            results.append(record)
        return results


    @staticmethod
    def _mcp_session_log_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        raw = data.get("hosts_json")
        try:
            data["hosts"] = json.loads(raw) if isinstance(raw, str) else []
        except (TypeError, ValueError):
            data["hosts"] = []
        return data

    def insert_mcp_session_log(
        self: SQLiteStore,
        *,
        server_id: str | None,
        principal_id: str,
        transport: str,
        operation: str,
        hosts: list[str],
        tool_calls: int,
        bytes_in: int,
        bytes_out: int,
        error_count: int,
        outcome: str,
        started_at: str,
        ended_at: str | None = None,
    ) -> str:
        """Append one redacted per-session monitoring row for a connection.

        Stores only metadata — the tool-call count, the hosts contacted (netloc
        only), byte counts, error count, and outcome. No payload, token, or host
        secret is ever written here. Owner-scoped by ``principal_id``.
        """
        session_row_id = new_id("mses_")
        self._execute(
            """INSERT INTO mcp_session_log
               (session_row_id, server_id, principal_id, transport, operation,
                hosts_json, tool_calls, bytes_in, bytes_out, error_count,
                outcome, started_at, ended_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_row_id,
                server_id,
                principal_id,
                transport,
                operation,
                json.dumps(list(hosts)),
                int(tool_calls),
                int(bytes_in),
                int(bytes_out),
                int(error_count),
                outcome,
                started_at,
                ended_at,
            ),
        )
        return session_row_id

    def list_mcp_session_logs(
        self: SQLiteStore, server_id: str | None, principal_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Owner-scoped, most-recent-first session rows for one connection. A
        different owner (or a null server_id) resolves nothing, so a baseline can
        never be read across owners."""
        if not server_id:
            return []
        rows = self._rows(
            """SELECT * FROM mcp_session_log
               WHERE principal_id = ? AND server_id = ?
               ORDER BY started_at DESC, rowid DESC LIMIT ?""",
            (principal_id, server_id, int(limit)),
        )
        return [self._mcp_session_log_row(row) for row in rows]

    def _session_owner(
        self: SQLiteStore, connection: sqlite3.Connection, session_id: str
    ) -> tuple[bool, str | None]:
        """Return (exists, owner_user_id). ``exists`` is False when the session
        does not exist; ``owner`` is None for legacy unattributed sessions."""
        row = connection.execute(
            "SELECT user_id FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return False, None
        return True, dict(row).get("user_id")

    def _update_owned_session(
        self: SQLiteStore, session_id: str, user_id: str | None, assignments: dict[str, Any]
    ) -> bool:
        """Apply column assignments to one session under the owner check shared
        by every session mutator. Returns False when the session does not exist
        or is owned by another account (legacy unowned sessions stay writable by
        any authenticated account, mirroring set_session_pinned). ``updated_at``
        is always refreshed. Column names come only from trusted call sites."""
        if not assignments:
            return False
        with self.connect() as connection:
            exists, owner = self._session_owner(connection, session_id)
            if not exists:
                return False
            if user_id is not None and owner is not None and str(owner) != user_id:
                return False
            columns = ", ".join(f"{column} = ?" for column in assignments)
            connection.execute(
                f"UPDATE sessions SET {columns}, updated_at = ? WHERE session_id = ?",
                (*assignments.values(), utc_now(), session_id),
            )
        return True

    def rename_session(self: SQLiteStore, session_id: str, title: str, user_id: str | None = None) -> bool:
        """Set one session's title. The caller supplies the already-normalized
        title. Returns False if the session does not exist or is owned by
        another account (isolation mirrors set_session_pinned)."""
        return self._update_owned_session(session_id, user_id, {"title": title})

    def set_session_archived(
        self: SQLiteStore, session_id: str, archived: bool, user_id: str | None = None
    ) -> bool:
        """Soft-archive (or restore) one session — a reversible organizing state
        that never deletes transcripts, events, checkpoints, or permissions.
        ``archived_at`` records the archive time and clears on restore. Returns
        False if the session does not exist or is owned by another account
        (isolation mirrors set_session_pinned)."""
        return self._update_owned_session(
            session_id,
            user_id,
            {"archived": int(archived), "archived_at": utc_now() if archived else None},
        )

    def set_session_project(
        self: SQLiteStore, session_id: str, project_id: str | None, user_id: str | None = None
    ) -> bool:
        """Move one session into a project, or out of every project with
        ``project_id=None``. Returns False if the session does not exist or is
        owned by another account (user isolation mirrors set_session_pinned).
        The caller validates that ``project_id`` names a real project — a
        project is an organizing scope, so the move grants nothing; it only
        changes the bounded context the chat receives."""
        with self.connect() as connection:
            exists, owner = self._session_owner(connection, session_id)
            if not exists:
                return False
            if user_id is not None and owner is not None and str(owner) != user_id:
                return False
            if project_id is not None:
                project = connection.execute(
                    "SELECT owner_user_id FROM projects WHERE project_id = ?", (project_id,)
                ).fetchone()
                if project is None or project["owner_user_id"] != owner:
                    return False
            connection.execute(
                "UPDATE sessions SET project_id = ?, updated_at = ? WHERE session_id = ?",
                (project_id, utc_now(), session_id),
            )
        return True

    def set_session_pinned(self: SQLiteStore, session_id: str, pinned: bool, user_id: str | None = None) -> bool:
        """Pin (or unpin) a session. Returns False if the session does not exist
        or is owned by another account (user isolation mirrors list_sessions)."""
        with self.connect() as connection:
            exists, owner = self._session_owner(connection, session_id)
            if not exists:
                return False
            if user_id is not None and owner is not None and str(owner) != user_id:
                return False
            connection.execute(
                "UPDATE sessions SET pinned = ?, updated_at = ? WHERE session_id = ?",
                (1 if pinned else 0, utc_now(), session_id),
            )
        return True

    # A tag is an organizing label only (like the `pinned` flag and the
    # `projects` table) — it grants nothing and changes no gate, policy, or
    # authority. Many-to-many: a session carries an ordered set of tags; the
    # same tag may be reused across sessions. Setters are full-replace so the
    # caller's normalized list is the single source of truth. User/session
    # visibility mirrors set_session_pinned — an account cannot retag another
    # account's session.

    def list_session_tags(self: SQLiteStore, session_id: str) -> list[str]:
        rows = self._rows(
            "SELECT tag FROM session_tags WHERE session_id = ? ORDER BY tag",
            (session_id,),
        )
        return [str(row["tag"]) for row in rows]

    def list_session_tags_by_session(self: SQLiteStore, session_ids: list[str]) -> dict[str, list[str]]:
        """Tags for a whole page of sessions, in one query (BUG-303).

        The work index draws the tag editor on every row, and calling
        :meth:`list_session_tags` per row would make one page of Threads fifty
        round trips against an encrypted store. Sessions with no tags are simply
        absent, exactly as the per-session read returns an empty list.
        """
        wanted = [item for item in dict.fromkeys(session_ids) if item]
        if not wanted:
            return {}
        placeholders = ",".join("?" for _ in wanted)
        rows = self._rows(
            f"""SELECT session_id, tag FROM session_tags
                WHERE session_id IN ({placeholders})
                ORDER BY session_id, tag""",
            tuple(wanted),
        )
        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(str(row["session_id"]), []).append(str(row["tag"]))
        return grouped

    def set_session_tags(
        self: SQLiteStore, session_id: str, tags: list[str], user_id: str | None = None
    ) -> bool:
        """Full-replace the tag set for one session. ``tags`` is the already
        normalized, deduplicated, ordered list. Returns False if the session
        does not exist or is owned by another account (mirrors
        set_session_pinned). FK ON DELETE CASCADE keeps rows consistent if the
        session is removed out-of-band, but the explicit delete_session
        cascade also clears them."""
        with self.connect() as connection:
            exists, owner = self._session_owner(connection, session_id)
            if not exists:
                return False
            if user_id is not None and owner is not None and str(owner) != user_id:
                return False
            connection.execute("DELETE FROM session_tags WHERE session_id = ?", (session_id,))
            if tags:
                now = utc_now()
                connection.executemany(
                    "INSERT OR IGNORE INTO session_tags (session_id, tag, created_at) VALUES (?, ?, ?)",
                    [(session_id, tag, now) for tag in tags],
                )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (utc_now(), session_id),
            )
        return True

    def delete_session(
        self: SQLiteStore, session_id: str, user_id: str | None = None, *, journal: bool = True
    ) -> bool:
        """Delete one session and its cascaded rows (turns, events index, tool
        actions, policy decisions, checkpoints, tasks). Returns False if the
        session does not exist or is owned by another account. The per-session
        events JSONL file is removed too — it is the append-only transcript and
        must not be left orphaned. Mirrors delete_project's cascade scope."""
        with self.connect() as connection:
            exists, owner = self._session_owner(connection, session_id)
            if not exists:
                return False
            if user_id is not None and owner is not None and str(owner) != user_id:
                return False
            self._delete_session_rows(connection, session_id)
        # Remove the per-session events transcript file (best-effort; the db rows
        # above are already the source of truth and are committed).
        with contextlib.suppress(FileNotFoundError):
            (self.paths.events_dir / f"{session_id}.jsonl").unlink()
        if journal:
            # DEC-24 step 5 — outside the database, so a restore honours it.
            record_deletion(self.paths.workspace_root, SESSION_DELETE, session_id, owner)
        return True

    @staticmethod
    def _delete_session_rows(connection: sqlite3.Connection, session_id: str) -> None:
        action_ids = "SELECT action_id FROM tool_actions WHERE session_id = ?"
        connection.execute(
            f"DELETE FROM policy_decisions WHERE action_id IN ({action_ids})", (session_id,)
        )
        for table in (
            "events_index",
            "tool_actions",
            "checkpoints",
            "tasks",
            "turns",
            "model_session_state",
            "model_fallback_sequence",
            "model_advisor",
            "session_tags",
            # Session-keyed rows added after this cascade was written, each of
            # which holds conversation content or state that must not outlive the
            # conversation: the source ledger and its recorded passages (C6/C4),
            # the agent's standing plan (B6), and any parked stop/steer (B17/C13).
            "turn_sources",
            "agent_plans",
            "turn_controls",
        ):
            connection.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_id,))
        connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def delete_sessions(self: SQLiteStore, session_ids: list[str], user_id: str | None = None) -> bool:
        """Atomically delete visible sessions and their cascaded rows."""
        if not session_ids or len(set(session_ids)) != len(session_ids):
            return False
        with self.connect() as connection:
            for session_id in session_ids:
                exists, owner = self._session_owner(connection, session_id)
                if not exists or (
                    user_id is not None and owner is not None and str(owner) != user_id
                ):
                    return False
            for session_id in session_ids:
                self._delete_session_rows(connection, session_id)
        for session_id in session_ids:
            with contextlib.suppress(FileNotFoundError):
                (self.paths.events_dir / f"{session_id}.jsonl").unlink()
            record_deletion(self.paths.workspace_root, SESSION_DELETE, session_id, user_id)
        return True

    def list_turns(self: SQLiteStore, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        )
        return [dict(row) for row in rows]

    def count_turns_by_session(self: SQLiteStore, session_ids: list[str]) -> dict[str, int]:
        """How many turns each of these sessions holds (C11).

        One query for a whole task list rather than one per card: the Tasks page
        renders every task's thread link and each needs to know whether the
        thread has anything in it yet.
        """
        wanted = [item for item in dict.fromkeys(session_ids) if item]
        if not wanted:
            return {}
        placeholders = ",".join("?" for _ in wanted)
        rows = self._rows(
            f"""SELECT session_id, COUNT(*) AS turns FROM turns
                WHERE session_id IN ({placeholders})
                GROUP BY session_id""",
            tuple(wanted),
        )
        return {str(row["session_id"]): int(row["turns"]) for row in rows}

    def load_turn(self: SQLiteStore, turn_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM turns WHERE turn_id = ?", (turn_id,))
        return dict(row) if row else None

    def insert_turn(
        self: SQLiteStore, session_id: str, turn_id: str, prompt_text: str, status: str = "running"
    ) -> None:
        title = " ".join(prompt_text.split())[:80].rstrip()
        if len(title) == 80:
            title = f"{title[:-1]}…"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO turns
                (turn_id, session_id, turn_type, status, prompt_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (turn_id, session_id, "prompt", status, prompt_text, utc_now()),
            )
            # Keep a human-readable conversation name without replacing a
            # title that was explicitly supplied or generated earlier.
            connection.execute(
                """
                UPDATE sessions SET title = CASE
                    WHEN (title IS NULL OR TRIM(title) = '') AND ? != '' THEN ?
                    ELSE title
                END, updated_at = ?
                WHERE session_id = ?
                """,
                (title, title, utc_now(), session_id),
            )
            self._sync_conversation_fts(connection, turn_id)

    def complete_turn(self: SQLiteStore, turn_id: str, status: str, summary: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE turns SET status = ?, completed_at = ?, summary = ? WHERE turn_id = ?",
                (status, utc_now(), summary, turn_id),
            )
            self._sync_conversation_fts(connection, turn_id)

    def record_turn_reasoning(self: SQLiteStore, turn_id: str, *, chars: int, text: str | None) -> None:
        """Add to how much working a turn produced, and to the working if it is kept.

        BUG-215 — the two are separate on purpose. ``chars`` is always written and
        is not sensitive: it is what lets a re-opened turn distinguish "produced
        no reasoning" from "produced reasoning that was not kept", which is the
        difference between an honest surface and one that quietly shows less than
        it did while the turn ran. ``text`` is written only when the owner has
        turned retention on, and is deliberately **not** projected into
        ``conversation_fts``: retained working must not become searchable
        conversation content the owner never asked to index.

        **Additive, because a turn can run its loop more than once.** A turn that
        parks on an approval and resumes re-enters the same loop under the same
        ``turn_id``; the owner watched both halves of its working stream by, so
        replacing would keep only the half after the decision and silently drop
        the reasoning that produced the proposal they approved.
        """
        added = max(0, int(chars))
        if added == 0 and text is None:
            return
        self._execute(
            """UPDATE turns
               SET reasoning_chars = COALESCE(reasoning_chars, 0) + ?,
                   reasoning_text = CASE
                       WHEN ? IS NULL THEN reasoning_text
                       WHEN reasoning_text IS NULL OR reasoning_text = '' THEN ?
                       ELSE reasoning_text || ?
                   END
               WHERE turn_id = ?""",
            (added, text, text, f"\n\n{text}", turn_id),
        )

    @staticmethod
    def _match_terms(query: str) -> list[str]:
        """Terms both engines read as literals. Punctuation is stripped, not escaped.

        Stripping punctuation removes the parenthesis and quote operators, but it
        leaves the *keyword* operators, which FTS4 and FTS5 alike recognise only
        in upper case. A prompt is ordinary prose, so `AND`, `OR`, `NOT`, and
        `NEAR` arrive as words the owner typed, not as syntax: `NOT deployment`
        is a malformed expression that raises, and `find NOT deployment` parses
        as an exclusion and answers with the opposite of what was asked.
        Lower-casing every term makes each one a literal, which is what the
        tokenizer already matches case-insensitively — so the search means what
        the prompt says. What is left is alphanumeric ASCII, which is a bareword
        under both grammars and therefore needs no quoting in either.
        """
        cleaned = "".join(character if character.isalnum() else " " for character in query)
        terms = [term.lower() for term in cleaned.split() if len(term) >= 3][:12]
        # BUG-243 — the join is an AND, so every surviving word has to appear in
        # the stored text. A question carries words that carry no meaning for a
        # search — "where do my nightly backups go?" failed against a memory
        # reading "my nightly backups go to the encrypted NAS", because "where"
        # is not in it. Recall therefore fired for keyword queries and almost
        # never for a sentence, which is the shape of a memory system that looks
        # present and is not.
        #
        # Function words are dropped rather than the join loosened: an OR over a
        # whole sentence would rank an unrelated memory highly for containing
        # "the", which is a worse failure than finding nothing because it is
        # presented as an answer. A query that is *only* function words keeps
        # them, so searching for a literal "the" still searches for it.
        content = [term for term in terms if term not in _SEARCH_STOPWORDS]
        return content or terms

    def _match_expression(self: SQLiteStore, terms: list[str]) -> str:
        """The MATCH expression for *terms*.

        Space-separated barewords are an implicit **AND** in both FTS grammars,
        which is the right default: a row matching every word the owner typed is
        what they asked for, and an ``OR`` over a whole sentence would rank an
        unrelated memory highly for containing the word "the". The join is left
        alone; what changed is which words reach it — see ``_match_terms``.
        """
        return " ".join(terms)

    def search_conversation_turns(
        self: SQLiteStore,
        query: str,
        *,
        user_id: str | None = None,
        limit: int = 10,
        session_id: str | None = None,
        project_id: str | None = None,
        after: str | None = None,
        before: str | None = None,
    ) -> list[dict[str, Any]]:
        """Exchanges matching *query*, best match first, scoped to one owner.

        The index answers "which exchanges mention this"; the join answers "and
        may this caller see them". ``after``/``before`` are ISO timestamps, which
        is what makes an old conversation reachable at all: without them a bounded
        result set is always the recent one.

        MEM-05 — ordering is relevance, then recency. Under FTS4 there was no
        relevance score to order by, so the oldest exact answer was the first
        row the limit discarded; under FTS5 `bm25()` supplies one and recency
        only breaks ties. A query with no indexable term still falls back to a
        substring scan, and that branch has no score, so it stays newest-first.
        """
        if limit < 1:
            return []
        terms = self._match_terms(query)
        conditions = ["turns.turn_id IS NOT NULL"]
        params: list[Any] = []
        ordering = "turns.created_at DESC"
        if terms:
            source = (
                "conversation_fts JOIN turns ON turns.turn_id = conversation_fts.turn_id "
                "JOIN sessions ON sessions.session_id = turns.session_id"
            )
            selected = (
                "conversation_fts.role AS role, "
                f"{self._snippet_expression('conversation_fts', 3)} AS snippet"
            )
            conditions.append("conversation_fts MATCH ?")
            params.append(self._match_expression(terms))
            if self.resolved_text_search_engine() == TEXT_SEARCH_FTS5:
                # Only the `text` column is indexed; the other three are
                # UNINDEXED and can never contribute, but `bm25` still requires
                # one weight per declared column.
                ordering = "bm25(conversation_fts, 0.0, 0.0, 0.0, 1.0) ASC, turns.created_at DESC"
        else:
            # Terms shorter than the index tokenizer's floor (an identifier such
            # as `q3`) still have to be findable, so a substring scan stands in.
            # The role has to be decided by which side actually matched, or a hit
            # in an answer is reported as a prompt and read back from the wrong
            # column.
            source = "turns JOIN sessions ON sessions.session_id = turns.session_id"
            selected = (
                "CASE WHEN turns.prompt_text LIKE ? THEN 'prompt' ELSE 'answer' END AS role, "
                "SUBSTR(CASE WHEN turns.prompt_text LIKE ? THEN turns.prompt_text "
                "ELSE COALESCE(turns.summary, '') END, 1, 220) AS snippet"
            )
            like = f"%{query.strip()}%"
            params.extend([like, like])
            conditions.append("(turns.prompt_text LIKE ? OR turns.summary LIKE ?)")
            params.extend([like, like])
        if user_id is not None:
            conditions.append("(sessions.user_id = ? OR sessions.user_id IS NULL)")
            params.append(user_id)
        if session_id is not None:
            conditions.append("turns.session_id = ?")
            params.append(session_id)
        if project_id is not None:
            # Build's boundary: only conversations assigned to the selected
            # project. An unassigned conversation is *not* in scope -- a NULL
            # project_id means "belongs to no project", not "belongs to all".
            conditions.append("sessions.project_id = ?")
            params.append(project_id)
        if after:
            conditions.append("turns.created_at >= ?")
            params.append(after)
        if before:
            conditions.append("turns.created_at <= ?")
            params.append(before)
        params.append(limit)
        sql = (
            f"SELECT turns.turn_id AS turn_id, turns.session_id AS session_id, "
            f"turns.created_at AS created_at, turns.prompt_text AS prompt_text, "
            f"turns.summary AS summary, sessions.title AS session_title, "
            f"sessions.origin AS origin, {selected} FROM {source} "
            f"WHERE {' AND '.join(conditions)} "
            f"ORDER BY {ordering} LIMIT ?"
        )
        with self.connect() as connection:
            try:
                rows = connection.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(row) for row in rows]

    def index_event(
        self: SQLiteStore,
        event: AgentEvent,
        jsonl_path: str,
        jsonl_offset: int,
        payload_sha256: str,
        prev_event_sha256: str | None = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO events_index
            (event_id, session_id, turn_id, task_id, event_type, actor, timestamp, jsonl_path, jsonl_offset, payload_sha256, prev_event_sha256, risk_level, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.session_id,
                event.turn_id,
                event.payload.get("task_id"),
                event.event_type,
                event.actor,
                event.timestamp,
                jsonl_path,
                jsonl_offset,
                payload_sha256,
                prev_event_sha256,
                event.payload.get("risk_level"),
                event.payload.get("summary"),
            ),
        )

    @staticmethod
    def tool_action_payload_sha256(tool_name: str, arguments_json: str, risk_level: str) -> str:
        payload = json.dumps(
            {
                "tool_name": tool_name,
                "arguments": json.loads(arguments_json),
                "risk_level": risk_level,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def insert_tool_action(
        self: SQLiteStore,
        action: ToolAction,
        session_id: str,
        turn_id: str | None,
        status: str,
        *,
        owner_principal_id: str | None = None,
        machine_subject: str | None = None,
        machine_token_id: str | None = None,
        machine_key_id: str | None = None,
        machine_issued_at: str | None = None,
        machine_expires_at: str | None = None,
    ) -> None:
        self._execute(
            """
              INSERT OR REPLACE INTO tool_actions
              (action_id, session_id, turn_id, task_id, tool_name, arguments_json,
               risk_level, status, proposed_at, completed_at, proposed_by,
               owner_principal_id, machine_subject, machine_token_id,
               machine_key_id, machine_issued_at, machine_expires_at)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                      COALESCE((SELECT proposed_at FROM tool_actions WHERE action_id = ?), ?),
                      ?, ?,
                      COALESCE(?, (SELECT owner_principal_id FROM tool_actions WHERE action_id = ?)),
                      COALESCE(?, (SELECT machine_subject FROM tool_actions WHERE action_id = ?)),
                      COALESCE(?, (SELECT machine_token_id FROM tool_actions WHERE action_id = ?)),
                      COALESCE(?, (SELECT machine_key_id FROM tool_actions WHERE action_id = ?)),
                      COALESCE(?, (SELECT machine_issued_at FROM tool_actions WHERE action_id = ?)),
                      COALESCE(?, (SELECT machine_expires_at FROM tool_actions WHERE action_id = ?)))
            """,
            (
                action.action_id,
                session_id,
                turn_id,
                None,
                action.tool_name,
                json.dumps(action.arguments, sort_keys=True),
                action.risk_level,
                status,
                action.action_id,
                utc_now(),
                utc_now()
                if status in {"success", "failed", "denied", "approval_required"}
                else None,
                action.proposed_by,
                owner_principal_id,
                action.action_id,
                machine_subject,
                action.action_id,
                machine_token_id,
                action.action_id,
                machine_key_id,
                action.action_id,
                machine_issued_at,
                action.action_id,
                machine_expires_at,
                action.action_id,
            ),
        )

    def list_turn_tool_actions(self: SQLiteStore, session_id: str, turn_id: str | None) -> list[dict[str, Any]]:
        """Every tool action proposed in one turn, oldest first.

        BUG-218 — the record `auto` mode's alignment check reads. A turn's own
        history is what makes "does this action match what was asked?" a
        deterministic question instead of a judgement: the arguments are stored
        verbatim, so the check is set membership over facts rather than a model's
        opinion.

        Scoped to the turn, never the session, because establishing a file in one
        turn must not silently authorise writing it unprompted in the next.
        """
        if not turn_id:
            return []
        rows = self._rows(
            """SELECT action_id, tool_name, arguments_json, status, proposed_at
               FROM tool_actions
               WHERE session_id = ? AND turn_id = ?
               ORDER BY proposed_at ASC, rowid ASC""",
            (session_id, turn_id),
        )
        return [dict(row) for row in rows]

    def load_tool_action(self: SQLiteStore, action_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM tool_actions WHERE action_id = ?", (action_id,))
        return dict(row) if row else None

    def insert_policy_decision(self: SQLiteStore, decision: PolicyDecision) -> None:
        self._execute(
            """
            INSERT INTO policy_decisions
            (decision_id, action_id, decision, reasons_json, policy_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                decision.decision_id,
                decision.action_id,
                decision.decision,
                json.dumps(decision.reasons),
                decision.policy_version,
                decision.timestamp or utc_now(),
            ),
        )


    def save_agent_plan(
        self: SQLiteStore, *, session_id: str, principal_id: str, turn_id: str, steps_json: str
    ) -> str:
        """Replace this conversation's plan with *steps_json*; returns ``updated_at``.

        The plan is current intent, not a history, so one row per
        (session, principal) is replaced whole. ``created_at`` is preserved
        across updates so the workspace can say how long the plan has stood.
        """
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT created_at FROM agent_plans WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            ).fetchone()
            created_at = str(existing["created_at"]) if existing is not None else now
            connection.execute(
                """INSERT OR REPLACE INTO agent_plans
                   (session_id, principal_id, turn_id, steps_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, principal_id, turn_id, steps_json, created_at, now),
            )
        return now

    def load_agent_plan(self: SQLiteStore, session_id: str, principal_id: str) -> dict[str, Any] | None:
        """This conversation's plan, or None. Owner-scoped: never cross-account."""
        row = self._row(
            "SELECT * FROM agent_plans WHERE session_id = ? AND principal_id = ?",
            (session_id, principal_id),
        )
        return dict(row) if row is not None else None

    def clear_agent_plan(self: SQLiteStore, session_id: str, principal_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM agent_plans WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            )
            return cursor.rowcount > 0


    def record_turn_sources(
        self: SQLiteStore, *, session_id: str, turn_id: str, principal_id: str, rows: list[dict[str, Any]]
    ) -> None:
        """Append this turn's newly used sources, keeping the order they arrived.

        ``INSERT OR IGNORE`` rather than ``REPLACE``: a source id is assigned
        once per turn and a re-run of the same turn (a resumed one, say) must
        not rewrite the row a chip is already pointing at.
        """
        if not rows:
            return
        now = utc_now()
        with self.connect() as connection:
            connection.executemany(
                """INSERT OR IGNORE INTO turn_sources
                   (session_id, turn_id, source_id, principal_id, ordinal, kind, title,
                    locator, tool_name, detail, attachment_id, passage, anchors_json,
                    created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        session_id,
                        turn_id,
                        str(row["source_id"]),
                        principal_id,
                        int(row["ordinal"]),
                        str(row.get("kind", "")),
                        str(row.get("title", "")),
                        str(row.get("locator", "")),
                        str(row.get("tool_name", "")),
                        str(row.get("detail", "")),
                        str(row.get("attachment_id", "")),
                        str(row.get("passage", "")),
                        str(row.get("anchors_json", "")),
                        now,
                    )
                    for row in rows
                ],
            )

    def count_turn_sources(self: SQLiteStore, session_id: str, turn_id: str, principal_id: str) -> int:
        """How many sources this turn has already recorded, for the next id."""
        row = self._row(
            "SELECT COUNT(*) AS n FROM turn_sources "
            "WHERE session_id = ? AND turn_id = ? AND principal_id = ?",
            (session_id, turn_id, principal_id),
        )
        return int(row["n"]) if row is not None else 0

    def load_turn_sources(
        self: SQLiteStore, session_id: str, principal_id: str, turn_id: str | None = None
    ) -> list[dict[str, Any]]:
        """This conversation's recorded sources. Owner-scoped: never cross-account."""
        query = "SELECT * FROM turn_sources WHERE session_id = ? AND principal_id = ?"
        params: list[Any] = [session_id, principal_id]
        if turn_id:
            query += " AND turn_id = ?"
            params.append(turn_id)
        query += " ORDER BY created_at ASC, ordinal ASC"
        rows = self._rows(query, tuple(params))
        return [dict(row) for row in rows]

    def load_turn_source(
        self: SQLiteStore, session_id: str, turn_id: str, source_id: str, principal_id: str
    ) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM turn_sources WHERE session_id = ? AND turn_id = ? "
            "AND source_id = ? AND principal_id = ?",
            (session_id, turn_id, source_id, principal_id),
        )
        return dict(row) if row is not None else None

    #
    # Ambient recall reaches a turn through the context bundle, so it leaves no
    # citation to click. These two methods are the whole record: the ids a turn
    # was given, and reading them back for the account that owns the
    # conversation. The sentences themselves are never copied here — they are
    # read live from `approved_memory`, so a memory corrected or forgotten since
    # the turn ran reads as it is now rather than as it was.

    def record_turn_recall(
        self: SQLiteStore, *, session_id: str, turn_id: str, principal_id: str, memory_ids: Sequence[str]
    ) -> None:
        if not memory_ids:
            return
        now = utc_now()
        with self.connect() as connection:
            connection.executemany(
                """INSERT OR IGNORE INTO turn_recalls
                   (session_id, turn_id, principal_id, memory_id, ordinal, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (session_id, turn_id, principal_id, str(memory_id), ordinal, now)
                    for ordinal, memory_id in enumerate(memory_ids)
                ],
            )

    def load_turn_recall(
        self: SQLiteStore, session_id: str, principal_id: str, turn_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Recalled memory ids for this conversation. Owner-scoped, never cross-account."""
        query = "SELECT * FROM turn_recalls WHERE session_id = ? AND principal_id = ?"
        params: list[Any] = [session_id, principal_id]
        if turn_id:
            query += " AND turn_id = ?"
            params.append(turn_id)
        query += " ORDER BY created_at ASC, ordinal ASC"
        rows = self._rows(query, tuple(params))
        return [dict(row) for row in rows]

    def memory_recall_usage(
        self: SQLiteStore, memory_ids: Sequence[str], principal_id: str
    ) -> dict[str, dict[str, Any]]:
        """UX-MEM-05 — the same ledger read from the memory's end.

        For each memory: how many turns were given it, when the latest was, and
        which conversation that turn belongs to, so the record can link to the
        answer it was put in front of. Inclusion, never reliance: the ledger
        records what a turn was given, not whether the answer leaned on it.

        Keyed by the principal that ran the turn, so a turn link never points
        into another account's conversation. No principal, no rows.
        """
        ids = [str(memory_id) for memory_id in memory_ids if memory_id]
        if not principal_id or not ids:
            return {}
        usage: dict[str, dict[str, Any]] = {}
        # Chunked so a long listing cannot exceed SQLite's bound-parameter limit.
        for start in range(0, len(ids), 400):
            chunk = ids[start : start + 400]
            marks = ",".join("?" for _ in chunk)
            rows = self._rows(
                f"""SELECT r.memory_id, r.session_id, r.turn_id, r.created_at,
                           COALESCE(s.origin, 'chat') AS origin
                      FROM turn_recalls r
                      LEFT JOIN sessions s ON s.session_id = r.session_id
                     WHERE r.principal_id = ? AND r.memory_id IN ({marks})
                     ORDER BY r.created_at DESC, r.ordinal ASC""",  # noqa: S608 - placeholders only
                (principal_id, *chunk),
            )
            for row in rows:
                memory_id = str(row["memory_id"])
                entry = usage.get(memory_id)
                if entry is None:
                    usage[memory_id] = {
                        "turn_count": 1,
                        "last_recalled_at": str(row["created_at"]),
                        "last_session_id": str(row["session_id"]),
                        "last_turn_id": str(row["turn_id"]),
                        "last_session_origin": str(row["origin"]),
                    }
                else:
                    entry["turn_count"] += 1
        return usage

    #
    # `turn_sources` is a link table that was only ever read forwards: "what did
    # this turn use". Read backwards and sideways it is the graph Obsidian's
    # metadata cache exposes over a vault — `getBacklinksForFile` (who cites
    # this), `resolvedLinks` (what this cites, with a count per target), and the
    # block reference (the exact passage, not the whole document). Raiker
    # already stored all three facts per row; nothing here derives anything new,
    # it reads what the ledger recorded from the other end.
    #
    # Every method is owner-scoped in the query. `principal_id` is optional only
    # so the Knowledge Map can render an unfiltered workspace view; the
    # model-facing tool always passes it.

    def list_source_backlinks(
        self: SQLiteStore, locator: str, *, principal_id: str | None = None, limit: int = 25
    ) -> list[dict[str, Any]]:
        """Which conversations cited this source, and how often.

        The reference count is per target-and-conversation, matching what
        Obsidian reports for a backlink: one entry per citing document, carrying
        how many references it holds.
        """
        cleaned = locator.strip()
        if not cleaned:
            return []
        sql = """SELECT s.session_id,
                        COALESCE(NULLIF(TRIM(sess.title), ''), 'Untitled') AS session_title,
                        COALESCE(sess.origin, '') AS session_origin,
                        MIN(s.kind) AS kind,
                        MIN(s.title) AS title,
                        MIN(s.tool_name) AS tool_name,
                        COUNT(*) AS refs,
                        COUNT(DISTINCT s.turn_id) AS turns,
                        SUM(CASE WHEN TRIM(s.passage) != '' THEN 1 ELSE 0 END) AS passages,
                        MAX(s.created_at) AS last_referenced_at
                 FROM turn_sources s
                 LEFT JOIN sessions sess ON sess.session_id = s.session_id
                 WHERE s.locator = ?"""
        params: list[Any] = [cleaned]
        if principal_id:
            sql += " AND s.principal_id = ?"
            params.append(principal_id)
        sql += " GROUP BY s.session_id ORDER BY refs DESC, last_referenced_at DESC LIMIT ?"
        params.append(limit)
        rows = self._rows(sql, params)
        return [dict(row) for row in rows]

    def list_source_outlinks(
        self: SQLiteStore, session_id: str, *, principal_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """What this conversation cited, one entry per target with a count."""
        if not session_id.strip():
            return []
        sql = """SELECT locator, kind, tool_name, attachment_id,
                        MIN(title) AS title,
                        COUNT(*) AS refs,
                        COUNT(DISTINCT turn_id) AS turns,
                        SUM(CASE WHEN TRIM(passage) != '' THEN 1 ELSE 0 END) AS passages,
                        MAX(created_at) AS last_referenced_at
                 FROM turn_sources
                 WHERE session_id = ?"""
        params: list[Any] = [session_id.strip()]
        if principal_id:
            sql += " AND principal_id = ?"
            params.append(principal_id)
        sql += (
            " GROUP BY locator, kind, tool_name, attachment_id"
            " ORDER BY refs DESC, last_referenced_at DESC LIMIT ?"
        )
        params.append(limit)
        rows = self._rows(sql, params)
        return [dict(row) for row in rows]

    def list_co_cited_sources(
        self: SQLiteStore, locator: str, *, principal_id: str | None = None, limit: int = 25
    ) -> list[dict[str, Any]]:
        """What else was cited by the conversations that cited this.

        The edge a graph view actually draws. Two sources cited by the same work
        are related in the only sense Raiker can evidence — some work needed
        both — which is weaker than a hyperlink, so it is reported with the
        number of conversations behind it rather than as a bare edge.
        """
        cleaned = locator.strip()
        if not cleaned:
            return []
        sql = """SELECT other.locator,
                        MIN(other.kind) AS kind,
                        MIN(other.title) AS title,
                        COUNT(DISTINCT other.session_id) AS shared_sessions,
                        COUNT(*) AS refs,
                        MAX(other.created_at) AS last_referenced_at
                 FROM turn_sources mine
                 JOIN turn_sources other
                   ON other.session_id = mine.session_id
                  AND other.locator != mine.locator
                 WHERE mine.locator = ? AND TRIM(other.locator) != ''"""
        params: list[Any] = [cleaned]
        if principal_id:
            sql += " AND mine.principal_id = ? AND other.principal_id = ?"
            params.extend([principal_id, principal_id])
        sql += (
            " GROUP BY other.locator"
            " ORDER BY shared_sessions DESC, refs DESC, last_referenced_at DESC LIMIT ?"
        )
        params.append(limit)
        rows = self._rows(sql, params)
        return [dict(row) for row in rows]

    def list_source_passages(
        self: SQLiteStore, locator: str, *, principal_id: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """The bounded text this source actually contributed, most recent first.

        This is the half a reference graph is useless without. A backlink says
        *something over there mentioned this*; the passage is the sentence, and
        it is the copy that really reached the model rather than whatever the
        file says today.
        """
        cleaned = locator.strip()
        if not cleaned:
            return []
        sql = """SELECT session_id, turn_id, source_id, kind, title, tool_name,
                        attachment_id, passage, created_at
                 FROM turn_sources
                 WHERE locator = ? AND TRIM(passage) != ''"""
        params: list[Any] = [cleaned]
        if principal_id:
            sql += " AND principal_id = ?"
            params.append(principal_id)
        sql += " ORDER BY created_at DESC, ordinal ASC LIMIT ?"
        params.append(limit)
        rows = self._rows(sql, params)
        return [dict(row) for row in rows]


    def request_turn_stop(self: SQLiteStore, session_id: str, principal_id: str, *, reason: str) -> str:
        """Ask the turn running in this conversation to stop at its next boundary."""
        now = utc_now()
        self._execute(
            """INSERT INTO turn_controls
                 (session_id, principal_id, stop_requested, stop_reason, steer_json, updated_at)
               VALUES (?, ?, 1, ?, '[]', ?)
               ON CONFLICT(session_id, principal_id) DO UPDATE SET
                 stop_requested = 1, stop_reason = excluded.stop_reason,
                 updated_at = excluded.updated_at""",
            (session_id, principal_id, reason, now),
        )
        return now

    def queue_turn_steer(self: SQLiteStore, session_id: str, principal_id: str, *, text: str) -> int:
        """Append one owner instruction for the running turn; returns the queue depth.

        Appending rather than replacing is deliberate: an owner who types two
        corrections while a turn runs meant both of them.
        """
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT steer_json FROM turn_controls WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            ).fetchone()
            queued: list[str] = []
            if row is not None:
                try:
                    parsed = json.loads(str(row["steer_json"]))
                    if isinstance(parsed, list):
                        queued = [str(item) for item in parsed]
                except ValueError:
                    queued = []
            queued.append(text)
            connection.execute(
                """INSERT INTO turn_controls
                     (session_id, principal_id, stop_requested, stop_reason, steer_json, updated_at)
                   VALUES (?, ?, 0, NULL, ?, ?)
                   ON CONFLICT(session_id, principal_id) DO UPDATE SET
                     steer_json = excluded.steer_json, updated_at = excluded.updated_at""",
                (session_id, principal_id, json.dumps(queued), now),
            )
        return len(queued)

    def take_turn_control(self: SQLiteStore, session_id: str, principal_id: str) -> dict[str, Any]:
        """Read and clear this conversation's pending controls, atomically.

        Consuming on read is what keeps a control from applying twice: a stop the
        loop has honoured must not also end the *next* turn, and a steer must
        reach the model once.
        """
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM turn_controls WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            ).fetchone()
            if row is None:
                return {"stop_requested": False, "stop_reason": None, "steer_texts": []}
            connection.execute(
                "DELETE FROM turn_controls WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            )
        try:
            parsed = json.loads(str(row["steer_json"]))
            steer = [str(item) for item in parsed] if isinstance(parsed, list) else []
        except ValueError:
            steer = []
        return {
            "stop_requested": bool(row["stop_requested"]),
            "stop_reason": row["stop_reason"],
            "steer_texts": steer,
        }

    def clear_turn_control(self: SQLiteStore, session_id: str, principal_id: str) -> None:
        """Drop anything left over before a new turn starts.

        A stop or steer that arrived between turns had no turn to act on; keeping
        it would apply the owner's decision to work they had not yet asked for.
        """
        self._execute(
            "DELETE FROM turn_controls WHERE session_id = ? AND principal_id = ?",
            (session_id, principal_id),
        )


    def insert_suspended_turn(self: SQLiteStore, record: dict[str, Any]) -> None:
        """Park one turn's working state against the approval that blocked it.

        ``INSERT OR REPLACE`` keyed on ``approval_id``: an approval blocks exactly
        one turn, and re-suspending the same approval is a re-park, not a second
        row.
        """
        self._execute(
            """INSERT OR REPLACE INTO suspended_turns
               (approval_id, session_id, turn_id, request_id, principal_id, action_id,
                tool_name, call_id, prompt_text, messages_json, options_json, client_json,
                tool_calls_made, status, outcome_json, created_at, resumed_at,
                pending_calls_json, queue_position, queue_total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'suspended', NULL, ?, NULL,
                       ?, ?, ?)""",
            (
                record["approval_id"],
                record["session_id"],
                record["turn_id"],
                record["request_id"],
                record["principal_id"],
                record["action_id"],
                record["tool_name"],
                record["call_id"],
                record["prompt_text"],
                record["messages_json"],
                record["options_json"],
                record["client_json"],
                int(record.get("tool_calls_made", 0)),
                utc_now(),
                # ADD-02 — the rest of the batch travels with the turn. A
                # caller that parks a single call writes the defaults, which
                # are exactly the pre-queue behaviour.
                str(record.get("pending_calls_json") or "[]"),
                int(record.get("queue_position", 1)),
                int(record.get("queue_total", 1)),
            ),
        )

    def load_suspended_turn(
        self: SQLiteStore, approval_id: str, *, principal_id: str | None = None
    ) -> dict[str, Any] | None:
        """Load a parked turn. Scoping by principal keeps turns owner-isolated."""
        query = "SELECT * FROM suspended_turns WHERE approval_id = ?"
        params: tuple[Any, ...] = (approval_id,)
        if principal_id is not None:
            query += " AND principal_id = ?"
            params = (approval_id, principal_id)
        row = self._row(query, params)
        return dict(row) if row is not None else None

    def list_resumable_suspended_turns(
        self: SQLiteStore, principal_id: str, session_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Parked turns whose approval has been resolved and which may resume (BUG-24).

        A turn qualifies only when it is still ``suspended`` *and* carries an
        ``outcome_json`` — that outcome is written when the approval is resolved,
        so its presence is exactly the "this approval has been decided" signal a
        Chat tab in another window needs. A turn already claimed by a resuming
        client has moved to ``resuming`` and is not listed, so two tabs polling
        together cannot both start the same continuation.

        Owner-scoped by principal: this can never reveal another account's turn.
        No conversation state is returned — ids and metadata only.
        """
        query = (
            "SELECT approval_id, session_id, turn_id, tool_name, outcome_json, created_at, "
            "queue_position, queue_total "
            "FROM suspended_turns WHERE principal_id = ? AND status = 'suspended' "
            "AND outcome_json IS NOT NULL"
        )
        params: tuple[Any, ...] = (principal_id,)
        if session_id is not None:
            query += " AND session_id = ?"
            params = (principal_id, session_id)
        query += " ORDER BY created_at ASC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def list_pending_suspended_turns(
        self: SQLiteStore, principal_id: str, session_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Metadata for unresolved parked turns, scoped to their owner (BUG-34)."""
        query = (
            "SELECT approval_id, session_id, turn_id, tool_name, created_at, "
            "queue_position, queue_total "
            "FROM suspended_turns WHERE principal_id = ? AND status = 'suspended' "
            "AND outcome_json IS NULL"
        )
        params: tuple[Any, ...] = (principal_id,)
        if session_id is not None:
            query += " AND session_id = ?"
            params = (principal_id, session_id)
        query += " ORDER BY created_at ASC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def suspended_turn_queue_positions(
        self: SQLiteStore, approval_ids: Sequence[str]
    ) -> dict[str, tuple[int, int]]:
        """Where each approval sits in the batch its turn parked on (ADD-02).

        Approvals themselves know nothing about batching — an approval is one
        action. The batch is a property of the parked turn, so this is the join
        that lets the Approvals list say "decision 2 of 3" without teaching the
        approvals table about tool-call queues. Metadata only: two integers, no
        conversation state, and an approval with no parked turn is simply absent.
        """
        ids = [str(approval_id) for approval_id in approval_ids if approval_id]
        if not ids:
            return {}
        positions: dict[str, tuple[int, int]] = {}
        with self.connect() as connection:
            # Chunked so a long pending list cannot exceed SQLite's variable limit.
            for start in range(0, len(ids), 400):
                chunk = ids[start : start + 400]
                placeholders = ",".join("?" for _ in chunk)
                rows = connection.execute(
                    "SELECT approval_id, queue_position, queue_total FROM suspended_turns "
                    f"WHERE approval_id IN ({placeholders})",
                    chunk,
                ).fetchall()
                for row in rows:
                    positions[str(row["approval_id"])] = (
                        int(row["queue_position"] or 1),
                        int(row["queue_total"] or 1),
                    )
        return positions

    def record_suspended_turn_outcome(self: SQLiteStore, approval_id: str, outcome_json: str) -> bool:
        """Attach the resolution outcome the model will see as its tool result.

        Guarded on ``suspended`` so a resumed (or abandoned) turn cannot have its
        outcome rewritten after the model has already acted on it.
        """
        changed = self._execute(
            "UPDATE suspended_turns SET outcome_json = ? "
            "WHERE approval_id = ? AND status = 'suspended'",
            (outcome_json, approval_id),
        )
        return changed == 1

    def claim_suspended_turn(self: SQLiteStore, approval_id: str) -> bool:
        """Atomically claim a parked turn for resumption (suspended → resuming).

        The single-resumption primitive: a turn's working state may be replayed
        into the model exactly once, so a double-click or a racing client cannot
        run the continuation twice.
        """
        changed = self._execute(
            "UPDATE suspended_turns SET status = 'resuming', resumed_at = ? "
            "WHERE approval_id = ? AND status = 'suspended'",
            (utc_now(), approval_id),
        )
        return changed == 1

    def finalize_suspended_turn(self: SQLiteStore, approval_id: str, *, status: str) -> bool:
        """Resolve a claimed turn to a terminal state (resuming → status)."""
        changed = self._execute(
            "UPDATE suspended_turns SET status = ? WHERE approval_id = ? AND status = 'resuming'",
            (status, approval_id),
        )
        return changed == 1

    def load_api_session(self: SQLiteStore, session_id: str) -> dict[str, Any] | None:
        """Best-effort lookup of an API session row by id (posture snapshots)."""
        if not session_id:
            return None
        row = self._row("SELECT * FROM api_sessions WHERE session_id = ?", (session_id,))
        return dict(row) if row else None

    def list_event_index(
        self: SQLiteStore,
        session_id: str | None = None,
        turn_id: str | None = None,
        task_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        project_id: str | None = None,
        user_id: str | None = None,
        apply_user_visibility_filter: bool = False,
    ) -> list[dict]:
        query = """
            SELECT events_index.*, machine.principal_id AS proposed_by,
                   machine.subject AS machine_subject,
                   machine.key_id AS machine_key_id,
                   machine.issued_at AS machine_issued_at,
                   machine.expires_at AS machine_expires_at,
                   machine.is_active AS machine_is_active,
                   proposer.principal_type AS proposer_principal_type,
                   proposer.display_name AS proposer_display_name
            FROM events_index
            LEFT JOIN turn_machine_identities AS machine
              ON machine.principal_id = (
                SELECT identity.principal_id
                FROM turn_machine_identities AS identity
                WHERE identity.session_id = events_index.session_id
                  AND identity.turn_id = events_index.turn_id
                ORDER BY identity.issued_at DESC LIMIT 1
              )
            LEFT JOIN principals AS proposer
              ON proposer.principal_id = machine.principal_id
        """
        params: list[Any] = []
        conditions: list[str] = []
        if session_id is not None:
            conditions.append("events_index.session_id = ?")
            params.append(session_id)
        if turn_id is not None:
            conditions.append("events_index.turn_id = ?")
            params.append(turn_id)
        if task_id is not None:
            conditions.append("events_index.task_id = ?")
            params.append(task_id)
        if event_type is not None:
            conditions.append("events_index.event_type = ?")
            params.append(event_type)
        if project_id is not None:
            conditions.append(
                "events_index.session_id IN (SELECT session_id FROM sessions WHERE project_id = ?)"
            )
            params.append(project_id)
        if apply_user_visibility_filter:
            # BUG-231 — this filter has to agree with the account scope the audit
            # log *view* applies (`DashboardService.list_events`), or an export
            # is a different record than the screen it was taken from. Both rules
            # are: a row is visible when it belongs to one of this account's own
            # sessions, **or to no session record at all**. The second clause is
            # what keeps governed steps taken outside any conversation — a
            # credential connected, a model pinned, a principal resolved, all
            # recorded on runtime channels that are not sessions — inside the
            # evidence. It cannot leak another account's conversation: theirs are
            # session records, so they fail both clauses and stay filtered.
            unowned = "events_index.session_id NOT IN (SELECT session_id FROM sessions)"
            if user_id is None:
                conditions.append(
                    "(events_index.session_id IN "
                    "(SELECT session_id FROM sessions WHERE user_id IS NULL)"
                    f" OR {unowned})"
                )
            else:
                conditions.append(
                    "(events_index.session_id IN (SELECT session_id FROM sessions "
                    "WHERE user_id = ? OR user_id IS NULL)"
                    f" OR {unowned})"
                )
                params.append(user_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY events_index.timestamp DESC, events_index.rowid DESC LIMIT ?"
        params.append(str(limit))
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def all_session_ids(self: SQLiteStore) -> set[str]:
        """Every conversation session id in this workspace, whoever owns it.

        Read by the audit log (BUG-87) to tell a runtime channel — an event
        recorded outside any conversation — from another user's conversation.
        It carries no ownership, so it is never used to decide what to *show*,
        only what is not a conversation in the first place.
        """
        rows = self._rows("SELECT session_id FROM sessions")
        return {str(row["session_id"]) for row in rows}

    def count_events(self: SQLiteStore, session_id: str | None = None) -> int:
        query = "SELECT COUNT(*) AS cnt FROM events_index"
        params: list[Any] = []
        if session_id is not None:
            query += " WHERE session_id = ?"
            params.append(session_id)
        row = self._row(query, params)
        return int(row["cnt"]) if row else 0

    def load_event_index(self: SQLiteStore, event_id: str) -> dict | None:
        row = self._row("SELECT * FROM events_index WHERE event_id = ?", (event_id,))
        return dict(row) if row else None

    #
    # The map is about three things, read directly: the tools a session really
    # used, what a turn's answer came from, and the files the owner attached.
    # The event index is not one of them — most of its `tool` rows are
    # lifecycle events, not tools.

    def summarize_session_tool_use(
        self: SQLiteStore, session_ids: Sequence[str], *, owner_principal_id: str | None = None
    ) -> list[dict[str, Any]]:
        """One row per (session, tool), with how often it ran and how it ended.

        Aggregated in SQL rather than in the caller because the un-aggregated
        form is the defect: a busy session has hundreds of tool actions and the
        map only ever wanted "which tools, how much".
        """
        if not session_ids:
            return []
        placeholders = ",".join("?" for _ in session_ids)
        sql = f"""SELECT session_id, tool_name, COUNT(*) AS uses,
                         SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failures,
                         MAX(COALESCE(completed_at, proposed_at)) AS last_used_at
                  FROM tool_actions
                  WHERE session_id IN ({placeholders}) AND TRIM(tool_name) != ''"""
        params: list[Any] = list(session_ids)
        if owner_principal_id:
            sql += " AND (owner_principal_id = ? OR owner_principal_id IS NULL OR owner_principal_id = '')"
            params.append(owner_principal_id)
        sql += " GROUP BY session_id, tool_name ORDER BY uses DESC, tool_name"
        rows = self._rows(sql, params)
        return [dict(row) for row in rows]

    def list_session_context_sources(
        self: SQLiteStore, session_ids: Sequence[str], *, principal_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        """What the answers in these sessions actually came from.

        `turn_sources` is the citation record — the file, page or tool result an
        answer was grounded in. It is the closest thing Raiker has to "the
        context this work used", and the Knowledge Map never read it, which is
        why a map of the owner's work showed no files and no context.
        """
        if not session_ids:
            return []
        placeholders = ",".join("?" for _ in session_ids)
        sql = f"""SELECT session_id, kind, title, locator, tool_name, attachment_id,
                         COUNT(*) AS uses, MAX(created_at) AS last_used_at
                  FROM turn_sources
                  WHERE session_id IN ({placeholders})"""
        params: list[Any] = list(session_ids)
        if principal_id:
            sql += " AND principal_id = ?"
            params.append(principal_id)
        sql += (
            " GROUP BY session_id, kind, title, locator, tool_name, attachment_id"
            " ORDER BY last_used_at DESC LIMIT ?"
        )
        params.append(limit)
        rows = self._rows(sql, params)
        return [dict(row) for row in rows]

    def list_session_attached_files(
        self: SQLiteStore, session_ids: Sequence[str], *, owner_principal_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Files the owner attached to a conversation, by name and type.

        Metadata only — the `attachments.data` blob is never selected here. A
        map is a map; reading the bytes to draw a node would be a needless
        exposure of file content to a view that only shows its name.
        """
        if not session_ids:
            return []
        placeholders = ",".join("?" for _ in session_ids)
        sql = f"""SELECT r.session_id, r.source, a.attachment_id, a.filename,
                         a.media_type, a.byte_size, a.kind
                  FROM session_attachment_refs r
                  JOIN attachments a ON a.attachment_id = r.attachment_id
                  WHERE r.session_id IN ({placeholders})"""
        params: list[Any] = list(session_ids)
        if owner_principal_id:
            sql += " AND r.owner_principal_id = ?"
            params.append(owner_principal_id)
        sql += " ORDER BY r.created_at DESC"
        rows = self._rows(sql, params)
        return [dict(row) for row in rows]

    def sessions_for_events(self: SQLiteStore, event_ids: Sequence[str]) -> dict[str, str]:
        """`event_id -> session_id`, for events outside any paged window.

        The Knowledge Map keeps only a bounded page of recent events, so a
        memory produced months ago has a `source_event_id` the page does not
        contain. Resolving it directly is what stops that memory being drawn as
        a fact floating free of the work that produced it.
        """
        if not event_ids:
            return {}
        placeholders = ",".join("?" for _ in event_ids)
        rows = self._rows(
            f"SELECT event_id, session_id FROM events_index WHERE event_id IN ({placeholders})",
            list(event_ids),
        )
        return {str(row["event_id"]): str(row["session_id"]) for row in rows if row["session_id"]}

    def save_model_session_state(self: SQLiteStore, state: ModelSessionState) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO model_session_state
            (session_id, profile_id, model, reasoning_enabled, reasoning_effort, reasoning_mode, reasoning_budget_tokens, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.session_id,
                state.profile_id,
                state.model,
                int(state.reasoning_enabled),
                state.reasoning_effort,
                state.reasoning_mode,
                state.reasoning_budget_tokens,
                utc_now(),
            ),
        )

    def events_after_cursor(
        self: SQLiteStore, *, after_timestamp: str | None, after_seq: int | None, limit: int
    ) -> list[dict[str, Any]]:
        """Indexed events newer than the cursor, oldest first, each with a ``seq``.

        Ordered by ``(timestamp, rowid)`` and **not** by timestamp alone.
        ``utc_now()`` truncates to whole seconds, so a busy turn writes several
        events inside one; a cursor on the timestamp alone would either re-send
        that whole second every run or skip the part of it that arrived after
        the cursor was written. The rowid is insertion order, which is exactly
        the order the append-only log was written in, so it breaks the tie the
        way the log itself does.

        The event id is deliberately *not* the tie-breaker: it is a random
        UUID, so an event appended a moment later inside the same second could
        sort before the cursor and be silently skipped. An export that quietly
        loses events is the one failure this whole surface exists to avoid.
        """
        query = "SELECT rowid AS seq, * FROM events_index"
        params: list[Any] = []
        if after_timestamp:
            query += " WHERE (timestamp > ? OR (timestamp = ? AND rowid > ?))"
            params.extend([after_timestamp, after_timestamp, after_seq or 0])
        query += " ORDER BY timestamp ASC, rowid ASC LIMIT ?"
        params.append(max(1, limit))
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def get_last_event_sha256(self: SQLiteStore, session_id: str) -> str | None:
        """The hash of the event this session's next event follows.

        Invariant: the writer's *previous* and the verifier's *previous* are the
        same key, ``jsonl_offset``, the key ``verify_session_events`` walks the
        chain by. Never ``timestamp``: `utc_now()` truncates to whole seconds, so
        events a busy turn writes within one second tie, and a correctly written
        log would report `chain_intact: false`.

        `rowid` breaks any remaining tie, which covers legacy rows written before
        an offset was recorded.
        """
        row = self._row(
            "SELECT payload_sha256 FROM events_index WHERE session_id = ? "
            "ORDER BY jsonl_offset DESC, rowid DESC LIMIT 1",
            (session_id,),
        )
        return str(row["payload_sha256"]) if row else None

    def list_session_events_for_integrity(self: SQLiteStore, session_id: str) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT event_id, payload_sha256, prev_event_sha256, jsonl_path, jsonl_offset FROM events_index WHERE session_id = ? ORDER BY jsonl_offset ASC",
            (session_id,),
        )
        return [dict(row) for row in rows]

    def load_model_session_state(self: SQLiteStore, session_id: str) -> ModelSessionState | None:
        row = self._row("SELECT * FROM model_session_state WHERE session_id = ?", (session_id,))
        if row is None:
            return None
        return ModelSessionState(
            session_id=str(row["session_id"]),
            profile_id=str(row["profile_id"]),
            model=(str(row["model"]) if row["model"] else None),
            reasoning_enabled=bool(row["reasoning_enabled"]),
            reasoning_effort=row["reasoning_effort"],
            reasoning_mode=row["reasoning_mode"],
            reasoning_budget_tokens=row["reasoning_budget_tokens"],
        )


    def save_session_attachment_ref(
        self: SQLiteStore,
        *,
        session_id: str,
        attachment_id: str,
        owner_principal_id: str,
        turn_id: str,
        source: str = "uploaded",
    ) -> None:
        """Record that one attachment was carried by one session's prompt turn.

        The caller must already have confirmed that both the session and the
        attachment belong to ``owner_principal_id`` — this layer only writes the
        reference the preview route later requires.
        """
        if not (session_id and attachment_id and owner_principal_id):
            return
        self._execute(
            """
            INSERT OR IGNORE INTO session_attachment_refs
            (session_id, attachment_id, owner_principal_id, turn_id, created_at, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, attachment_id, owner_principal_id, turn_id, utc_now(), source),
        )

    def session_attachment_ref_exists(
        self: SQLiteStore, *, session_id: str, attachment_id: str, owner_principal_id: str
    ) -> bool:
        """True only when this owner attached this file to this conversation."""
        # Every predicate is required: an empty owner, session, or attachment id
        # matches nothing rather than widening the query (fail closed).
        if not (session_id and attachment_id and owner_principal_id):
            return False
        row = self._row(
            """
            SELECT 1 FROM session_attachment_refs
            WHERE session_id = ? AND attachment_id = ? AND owner_principal_id = ?
            """,
            (session_id, attachment_id, owner_principal_id),
        )
        return row is not None

    def list_session_attachment_refs(
        self: SQLiteStore, *, session_id: str, owner_principal_id: str
    ) -> list[dict[str, Any]]:
        """Return this owner's attachment references for one session, oldest first."""
        if not (session_id and owner_principal_id):
            return []
        rows = self._rows(
            """
            SELECT attachment_id, turn_id, created_at, source FROM session_attachment_refs
            WHERE session_id = ? AND owner_principal_id = ?
            ORDER BY created_at, rowid
            """,
            (session_id, owner_principal_id),
        )
        return [dict(row) for row in rows]

    def put_session_command_grant(
        self: SQLiteStore,
        *,
        session_id: str,
        principal_id: str,
        commands: list[list[str]],
        timeout_seconds: int,
        expires_at: str,
    ) -> None:
        self._execute(
            """INSERT INTO session_command_grants
               (session_id, principal_id, commands_json, timeout_seconds, expires_at, revoked, created_at)
               VALUES (?, ?, ?, ?, ?, 0, ?)
               ON CONFLICT(session_id, principal_id) DO UPDATE SET
               commands_json=excluded.commands_json,
               timeout_seconds=excluded.timeout_seconds,
               expires_at=excluded.expires_at, revoked=0, created_at=excluded.created_at""",
            (
                session_id,
                principal_id,
                json.dumps(commands),
                timeout_seconds,
                expires_at,
                utc_now(),
            ),
        )

    def load_session_command_grant(
        self: SQLiteStore, *, session_id: str, principal_id: str
    ) -> dict[str, Any] | None:
        row = self._row(
            """SELECT * FROM session_command_grants
               WHERE session_id=? AND principal_id=? AND revoked=0 AND expires_at>?""",
            (session_id, principal_id, utc_now()),
        )
        if row is None:
            return None
        result = dict(row)
        result["commands"] = json.loads(str(result.pop("commands_json")))
        return result

    def revoke_session_command_grant(self: SQLiteStore, *, session_id: str, principal_id: str) -> None:
        self._execute(
            "UPDATE session_command_grants SET revoked=1 WHERE session_id=? AND principal_id=?",
            (session_id, principal_id),
        )
