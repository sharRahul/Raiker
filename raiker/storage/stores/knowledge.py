# mypy: disable-error-code="misc"
"""Knowledge Map sources and folder grants, and the managed files and text chunks
indexed from them (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import contextlib
import json
import secrets
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import utc_now
from raiker.storage.migrations import TEXT_SEARCH_FTS5

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class KnowledgeStore:

    def list_brain_sources(self: SQLiteStore, owner_principal_id: str) -> list[str]:
        rows = self._rows(
            "SELECT path FROM brain_sources WHERE owner_principal_id = ? ORDER BY created_at, path",
            (owner_principal_id,),
        )
        return [str(row["path"]) for row in rows]

    def add_brain_source(self: SQLiteStore, owner_principal_id: str, path: str) -> None:
        self._execute(
            "INSERT OR IGNORE INTO brain_sources (owner_principal_id, path, created_at) VALUES (?, ?, ?)",
            (owner_principal_id, path, utc_now()),
        )

    # A grant is the owner naming a folder on this machine that the Knowledge
    # Map may read *where it is*. It is stored so it can be shown back and
    # revoked; nothing is copied into the workspace by recording one.

    def list_brain_source_grants(self: SQLiteStore, owner_principal_id: str) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT root_id, path, label, created_at, write_enabled FROM brain_source_grants "
            "WHERE owner_principal_id = ? ORDER BY created_at, path",
            (owner_principal_id,),
        )
        return [dict(row) for row in rows]

    def add_brain_source_grant(
        self: SQLiteStore, owner_principal_id: str, root_id: str, path: str, label: str
    ) -> None:
        self._execute(
            "INSERT INTO brain_source_grants "
            "(owner_principal_id, root_id, path, label, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(owner_principal_id, root_id) DO UPDATE SET path = excluded.path, "
            "label = excluded.label",
            (owner_principal_id, root_id, path, label, utc_now()),
        )

    def set_grant_write_enabled(self: SQLiteStore, owner_principal_id: str, root_id: str, enabled: bool) -> bool:
        """Record whether Raiker may write into one granted folder.

        A separate decision from the grant itself: reading a folder and editing
        it are not the same permission, and the Knowledge Map's grants stay
        read-only however a project uses them.
        """
        updated = self._execute(
            "UPDATE brain_source_grants SET write_enabled = ? "
            "WHERE owner_principal_id = ? AND root_id = ?",
            (1 if enabled else 0, owner_principal_id, root_id),
        )
        return updated == 1

    def remove_brain_source_grant(self: SQLiteStore, owner_principal_id: str, root_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM brain_source_grants WHERE owner_principal_id = ? AND root_id = ?",
                (owner_principal_id, root_id),
            )
            # Revoking the grant revokes what was indexed under it: leaving the
            # sources behind would keep reading a folder the owner just said
            # Raiker may not read.
            connection.execute(
                "DELETE FROM brain_sources WHERE owner_principal_id = ? "
                "AND (path = ? OR path LIKE ?)",
                (owner_principal_id, root_id, f"{root_id}/%"),
            )

    def load_brain_preferences(self: SQLiteStore, owner_principal_id: str) -> dict[str, Any]:
        row = self._row(
            "SELECT settings_json FROM brain_preferences WHERE owner_principal_id = ?",
            (owner_principal_id,),
        )
        if row is None:
            return {}
        try:
            value = json.loads(row["settings_json"])
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    def save_brain_preferences(self: SQLiteStore, owner_principal_id: str, settings: dict[str, Any]) -> str:
        updated_at = utc_now()
        self._execute(
            """INSERT INTO brain_preferences (owner_principal_id, settings_json, updated_at)
            VALUES (?, ?, ?) ON CONFLICT(owner_principal_id) DO UPDATE SET
            settings_json = excluded.settings_json, updated_at = excluded.updated_at""",
            (owner_principal_id, json.dumps(settings, sort_keys=True), updated_at),
        )
        return updated_at

    def remove_brain_source(self: SQLiteStore, owner_principal_id: str, path: str) -> None:
        self._execute(
            "DELETE FROM brain_sources WHERE owner_principal_id = ? AND path = ?",
            (owner_principal_id, path),
        )


    def insert_managed_file(
        self: SQLiteStore,
        *,
        file_id: str,
        owner_principal_id: str,
        scope_kind: str,
        project_id: str | None,
        relative_path: str,
        media_type: str,
        size_bytes: int,
        content_hash: str,
        index_state: str,
        index_error: str | None,
        created_at: str,
        updated_at: str,
        _connection: sqlite3.Connection | None = None,
    ) -> None:
        if _connection is not None:
            self._insert_managed_file(
                _connection,
                file_id=file_id,
                owner_principal_id=owner_principal_id,
                scope_kind=scope_kind,
                project_id=project_id,
                relative_path=relative_path,
                media_type=media_type,
                size_bytes=size_bytes,
                content_hash=content_hash,
                index_state=index_state,
                index_error=index_error,
                created_at=created_at,
                updated_at=updated_at,
            )
            return
        with self.connect() as connection:
            self._insert_managed_file(
                connection,
                file_id=file_id,
                owner_principal_id=owner_principal_id,
                scope_kind=scope_kind,
                project_id=project_id,
                relative_path=relative_path,
                media_type=media_type,
                size_bytes=size_bytes,
                content_hash=content_hash,
                index_state=index_state,
                index_error=index_error,
                created_at=created_at,
                updated_at=updated_at,
            )

    @staticmethod
    def _insert_managed_file(
        connection: sqlite3.Connection,
        *,
        file_id: str,
        owner_principal_id: str,
        scope_kind: str,
        project_id: str | None,
        relative_path: str,
        media_type: str,
        size_bytes: int,
        content_hash: str,
        index_state: str,
        index_error: str | None,
        created_at: str,
        updated_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO managed_files (
                file_id, owner_principal_id, scope_kind, project_id, relative_path,
                media_type, size_bytes, content_hash, index_state, index_error,
                created_at, updated_at, retired_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                file_id,
                owner_principal_id,
                scope_kind,
                project_id,
                relative_path,
                media_type,
                size_bytes,
                content_hash,
                index_state,
                index_error,
                created_at,
                updated_at,
            ),
        )

    def publish_managed_file_atomic(
        self: SQLiteStore,
        *,
        file_id: str,
        owner_principal_id: str,
        scope_kind: str,
        project_id: str | None,
        relative_path: str,
        media_type: str,
        size_bytes: int,
        content_hash: str,
        index_state: str,
        index_error: str | None,
        created_at: str,
        updated_at: str,
        publish: Callable[[], None],
    ) -> bool:
        """Publish a file and its active identity under one cross-process lock.

        SQLite's ``BEGIN IMMEDIATE`` serializes writers across processes. The
        caller's final same-directory replacement happens before commit, so a
        committed active row always names the bytes it published; a failure
        rolls back the reservation and leaves only its unique temporary file.
        """

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                active = connection.execute(
                    """
                    SELECT 1 FROM managed_files
                    WHERE owner_principal_id = ? AND scope_kind = ?
                      AND project_id IS ? AND relative_path = ? AND retired_at IS NULL
                    """,
                    (owner_principal_id, scope_kind, project_id, relative_path),
                ).fetchone()
                if active is not None:
                    connection.rollback()
                    return False
                self.insert_managed_file(
                    file_id=file_id,
                    owner_principal_id=owner_principal_id,
                    scope_kind=scope_kind,
                    project_id=project_id,
                    relative_path=relative_path,
                    media_type=media_type,
                    size_bytes=size_bytes,
                    content_hash=content_hash,
                    index_state=index_state,
                    index_error=index_error,
                    created_at=created_at,
                    updated_at=updated_at,
                    _connection=connection,
                )
                publish()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return True

    def register_discovered_file(
        self: SQLiteStore,
        *,
        file_id: str,
        owner_principal_id: str,
        scope_kind: str,
        project_id: str | None,
        relative_path: str,
        media_type: str,
        size_bytes: int,
        content_hash: str,
        source_mtime_ns: int,
    ) -> bool:
        """Catalogue bytes that are already on disk, writing no file.

        The sibling of `publish_managed_file_atomic`, for a root Raiker does not
        own: the bytes were never imported, so there is nothing to publish — only
        a row to record, plus the mtime that lets the next reconcile skip the
        file without re-reading it. Returns False when an active row for the same
        path already exists, so a racing second scan cannot double-index.
        """
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                active = connection.execute(
                    """
                    SELECT 1 FROM managed_files
                    WHERE owner_principal_id = ? AND scope_kind = ?
                      AND project_id IS ? AND relative_path = ? AND retired_at IS NULL
                    """,
                    (owner_principal_id, scope_kind, project_id, relative_path),
                ).fetchone()
                if active is not None:
                    connection.rollback()
                    return False
                self._insert_managed_file(
                    connection,
                    file_id=file_id,
                    owner_principal_id=owner_principal_id,
                    scope_kind=scope_kind,
                    project_id=project_id,
                    relative_path=relative_path,
                    media_type=media_type,
                    size_bytes=size_bytes,
                    content_hash=content_hash,
                    index_state="queued",
                    index_error=None,
                    created_at=now,
                    updated_at=now,
                )
                connection.execute(
                    "UPDATE managed_files SET source_mtime_ns = ? WHERE file_id = ?",
                    (int(source_mtime_ns), file_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return True

    def list_indexed_attached_roots(self: SQLiteStore) -> list[dict[str, Any]]:
        """Every attached project root that has something in the catalogue.

        The join is what makes "indexed" mean indexed: a project attached but
        never scanned has no rows, and watching its folder would read the
        owner's disk continuously to keep an index that does not exist current.
        Returns the owner principal alongside, because every downstream call —
        grants, reconcile, retirement — is owner-scoped.
        """
        rows = self._rows(
            """
            SELECT DISTINCT p.project_id AS project_id,
                   g.owner_principal_id AS owner_principal_id,
                   g.path AS path
            FROM projects p
            JOIN brain_source_grants g ON g.root_id = p.root_grant_id
            JOIN managed_files m
              ON m.project_id = p.project_id
             AND m.owner_principal_id = g.owner_principal_id
             AND m.retired_at IS NULL
            WHERE p.root_kind = 'attached' AND p.root_grant_id IS NOT NULL
            """,
        )
        return [dict(row) for row in rows]

    def set_managed_file_source_mtime(
        self: SQLiteStore, file_id: str, owner_principal_id: str, mtime_ns: int
    ) -> bool:
        updated = self._execute(
            "UPDATE managed_files SET source_mtime_ns = ? "
            "WHERE file_id = ? AND owner_principal_id = ?",
            (int(mtime_ns), file_id, owner_principal_id),
        )
        return updated == 1

    def list_managed_files(
        self: SQLiteStore,
        owner_principal_id: str,
        *,
        scope_kind: str | None = None,
        project_id: str | None = None,
        include_retired: bool = False,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM managed_files WHERE owner_principal_id = ?"
        parameters: list[Any] = [owner_principal_id]
        if scope_kind is not None:
            query += " AND scope_kind = ?"
            parameters.append(scope_kind)
        if project_id is not None:
            query += " AND project_id = ?"
            parameters.append(project_id)
        if not include_retired:
            query += " AND retired_at IS NULL"
        query += " ORDER BY created_at, file_id"
        rows = self._rows(query, parameters)
        return [dict(row) for row in rows]

    def get_managed_file(self: SQLiteStore, file_id: str, owner_principal_id: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM managed_files WHERE file_id = ? AND owner_principal_id = ?",
            (file_id, owner_principal_id),
        )
        return dict(row) if row else None

    def set_managed_file_index_state(
        self: SQLiteStore,
        file_id: str,
        owner_principal_id: str,
        index_state: str,
        index_error: str | None = None,
    ) -> bool:
        updated = self._execute(
            """
            UPDATE managed_files
            SET index_state = ?, index_error = ?, updated_at = ?
            WHERE file_id = ? AND owner_principal_id = ? AND retired_at IS NULL
            """,
            (index_state, index_error, utc_now(), file_id, owner_principal_id),
        )
        return updated == 1

    def retire_managed_file(self: SQLiteStore, file_id: str, owner_principal_id: str) -> bool:
        now = utc_now()
        retired = self._execute(
            """
            UPDATE managed_files
            SET index_state = 'retired', index_error = NULL, updated_at = ?, retired_at = ?
            WHERE file_id = ? AND owner_principal_id = ? AND retired_at IS NULL
            """,
            (now, now, file_id, owner_principal_id),
        )
        return retired == 1


    @staticmethod
    def _rebuild_managed_file_chunk_fts(connection: sqlite3.Connection) -> None:
        """Recompute the lexical index from the rows that own the text."""
        connection.execute("DELETE FROM managed_file_chunk_fts")
        connection.execute(
            """
            INSERT INTO managed_file_chunk_fts (chunk_id, file_id, text)
            SELECT chunk_id, file_id, text FROM managed_file_chunks
            """
        )

    def replace_managed_file_chunks(
        self: SQLiteStore,
        *,
        file_id: str,
        owner_principal_id: str,
        scope_kind: str,
        project_id: str | None,
        content_hash: str,
        chunks: Sequence[str],
    ) -> int:
        """Publish one revision's chunks, retiring every earlier revision first.

        Retirement and publication share a transaction so a reader never sees two
        revisions of one file at once, and never sees none of a file whose bytes
        are still stored.
        """
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._delete_managed_file_chunks(connection, file_id)
                for index, text in enumerate(chunks):
                    chunk_id = f"mchunk_{secrets.token_hex(12)}"
                    connection.execute(
                        """
                        INSERT INTO managed_file_chunks (
                            chunk_id, file_id, owner_principal_id, scope_kind, project_id,
                            chunk_index, content_hash, text, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk_id,
                            file_id,
                            owner_principal_id,
                            scope_kind,
                            project_id,
                            index,
                            content_hash,
                            text,
                            now,
                        ),
                    )
                    connection.execute(
                        "INSERT INTO managed_file_chunk_fts (chunk_id, file_id, text) "
                        "VALUES (?, ?, ?)",
                        (chunk_id, file_id, text),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return len(chunks)

    @staticmethod
    def _delete_managed_file_chunks(connection: sqlite3.Connection, file_id: str) -> int:
        vector_rows = connection.execute(
            """SELECT v.vector_id FROM managed_file_chunk_vectors v
               JOIN managed_file_chunks c ON c.chunk_id = v.chunk_id
               WHERE c.file_id = ?""",
            (file_id,),
        ).fetchall()
        vector_ids = [str(row["vector_id"]) for row in vector_rows]
        connection.execute(
            """DELETE FROM managed_file_chunk_vectors WHERE chunk_id IN
               (SELECT chunk_id FROM managed_file_chunks WHERE file_id = ?)""",
            (file_id,),
        )
        if vector_ids:
            placeholders = ",".join("?" for _ in vector_ids)
            connection.execute(
                f"DELETE FROM vector_records WHERE vector_id IN ({placeholders})", vector_ids
            )
        deleted = connection.execute(
            "DELETE FROM managed_file_chunks WHERE file_id = ?", (file_id,)
        ).rowcount
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute("DELETE FROM managed_file_chunk_fts WHERE file_id = ?", (file_id,))
        return int(deleted or 0)

    def list_managed_file_chunks(
        self: SQLiteStore, file_id: str, owner_principal_id: str
    ) -> list[dict[str, Any]]:
        rows = self._rows(
            """
            SELECT managed_file_chunks.*, managed_file_chunks.file_id AS source_file_id
            FROM managed_file_chunks
            WHERE file_id = ? AND owner_principal_id = ?
            ORDER BY chunk_index
            """,
            (file_id, owner_principal_id),
        )
        return [dict(row) for row in rows]

    def retire_managed_file_chunks(self: SQLiteStore, file_id: str, owner_principal_id: str) -> int:
        """Drop every projection of *file_id*. Ownership is checked, not assumed."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                owned = connection.execute(
                    "SELECT 1 FROM managed_files WHERE file_id = ? AND owner_principal_id = ?",
                    (file_id, owner_principal_id),
                ).fetchone()
                if owned is None:
                    connection.rollback()
                    return 0
                removed = self._delete_managed_file_chunks(connection, file_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return removed

    def search_managed_file_chunks(
        self: SQLiteStore,
        query: str,
        *,
        owner_principal_id: str,
        project_ids: Sequence[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Chunks matching *query* for one owner, with file provenance attached.

        ``project_ids`` is the Build boundary: when it is given, only account
        memory files and files belonging to those projects can match. ``None`` is
        Chat's owner-wide boundary. Either way the owner filter is applied first
        and is never optional.
        """
        if limit < 1 or not owner_principal_id:
            return []
        terms = self._match_terms(query)
        conditions = [
            "managed_file_chunks.owner_principal_id = ?",
            "managed_files.retired_at IS NULL",
        ]
        params: list[Any] = [owner_principal_id]
        ordering = "managed_file_chunks.created_at DESC, managed_file_chunks.chunk_index ASC"
        if terms:
            source = (
                "managed_file_chunk_fts "
                "JOIN managed_file_chunks "
                "ON managed_file_chunks.chunk_id = managed_file_chunk_fts.chunk_id "
                "JOIN managed_files ON managed_files.file_id = managed_file_chunks.file_id"
            )
            selected = f"{self._snippet_expression('managed_file_chunk_fts', 2)} AS snippet"
            conditions.append("managed_file_chunk_fts MATCH ?")
            params.append(self._match_expression(terms))
            if self.resolved_text_search_engine() == TEXT_SEARCH_FTS5:
                ordering = "bm25(managed_file_chunk_fts, 0.0, 0.0, 1.0) ASC, " + ordering
        else:
            # Terms below the tokenizer's floor still have to be findable, so a
            # bounded substring scan stands in -- with no score, hence no reorder.
            source = (
                "managed_file_chunks "
                "JOIN managed_files ON managed_files.file_id = managed_file_chunks.file_id"
            )
            selected = "SUBSTR(managed_file_chunks.text, 1, 220) AS snippet"
            conditions.append("managed_file_chunks.text LIKE ?")
            params.append(f"%{query.strip()}%")
        if project_ids is not None:
            placeholders = ",".join("?" for _ in project_ids)
            if placeholders:
                conditions.append(
                    "(managed_file_chunks.scope_kind = 'memory' "
                    f"OR managed_file_chunks.project_id IN ({placeholders}))"
                )
                params.extend(project_ids)
            else:
                conditions.append("managed_file_chunks.scope_kind = 'memory'")
        params.append(limit)
        sql = (
            "SELECT managed_file_chunks.chunk_id AS chunk_id, "
            "managed_file_chunks.file_id AS file_id, "
            "managed_file_chunks.chunk_index AS chunk_index, "
            "managed_file_chunks.text AS text, "
            "managed_file_chunks.scope_kind AS scope_kind, "
            "managed_file_chunks.project_id AS project_id, "
            "managed_file_chunks.content_hash AS content_hash, "
            "managed_files.relative_path AS relative_path, "
            "managed_files.media_type AS media_type, "
            f"{selected} FROM {source} "
            f"WHERE {' AND '.join(conditions)} "
            f"ORDER BY {ordering} LIMIT ?"
        )
        with self.connect() as connection:
            try:
                rows = connection.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(row) for row in rows]
