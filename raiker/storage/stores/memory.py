# mypy: disable-error-code="misc"
"""Durable memory: candidates, approved records, entities and relationships, their
projections and vectors, and the maintenance jobs over them (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import SemanticMemoryWriteRecord, VectorRecord
from raiker.storage.migrations import TEXT_SEARCH_FTS5

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class MemoryStore:

    def list_managed_file_chunks_missing_embedding(
        self: SQLiteStore,
        embedding_model: str,
        *,
        owner_principal_id: str,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        if limit < 1 or not owner_principal_id:
            return []
        rows = self._rows(
            """
            SELECT c.* FROM managed_file_chunks c
            JOIN managed_files f ON f.file_id = c.file_id
            WHERE c.owner_principal_id = ? AND f.retired_at IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM managed_file_chunk_vectors v
                WHERE v.chunk_id = c.chunk_id AND v.embedding_model = ?
              )
            ORDER BY c.created_at, c.file_id, c.chunk_index
            LIMIT ?
            """,
            (owner_principal_id, embedding_model, min(limit * 4, 2000)),
        )
        from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity

        blocked = {MemorySensitivity.SECRET_LIKE, MemorySensitivity.CREDENTIAL_LIKE}
        return [
            dict(row)
            for row in rows
            if classify_memory_sensitivity(str(row["text"])) not in blocked
        ][:limit]

    def link_managed_file_chunk_vector(
        self: SQLiteStore,
        chunk_id: str,
        vector_id: str,
        embedding_model: str,
        content_hash: str,
        *,
        owner_principal_id: str,
    ) -> bool:
        """Link a vector only while the exact owned chunk revision exists."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT 1 FROM managed_file_chunks
                   WHERE chunk_id = ? AND owner_principal_id = ? AND content_hash = ?""",
                (chunk_id, owner_principal_id, content_hash),
            ).fetchone()
            if row is None:
                return False
            previous = connection.execute(
                """SELECT vector_id FROM managed_file_chunk_vectors
                   WHERE chunk_id = ? AND embedding_model = ?""",
                (chunk_id, embedding_model),
            ).fetchone()
            connection.execute(
                """INSERT OR REPLACE INTO managed_file_chunk_vectors
                   (chunk_id, vector_id, embedding_model, content_hash)
                   VALUES (?, ?, ?, ?)""",
                (chunk_id, vector_id, embedding_model, content_hash),
            )
            if previous is not None and str(previous["vector_id"]) != vector_id:
                connection.execute(
                    "DELETE FROM vector_records WHERE vector_id = ?",
                    (str(previous["vector_id"]),),
                )
        return True

    def search_managed_file_chunk_vectors(
        self: SQLiteStore,
        query_vector: Sequence[float],
        embedding_model: str,
        *,
        owner_principal_id: str,
        project_ids: Sequence[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Cosine-ranked owned chunks in one named embedding space."""
        if not query_vector or limit < 1 or not owner_principal_id:
            return []
        conditions = [
            "c.owner_principal_id = ?",
            "f.retired_at IS NULL",
            "m.embedding_model = ?",
        ]
        params: list[Any] = [owner_principal_id, embedding_model]
        if project_ids is not None:
            placeholders = ",".join("?" for _ in project_ids)
            if placeholders:
                conditions.append(f"(c.scope_kind = 'memory' OR c.project_id IN ({placeholders}))")
                params.extend(project_ids)
            else:
                conditions.append("c.scope_kind = 'memory'")
        rows = self._rows(
            """SELECT c.*, f.relative_path, f.media_type, r.embedding
               FROM managed_file_chunk_vectors m
               JOIN managed_file_chunks c ON c.chunk_id = m.chunk_id
               JOIN managed_files f ON f.file_id = c.file_id
               JOIN vector_records r ON r.vector_id = m.vector_id
               WHERE """
            + " AND ".join(conditions),
            params,
        )
        from raiker.vector import VectorIndex

        ranked: list[tuple[float, dict[str, Any]]] = []
        for raw in rows:
            row = dict(raw)
            try:
                vector = json.loads(str(row.pop("embedding")))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(vector, list) or len(vector) != len(query_vector):
                continue
            if not all(isinstance(value, (int, float)) for value in vector):
                continue
            score = VectorIndex._cosine_similarity(  # noqa: SLF001
                [float(value) for value in query_vector],
                [float(value) for value in vector],
            )
            row["score"] = round(score, 6)
            row["snippet"] = str(row.get("text", ""))[:220]
            row["sources"] = ["vector"]
            ranked.append((score, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in ranked[:limit]]

    # memory_pins is an organizing label only (like session/project pins) —
    # it grants nothing and changes no authority. memory_settings.incognito
    # is a single-row flag (one scope) that, when on, withholds approved
    # project memory from the turn context (the context gatherer reads it).

    MEMORY_SETTINGS_SCOPE = "local_single_user"

    def set_memory_pinned(self: SQLiteStore, memory_id: str, pinned: bool) -> None:
        self._execute(
            """
            INSERT INTO memory_pins (memory_id, pinned, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET pinned = excluded.pinned, updated_at = excluded.updated_at
            """,
            (memory_id, 1 if pinned else 0, utc_now()),
        )

    def list_pinned_memory_ids(self: SQLiteStore) -> set[str]:
        rows = self._rows("SELECT memory_id FROM memory_pins WHERE pinned = 1")
        return {str(row["memory_id"]) for row in rows}

    def is_memory_incognito(self: SQLiteStore, owner_principal_id: str | None = None) -> bool:
        scope_id = (
            f"{self.MEMORY_SETTINGS_SCOPE}:{owner_principal_id}"
            if owner_principal_id
            else self.MEMORY_SETTINGS_SCOPE
        )
        with self.connect() as connection:
            row = connection.execute(
                "SELECT incognito FROM memory_settings WHERE scope_id = ?",
                (scope_id,),
            ).fetchone()
            if row is None and owner_principal_id is None:
                original = self._original_owner_from_connection(connection)
                if original is not None:
                    row = connection.execute(
                        "SELECT incognito FROM memory_settings WHERE scope_id = ?",
                        (f"{self.MEMORY_SETTINGS_SCOPE}:{original}",),
                    ).fetchone()
        return bool(row["incognito"]) if row is not None else False

    def set_memory_incognito(self: SQLiteStore, incognito: bool, owner_principal_id: str | None = None) -> None:
        if owner_principal_id is None:
            owner_principal_id = self.original_account_principal_id()
        self._execute(
            """
            INSERT INTO memory_settings (scope_id, incognito, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(scope_id) DO UPDATE SET incognito = excluded.incognito, updated_at = excluded.updated_at
            """,
            (
                f"{self.MEMORY_SETTINGS_SCOPE}:{owner_principal_id}"
                if owner_principal_id
                else self.MEMORY_SETTINGS_SCOPE,
                1 if incognito else 0,
                utc_now(),
            ),
        )


    def get_memory_embedding_backend(self: SQLiteStore, owner_principal_id: str | None = None) -> str:
        """The embedding space this owner chose, or ``auto``.

        Read exactly like ``is_memory_incognito``, including its fall back to
        the original account's row, so a workspace bootstrapped from the CLI
        does not silently answer with a different setting than the one the web
        surface writes.
        """
        scope_id = (
            f"{self.MEMORY_SETTINGS_SCOPE}:{owner_principal_id}"
            if owner_principal_id
            else self.MEMORY_SETTINGS_SCOPE
        )
        with self.connect() as connection:
            row = connection.execute(
                "SELECT embedding_backend FROM memory_settings WHERE scope_id = ?", (scope_id,)
            ).fetchone()
            if row is None and owner_principal_id is None:
                original = self._original_owner_from_connection(connection)
                if original is not None:
                    row = connection.execute(
                        "SELECT embedding_backend FROM memory_settings WHERE scope_id = ?",
                        (f"{self.MEMORY_SETTINGS_SCOPE}:{original}",),
                    ).fetchone()
        return (
            str(row["embedding_backend"])
            if row is not None and row["embedding_backend"]
            else "auto"
        )

    def set_memory_embedding_backend(
        self: SQLiteStore, backend: str, owner_principal_id: str | None = None
    ) -> None:
        if owner_principal_id is None:
            owner_principal_id = self.original_account_principal_id()
        scope_id = (
            f"{self.MEMORY_SETTINGS_SCOPE}:{owner_principal_id}"
            if owner_principal_id
            else self.MEMORY_SETTINGS_SCOPE
        )
        self._execute(
            """
            INSERT INTO memory_settings (scope_id, incognito, embedding_backend, updated_at)
            VALUES (?, 0, ?, ?)
            ON CONFLICT(scope_id) DO UPDATE SET
              embedding_backend = excluded.embedding_backend,
              updated_at = excluded.updated_at
            """,
            (scope_id, backend, utc_now()),
        )

    def list_memories_missing_embedding(
        self: SQLiteStore,
        embedding_model: str | None,
        *,
        owner_principal_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Active approved memories this owner holds no vector for in *embedding_model*.

        MEM-10 — the selectable spaces above are read from the vectors that
        exist, so an install that has never embedded anything has nothing
        semantic to offer. This is the other half of that question: which
        memories would have to be embedded before a space becomes selectable at
        all. The eligibility clauses match
        :meth:`get_active_approved_memory` exactly, so a row listed here is a
        row the executor will accept rather than refuse one at a time.

        ``embedding_model`` of ``None`` means "every eligible memory", which is
        what a caller asks for before it knows which space a provider will
        answer in.
        """
        now = utc_now()
        sql = """
        SELECT m.memory_id AS memory_id
        FROM approved_memory m
        WHERE m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
          AND m.sensitivity NOT IN ('secret_like', 'credential_like')
          AND (m.expires_at IS NULL OR m.expires_at > ?)
          AND (m.valid_from IS NULL OR m.valid_from <= ?)
          AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL
        """
        params: list[Any] = [now, now, now]
        if embedding_model is not None:
            sql += """
          AND NOT EXISTS (
            SELECT 1 FROM memory_projections p
            JOIN vector_records v ON v.vector_id = p.projection_id
            WHERE p.memory_id = m.memory_id AND p.projection_type = 'vector'
              AND v.embedding IS NOT NULL AND v.embedding_model = ?
          )
            """
            params.append(embedding_model)
        if owner_principal_id:
            sql += " AND m.owner_principal_id = ?"
            params.append(owner_principal_id)
        sql += " ORDER BY m.memory_id LIMIT ?"
        params.append(max(1, int(limit)))
        rows = self._rows(sql, params)
        return [dict(row) for row in rows]

    def stored_memory_checksums(
        self: SQLiteStore, *, owner_principal_id: str | None = None
    ) -> dict[tuple[str, str], str]:
        """``(content_checksum, scope)`` → ``memory_id`` for what this owner holds.

        BUG-244 — the read that lets an import ask before it writes, so import
        cannot create a duplicate where every other path records a correction
        or a supersession link.

        Two deliberate choices:

        * **Scope is part of the key.** The same sentence at ``project`` scope
          and at ``global`` scope is two records an owner may genuinely want;
          the same sentence twice at the same scope is not.
        * **Deleted memories do not count, archived ones do.** A forgotten
          memory is gone and re-importing it is how you bring it back. An
          archived one is still stored, still occupies the store, and a second
          copy of it is still a duplicate.

        ``content_checksum`` is written on every insert and update, so nothing
        new has to be stored for this — and a row that predates the column is
        backfilled by the same migration that added it.
        """
        sql = (
            "SELECT content_checksum, scope, memory_id FROM approved_memory "
            "WHERE deleted_at IS NULL AND content_checksum IS NOT NULL"
        )
        params: list[Any] = []
        if owner_principal_id:
            sql += " AND owner_principal_id = ?"
            params.append(owner_principal_id)
        # Oldest first, so the id reported for a checksum is the record the
        # duplicate would be a copy *of*.
        sql += " ORDER BY created_at ASC, memory_id ASC"
        rows = self._rows(sql, params)
        stored: dict[tuple[str, str], str] = {}
        for row in rows:
            key = (str(row["content_checksum"]), str(row["scope"] or ""))
            stored.setdefault(key, str(row["memory_id"]))
        return stored

    def list_memory_embedding_spaces(
        self: SQLiteStore, *, owner_principal_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Every ``(model, dimensions)`` this workspace can recall from.

        Active approved-memory and current managed-file projections both count.
        A space whose every source was archived or retired is not one a search
        could answer from, and offering it would be offering an empty corpus.
        """
        now = utc_now()
        sql = """
        SELECT v.embedding_model AS embedding_model, v.dimensions AS dimensions,
               COUNT(*) AS vector_count
        FROM vector_records v
        JOIN memory_projections p ON p.projection_id = v.vector_id
          AND p.projection_type = 'vector' AND p.active = 1
        JOIN approved_memory m ON m.memory_id = p.memory_id
        WHERE v.embedding IS NOT NULL AND m.deleted_at IS NULL AND m.archived_at IS NULL
          AND m.sensitivity NOT IN ('secret_like', 'credential_like')
          AND m.search_enabled = 1 AND (m.expires_at IS NULL OR m.expires_at > ?)
          AND (m.valid_from IS NULL OR m.valid_from <= ?)
          AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL
        """
        params: list[Any] = [now, now, now]
        if owner_principal_id:
            sql += " AND m.owner_principal_id = ?"
            params.append(owner_principal_id)
        sql += " GROUP BY v.embedding_model, v.dimensions ORDER BY v.embedding_model"
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
            file_sql = """
                SELECT v.embedding_model AS embedding_model,
                       v.dimensions AS dimensions, COUNT(*) AS vector_count
                FROM vector_records v
                JOIN managed_file_chunk_vectors p ON p.vector_id = v.vector_id
                JOIN managed_file_chunks c ON c.chunk_id = p.chunk_id
                JOIN managed_files f ON f.file_id = c.file_id
                WHERE v.embedding IS NOT NULL AND f.retired_at IS NULL
            """
            file_params: list[Any] = []
            if owner_principal_id:
                file_sql += " AND c.owner_principal_id = ?"
                file_params.append(owner_principal_id)
            file_sql += " GROUP BY v.embedding_model, v.dimensions"
            file_rows = connection.execute(file_sql, file_params).fetchall()
        merged: dict[tuple[str, int], int] = {}
        for raw in [*rows, *file_rows]:
            row = dict(raw)
            key = (str(row["embedding_model"]), int(row["dimensions"]))
            merged[key] = merged.get(key, 0) + int(row["vector_count"])
        return [
            {"embedding_model": model, "dimensions": dimensions, "vector_count": count}
            for (model, dimensions), count in sorted(merged.items())
        ]

    def insert_memory_candidate(
        self: SQLiteStore, candidate: Any, *, owner_principal_id: str | None = None
    ) -> bool:
        changed = self._execute(
            """
            INSERT OR IGNORE INTO memory_candidates
            (candidate_id, source_event_id, memory_type, scope, text, sensitivity,
             confidence, decision, created_at, owner_principal_id,
             source_session_id, source_turn_id, source_role, extractor_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.candidate_id,
                candidate.source_event_id,
                candidate.memory_type,
                candidate.scope,
                candidate.text,
                candidate.sensitivity,
                candidate.confidence,
                candidate.decision,
                candidate.created_at,
                owner_principal_id,
                getattr(candidate, "source_session_id", None),
                getattr(candidate, "source_turn_id", None),
                getattr(candidate, "source_role", None),
                getattr(candidate, "extractor_version", None),
            ),
        )
        return changed > 0

    def list_memory_candidates(
        self: SQLiteStore, decision: str | None = None, *, owner_principal_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM memory_candidates"
        params: list[Any] = []
        if decision is not None:
            query += " WHERE decision = ?"
            params.append(decision)
        if owner_principal_id is not None:
            query += " AND" if params else " WHERE"
            query += " owner_principal_id = ?"
            params.append(owner_principal_id)
        query += " ORDER BY created_at DESC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def get_memory_candidate(
        self: SQLiteStore, candidate_id: str, *, owner_principal_id: str
    ) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM memory_candidates WHERE candidate_id = ? AND owner_principal_id = ?",
            (candidate_id, owner_principal_id),
        )
        return dict(row) if row else None

    def resolve_memory_candidate(
        self: SQLiteStore,
        candidate_id: str,
        *,
        owner_principal_id: str,
        expected_decision: str,
        decision: str,
        reason: str | None,
        resolved_at: str,
    ) -> bool:
        """Resolve exactly one proposal without allowing stale double decisions."""
        changed = self._execute(
            """UPDATE memory_candidates
            SET decision = ?, reason = ?, resolved_at = ?
            WHERE candidate_id = ? AND owner_principal_id = ? AND decision = ?""",
            (
                decision,
                reason,
                resolved_at,
                candidate_id,
                owner_principal_id,
                expected_decision,
            ),
        )
        return changed == 1

    def insert_approved_memory(self: SQLiteStore, entry: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO approved_memory
                (memory_id, text, scope, sensitivity, source_event_id, memory_type, created_at, tags_json, source, provenance_json, confidence, trust_score, retention, approval_state, created_by, updated_at, deleted_at, archived_at, search_enabled, expires_at, valid_from, valid_until, supersedes_memory_id, superseded_at, remembered_reason, content_checksum, owner_principal_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.memory_id,
                    entry.text,
                    entry.scope,
                    entry.sensitivity,
                    entry.source_event_id,
                    entry.memory_type,
                    entry.created_at,
                    json.dumps(list(entry.tags)),
                    entry.source,
                    json.dumps(entry.provenance, sort_keys=True),
                    entry.confidence,
                    entry.trust_score,
                    entry.retention,
                    entry.approval_state,
                    entry.created_by,
                    entry.updated_at,
                    entry.deleted_at,
                    entry.archived_at,
                    int(entry.search_enabled),
                    entry.expires_at,
                    entry.valid_from or entry.created_at,
                    entry.valid_until,
                    entry.supersedes_memory_id,
                    entry.superseded_at,
                    entry.remembered_reason,
                    hashlib.sha256(entry.text.encode()).hexdigest(),
                    entry.owner_principal_id,
                ),
            )
            self._sync_memory_fts(connection, entry.memory_id)
            self._sync_memory_projection_eligibility(connection, entry.memory_id)

    def update_approved_memory(self: SQLiteStore, entry: Any) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE approved_memory SET text = ?, content_checksum = ?, scope = ?, sensitivity = ?, tags_json = ?, updated_at = ?,
                search_enabled = ?, expires_at = ?, valid_from = ?, valid_until = ?,
                supersedes_memory_id = ?, superseded_at = ?, remembered_reason = ?
                WHERE memory_id = ? AND deleted_at IS NULL"""
                + (" AND owner_principal_id = ?" if entry.owner_principal_id else ""),
                (
                    entry.text,
                    hashlib.sha256(entry.text.encode()).hexdigest(),
                    entry.scope,
                    entry.sensitivity,
                    json.dumps(list(entry.tags)),
                    entry.updated_at,
                    int(entry.search_enabled),
                    entry.expires_at,
                    entry.valid_from or entry.created_at,
                    entry.valid_until,
                    entry.supersedes_memory_id,
                    entry.superseded_at,
                    entry.remembered_reason,
                    entry.memory_id,
                    *([entry.owner_principal_id] if entry.owner_principal_id else []),
                ),
            )
            self._sync_memory_fts(connection, entry.memory_id)
            self._sync_memory_projection_eligibility(connection, entry.memory_id)
        return cursor.rowcount > 0

    def supersede_approved_memory(
        self: SQLiteStore, memory_id: str, replacement_id: str, *, at: str, owner_principal_id: str | None = None
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE approved_memory SET approval_state = 'superseded', valid_until = ?, superseded_at = ?,
                updated_at = ? WHERE memory_id = ? AND deleted_at IS NULL AND superseded_at IS NULL"""
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (at, at, at, memory_id, *([owner_principal_id] if owner_principal_id else [])),
            )
            self._sync_memory_fts(connection, memory_id)
            self._sync_memory_projection_eligibility(connection, memory_id)
            connection.execute(
                "UPDATE approved_memory SET supersedes_memory_id = ? WHERE memory_id = ?"
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (memory_id, replacement_id, *([owner_principal_id] if owner_principal_id else [])),
            )
        return cursor.rowcount > 0

    def create_memory_evaluation_run(self: SQLiteStore, report: Any, *, strategy: str | None = None) -> str:
        from raiker.contracts.ids import new_id

        evaluation_id = new_id("mev_")
        self._execute(
            """INSERT INTO memory_evaluation_runs (
                evaluation_id, corpus_version, strategy, case_count, precision_at_k,
                recall_at_k, mean_reciprocal_rank, ndcg_at_k, policy_leak_count,
                p50_latency_ms, p95_latency_ms, token_count, compute_cost_usd,
                storage_bytes, created_at, backend_version, scope, workload,
                latency_distribution_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                evaluation_id,
                report.corpus_version,
                strategy or report.strategy,
                report.case_count,
                report.precision_at_k,
                report.recall_at_k,
                report.mean_reciprocal_rank,
                report.ndcg_at_k,
                report.policy_leak_count,
                report.p50_latency_ms,
                report.p95_latency_ms,
                report.token_count,
                report.compute_cost_usd,
                report.storage_bytes,
                utc_now(),
                report.backend_version,
                report.scope,
                report.workload,
                json.dumps(report.latency_distribution, sort_keys=True),
            ),
        )
        return evaluation_id

    def upsert_memory_entity(self: SQLiteStore, entity_id: str, name: str, entity_type: str) -> None:
        normalized_name = " ".join(name.casefold().split())
        if not normalized_name or not entity_type.strip():
            raise ValueError("invalid_memory_entity")
        now = utc_now()
        self._execute(
            """INSERT INTO memory_entities VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_name, entity_type) DO UPDATE SET display_name = excluded.display_name, updated_at = excluded.updated_at""",
            (entity_id, normalized_name, name.strip(), entity_type.strip(), now, now),
        )

    def match_memory_entities(
        self: SQLiteStore,
        query: str,
        *,
        limit: int = 3,
        owner_principal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Entities this query actually names (MEM-12).

        The graph leg of hybrid retrieval needs somewhere to start, and until now
        the only way to give it one was for the caller to already know an
        ``entity_id`` — which the context gatherer never does, so the leg never
        ran on a real turn. This resolves the anchor from the words the owner
        typed.

        Matching is on ``normalized_name`` against whole query terms, using the
        same case-folding and whitespace collapse ``upsert_memory_entity``
        applies, so "the NAS" and "nas" resolve alike. Deliberately **not** a
        substring or prefix match: `LIKE '%term%'` over an unindexed column
        would make "id" match every entity containing those two letters, and a
        graph traversal seeded from a coincidence is worse than no traversal —
        it adds unrelated memories to a turn's context wearing the label
        "recalled".

        A multi-word entity ("encrypted nas") is matched by its whole normalized
        name appearing in the query, which is why the full query is compared as
        well as each term.
        """
        if limit < 1:
            return []
        collapsed = " ".join(query.casefold().split())
        if not collapsed:
            return []
        terms = {term for term in collapsed.split() if len(term) >= 3}
        if not terms:
            return []
        placeholders = ",".join("?" for _ in terms)
        owner_filter = ""
        params: list[Any] = [*sorted(terms), collapsed]
        if owner_principal_id:
            owner_filter = """ AND EXISTS (
                SELECT 1 FROM memory_entity_relationships r
                JOIN approved_memory m ON m.memory_id = r.evidence_memory_id
                WHERE r.active = 1
                  AND (r.subject_entity_id = memory_entities.entity_id
                       OR r.object_entity_id = memory_entities.entity_id)
                  AND m.owner_principal_id = ?
                  AND m.deleted_at IS NULL AND m.archived_at IS NULL
                  AND m.search_enabled = 1
                  AND m.sensitivity NOT IN ('secret_like', 'credential_like')
                  AND (m.expires_at IS NULL OR m.expires_at > ?)
                  AND (m.valid_from IS NULL OR m.valid_from <= ?)
                  AND (m.valid_until IS NULL OR m.valid_until > ?)
                  AND m.superseded_at IS NULL
            )"""
            now = utc_now()
            params.extend([owner_principal_id, now, now, now])
        params.append(limit)
        rows = self._rows(
            f"""SELECT entity_id, display_name, entity_type, normalized_name
                FROM memory_entities
                WHERE (normalized_name IN ({placeholders})
                   OR (INSTR(' ' || ? || ' ', ' ' || normalized_name || ' ') > 0
                       AND LENGTH(normalized_name) >= 3))
                {owner_filter}
                ORDER BY LENGTH(normalized_name) DESC, normalized_name
                LIMIT ?""",
            params,
        )
        return [dict(row) for row in rows]

    def link_memory_entities(
        self: SQLiteStore,
        relationship_id: str,
        subject_entity_id: str,
        predicate: str,
        object_entity_id: str,
        evidence_memory_id: str,
        confidence: float,
    ) -> None:
        if (
            not predicate.strip()
            or not 0 <= confidence <= 1
            or self.get_active_approved_memory(evidence_memory_id) is None
        ):
            raise ValueError("invalid_memory_relationship")
        self._execute(
            "INSERT OR IGNORE INTO memory_entity_relationships VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (
                relationship_id,
                subject_entity_id,
                predicate.strip(),
                object_entity_id,
                evidence_memory_id,
                confidence,
                utc_now(),
            ),
        )
        self.link_memory_projection(
            evidence_memory_id, "graph", relationship_id, "memory-entity-v1"
        )

    def create_memory_relationship_candidate(
        self: SQLiteStore,
        candidate_id: str,
        *,
        subject_name: str,
        subject_type: str,
        predicate: str,
        object_name: str,
        object_type: str,
        evidence_memory_id: str,
        confidence: float,
        owner_principal_id: str | None = None,
        extractor_version: str = "manual-v1",
    ) -> bool:
        if not all(
            value.strip()
            for value in (subject_name, subject_type, predicate, object_name, object_type)
        ):
            raise ValueError("invalid_memory_relationship_candidate")
        evidence = self.get_active_approved_memory(
            evidence_memory_id, owner_principal_id=owner_principal_id
        )
        if not 0 <= confidence <= 1 or evidence is None:
            raise ValueError("invalid_memory_relationship_candidate")
        owner = owner_principal_id or str(evidence.get("owner_principal_id") or "")
        if not owner or not extractor_version.strip():
            raise ValueError("invalid_memory_relationship_candidate")
        normalized_subject = " ".join(subject_name.casefold().split())
        normalized_object = " ".join(object_name.casefold().split())
        changed = self._execute(
            """INSERT OR IGNORE INTO memory_relationship_candidates
               (candidate_id, owner_principal_id, subject_name, subject_type,
                normalized_subject, predicate, object_name, object_type,
                normalized_object, evidence_memory_id, confidence, extractor_version,
                decision, created_at, resolved_at, resolved_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       'needs_user_review', ?, NULL, NULL)""",
            (
                candidate_id,
                owner,
                subject_name.strip(),
                subject_type.strip(),
                normalized_subject,
                predicate.strip(),
                object_name.strip(),
                object_type.strip(),
                normalized_object,
                evidence_memory_id,
                confidence,
                extractor_version.strip(),
                utc_now(),
            ),
        )
        return changed > 0

    def get_memory_relationship_candidate(
        self: SQLiteStore, candidate_id: str, *, owner_principal_id: str | None = None
    ) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM memory_relationship_candidates WHERE candidate_id = ?"
            + (" AND owner_principal_id = ?" if owner_principal_id else ""),
            (candidate_id, *([owner_principal_id] if owner_principal_id else [])),
        )
        return dict(row) if row else None

    def list_memory_relationship_candidates(
        self: SQLiteStore, owner_principal_id: str, *, decision: str = "needs_user_review"
    ) -> list[dict[str, Any]]:
        rows = self._rows(
            """SELECT c.*, m.text AS evidence_text,
                      m.source_event_id AS evidence_source_event_id
               FROM memory_relationship_candidates c
               JOIN approved_memory m ON m.memory_id = c.evidence_memory_id
               WHERE c.owner_principal_id = ? AND c.decision = ?
                 AND m.owner_principal_id = ?
               ORDER BY c.created_at, c.candidate_id""",
            (owner_principal_id, decision, owner_principal_id),
        )
        return [dict(row) for row in rows]

    def list_memory_relationships(self: SQLiteStore, owner_principal_id: str) -> list[dict[str, Any]]:
        """Active graph edges whose approved evidence belongs to one owner."""
        now = utc_now()
        rows = self._rows(
            """SELECT r.*, s.display_name AS subject_name,
                      s.entity_type AS subject_type,
                      o.display_name AS object_name,
                      o.entity_type AS object_type
               FROM memory_entity_relationships r
               JOIN memory_entities s ON s.entity_id = r.subject_entity_id
               JOIN memory_entities o ON o.entity_id = r.object_entity_id
               JOIN approved_memory m ON m.memory_id = r.evidence_memory_id
               WHERE r.active = 1 AND m.owner_principal_id = ?
                 AND m.deleted_at IS NULL AND m.archived_at IS NULL
                 AND m.search_enabled = 1
                 AND m.sensitivity NOT IN ('secret_like', 'credential_like')
                 AND (m.expires_at IS NULL OR m.expires_at > ?)
                 AND (m.valid_from IS NULL OR m.valid_from <= ?)
                 AND (m.valid_until IS NULL OR m.valid_until > ?)
                 AND m.superseded_at IS NULL
               ORDER BY r.created_at, r.relationship_id""",
            (owner_principal_id, now, now, now),
        )
        return [dict(row) for row in rows]

    def reject_memory_relationship(
        self: SQLiteStore,
        relationship_id: str,
        *,
        owner_principal_id: str,
        expected_active: bool = True,
    ) -> bool:
        """Deactivate one owner-evidenced edge and its projection atomically."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """UPDATE memory_entity_relationships AS r SET active = 0
                   WHERE r.relationship_id = ? AND r.active = ?
                     AND EXISTS (
                       SELECT 1 FROM approved_memory m
                       WHERE m.memory_id = r.evidence_memory_id
                         AND m.owner_principal_id = ?
                     )""",
                (relationship_id, int(expected_active), owner_principal_id),
            )
            if changed.rowcount != 1:
                return False
            connection.execute(
                """UPDATE memory_projections SET active = 0
                   WHERE projection_type = 'graph' AND projection_id = ?""",
                (relationship_id,),
            )
        return True

    def resolve_memory_relationship_candidate(
        self: SQLiteStore,
        candidate_id: str,
        *,
        decision: str,
        resolved_by: str,
    ) -> bool:
        if decision not in {"approved", "denied"} or not resolved_by.strip():
            raise ValueError("invalid_memory_relationship_resolution")
        changed = self._execute(
            """UPDATE memory_relationship_candidates SET decision = ?, resolved_at = ?, resolved_by = ?
            WHERE candidate_id = ? AND decision = 'needs_user_review'""",
            (decision, utc_now(), resolved_by, candidate_id),
        )
        return changed > 0

    def resolve_memory_relationship_candidate_atomic(
        self: SQLiteStore,
        candidate_id: str,
        *,
        owner_principal_id: str,
        decision: str,
        reviewer_id: str,
        expected_decision: str = "needs_user_review",
    ) -> str:
        if decision not in {"approved", "denied"} or not reviewer_id.strip():
            raise ValueError("invalid_memory_relationship_resolution")
        relationship_id = new_id("rel_")
        subject_id = new_id("ent_")
        object_id = new_id("ent_")
        now = utc_now()
        with self.connect() as connection:
            # Serialize the compare-and-swap before reading the candidate. A
            # deferred transaction lets two reviewers both observe "pending"
            # and makes the loser fail later with a database lock instead of
            # the stable stale-decision contract the API promises.
            connection.execute("BEGIN IMMEDIATE")
            candidate = connection.execute(
                """SELECT c.* FROM memory_relationship_candidates c
                   JOIN approved_memory m ON m.memory_id = c.evidence_memory_id
                   WHERE c.candidate_id = ? AND c.owner_principal_id = ?
                     AND c.decision = ? AND m.owner_principal_id = ?
                     AND m.deleted_at IS NULL AND m.archived_at IS NULL
                     AND m.search_enabled = 1
                     AND m.sensitivity NOT IN ('secret_like', 'credential_like')
                     AND (m.expires_at IS NULL OR m.expires_at > ?)
                     AND (m.valid_from IS NULL OR m.valid_from <= ?)
                     AND (m.valid_until IS NULL OR m.valid_until > ?)
                     AND m.superseded_at IS NULL""",
                (
                    candidate_id,
                    owner_principal_id,
                    expected_decision,
                    owner_principal_id,
                    now,
                    now,
                    now,
                ),
            ).fetchone()
            if candidate is None:
                raise ValueError("stale_memory_relationship_candidate")
            if decision == "denied":
                changed = connection.execute(
                    """UPDATE memory_relationship_candidates
                       SET decision='denied', resolved_at=?, resolved_by=?
                       WHERE candidate_id=? AND owner_principal_id=? AND decision=?""",
                    (
                        now,
                        reviewer_id,
                        candidate_id,
                        owner_principal_id,
                        expected_decision,
                    ),
                )
                if changed.rowcount != 1:
                    raise ValueError("stale_memory_relationship_candidate")
                return ""

            for entity_id, normalized, display_name, entity_type in (
                (
                    subject_id,
                    str(candidate["normalized_subject"]),
                    str(candidate["subject_name"]),
                    str(candidate["subject_type"]),
                ),
                (
                    object_id,
                    str(candidate["normalized_object"]),
                    str(candidate["object_name"]),
                    str(candidate["object_type"]),
                ),
            ):
                connection.execute(
                    """INSERT INTO memory_entities
                       (entity_id, normalized_name, display_name, entity_type, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(normalized_name, entity_type) DO UPDATE SET
                         display_name=excluded.display_name, updated_at=excluded.updated_at""",
                    (entity_id, normalized, display_name, entity_type, now, now),
                )
            subject = connection.execute(
                "SELECT entity_id FROM memory_entities WHERE normalized_name=? AND entity_type=?",
                (candidate["normalized_subject"], candidate["subject_type"]),
            ).fetchone()
            object_row = connection.execute(
                "SELECT entity_id FROM memory_entities WHERE normalized_name=? AND entity_type=?",
                (candidate["normalized_object"], candidate["object_type"]),
            ).fetchone()
            assert subject is not None and object_row is not None
            connection.execute(
                """INSERT INTO memory_entity_relationships
                   (relationship_id, subject_entity_id, predicate, object_entity_id,
                    evidence_memory_id, confidence, created_at, active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    relationship_id,
                    subject["entity_id"],
                    candidate["predicate"],
                    object_row["entity_id"],
                    candidate["evidence_memory_id"],
                    candidate["confidence"],
                    now,
                ),
            )
            changed = connection.execute(
                """UPDATE memory_relationship_candidates
                   SET decision='approved', resolved_at=?, resolved_by=?
                   WHERE candidate_id=? AND owner_principal_id=? AND decision=?""",
                (
                    now,
                    reviewer_id,
                    candidate_id,
                    owner_principal_id,
                    expected_decision,
                ),
            )
            if changed.rowcount != 1:
                raise ValueError("stale_memory_relationship_candidate")
            connection.execute(
                """INSERT OR REPLACE INTO memory_projections
                   (memory_id, projection_type, projection_id, source_version, active)
                   VALUES (?, 'graph', ?, ?, 1)""",
                (
                    candidate["evidence_memory_id"],
                    relationship_id,
                    candidate["extractor_version"],
                ),
            )
        return relationship_id

    def list_memory_entity_neighborhood(
        self: SQLiteStore, entity_id: str, scope: str | None = None, *, owner_principal_id: str | None = None
    ) -> list[dict[str, Any]]:
        now = utc_now()
        query = """SELECT r.*, s.display_name AS subject_name, o.display_name AS object_name
        FROM memory_entity_relationships r JOIN memory_entities s ON s.entity_id = r.subject_entity_id
        JOIN memory_entities o ON o.entity_id = r.object_entity_id
        JOIN approved_memory m ON m.memory_id = r.evidence_memory_id
        WHERE r.active = 1 AND (r.subject_entity_id = ? OR r.object_entity_id = ?)
          AND m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
          AND m.sensitivity NOT IN ('secret_like', 'credential_like')
          AND (m.expires_at IS NULL OR m.expires_at > ?)
          AND (m.valid_from IS NULL OR m.valid_from <= ?)
          AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL"""
        params: list[Any] = [entity_id, entity_id, now, now, now]
        if owner_principal_id:
            query += " AND m.owner_principal_id = ?"
            params.append(owner_principal_id)
        if scope:
            query += " AND m.scope = ?"
            params.append(scope)
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def mark_approved_memory_forgotten(
        self: SQLiteStore,
        memory_id: str,
        *,
        deleted_at: str,
        updated_at: str,
        owner_principal_id: str | None = None,
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approved_memory
                SET approval_state = ?, deleted_at = ?, updated_at = ?
                WHERE memory_id = ? AND deleted_at IS NULL"""
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (
                    "forgotten",
                    deleted_at,
                    updated_at,
                    memory_id,
                    *([owner_principal_id] if owner_principal_id else []),
                ),
            )
            self._sync_memory_fts(connection, memory_id)
            self._sync_memory_projection_eligibility(connection, memory_id)
        return cursor.rowcount > 0

    def set_approved_memory_archived(
        self: SQLiteStore,
        memory_id: str,
        *,
        archived_at: str | None,
        updated_at: str | None,
        owner_principal_id: str | None = None,
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE approved_memory SET archived_at = ?, updated_at = ? WHERE memory_id = ? AND deleted_at IS NULL"
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (
                    archived_at,
                    updated_at,
                    memory_id,
                    *([owner_principal_id] if owner_principal_id else []),
                ),
            )
            self._sync_memory_fts(connection, memory_id)
            self._sync_memory_projection_eligibility(connection, memory_id)
        return cursor.rowcount > 0

    def create_memory_purge_record(
        self: SQLiteStore,
        purge_id: str,
        memory_id: str,
        requested_by: str,
        confirmed_at: str,
        disposition: dict[str, Any],
    ) -> None:
        self._execute(
            "INSERT INTO memory_purge_records (purge_id, memory_id, requested_by, confirmed_at, disposition_json) VALUES (?, ?, ?, ?, ?)",
            (
                purge_id,
                memory_id,
                requested_by,
                confirmed_at,
                json.dumps(disposition, sort_keys=True),
            ),
        )

    def deactivate_memory_projections(self: SQLiteStore, memory_id: str) -> None:
        self._execute("UPDATE memory_projections SET active = 0 WHERE memory_id = ?", (memory_id,))

    def set_memory_projections_active(self: SQLiteStore, memory_id: str, active: bool) -> None:
        with self.connect() as connection:
            self._sync_memory_projection_eligibility(connection, memory_id, enabled=active)

    @staticmethod
    def _sync_memory_projection_eligibility(
        connection: sqlite3.Connection, memory_id: str, *, enabled: bool = True
    ) -> None:
        now = utc_now()
        connection.execute(
            """UPDATE memory_projections SET active = CASE WHEN ? = 1 AND EXISTS (
                SELECT 1 FROM approved_memory m WHERE m.memory_id = memory_projections.memory_id
                AND m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
                AND (m.expires_at IS NULL OR m.expires_at > ?)
                AND (m.valid_from IS NULL OR m.valid_from <= ?)
                AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL
            ) THEN 1 ELSE 0 END WHERE memory_id = ?""",
            (int(enabled), now, now, now, memory_id),
        )

    def link_memory_projection(
        self: SQLiteStore,
        memory_id: str,
        projection_type: str,
        projection_id: str,
        source_version: str,
        *,
        owner_principal_id: str | None = None,
    ) -> None:
        if projection_type not in {"fts", "vector", "graph"}:
            raise ValueError("invalid_memory_projection_type")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM approved_memory WHERE memory_id = ?"
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (memory_id, *([owner_principal_id] if owner_principal_id else [])),
            ).fetchone()
            if row is None:
                raise ValueError("unknown_memory")
            connection.execute(
                "INSERT OR REPLACE INTO memory_projections (memory_id, projection_type, projection_id, source_version, active) VALUES (?, ?, ?, ?, ?)",
                (memory_id, projection_type, projection_id, source_version, 0),
            )
            self._sync_memory_projection_eligibility(connection, memory_id)

    def list_memory_projections(self: SQLiteStore, memory_id: str) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM memory_projections WHERE memory_id = ? ORDER BY projection_type, projection_id",
            (memory_id,),
        )
        return [dict(row) for row in rows]

    def get_active_approved_memory(
        self: SQLiteStore, memory_id: str, *, owner_principal_id: str | None = None
    ) -> dict[str, Any] | None:
        now = utc_now()
        row = self._row(
            """SELECT * FROM approved_memory WHERE memory_id = ? AND deleted_at IS NULL
            AND archived_at IS NULL AND search_enabled = 1
            AND sensitivity NOT IN ('secret_like', 'credential_like')
            AND (expires_at IS NULL OR expires_at > ?)
            AND (valid_from IS NULL OR valid_from <= ?)
            AND (valid_until IS NULL OR valid_until > ?) AND superseded_at IS NULL"""
            + (" AND owner_principal_id = ?" if owner_principal_id else ""),
            (memory_id, now, now, now, *([owner_principal_id] if owner_principal_id else [])),
        )
        return dict(row) if row else None

    def reconcile_memory_projections(
        self: SQLiteStore, *, owner_principal_id: str | None = None
    ) -> dict[str, int]:
        with self.connect() as connection:
            now = utc_now()
            cursor = connection.execute(
                """UPDATE memory_projections SET active = CASE WHEN EXISTS (
                    SELECT 1 FROM approved_memory m WHERE m.memory_id = memory_projections.memory_id
                    AND m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
                    AND m.sensitivity NOT IN ('secret_like', 'credential_like')
                    AND (m.expires_at IS NULL OR m.expires_at > ?)
                    AND (m.valid_from IS NULL OR m.valid_from <= ?)
                    AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL
                ) THEN 1 ELSE 0 END"""
                + (
                    " WHERE memory_id IN (SELECT memory_id FROM approved_memory WHERE owner_principal_id = ?)"
                    if owner_principal_id
                    else ""
                ),
                (now, now, now, *([owner_principal_id] if owner_principal_id else [])),
            )
            if owner_principal_id is None:
                self._rebuild_memory_fts(connection)
        return {"projection_rows_reconciled": cursor.rowcount}

    @staticmethod
    def _sync_memory_fts(connection: sqlite3.Connection, memory_id: str) -> None:
        connection.execute("DELETE FROM approved_memory_fts WHERE memory_id = ?", (memory_id,))
        connection.execute(
            """INSERT INTO approved_memory_fts(memory_id, text, tags)
            SELECT memory_id, text, tags_json FROM approved_memory
            WHERE memory_id = ? AND deleted_at IS NULL AND archived_at IS NULL
              AND search_enabled = 1 AND (expires_at IS NULL OR expires_at > ?)
              AND (valid_from IS NULL OR valid_from <= ?) AND (valid_until IS NULL OR valid_until > ?)
              AND superseded_at IS NULL""",
            (memory_id, utc_now(), utc_now(), utc_now()),
        )

    @staticmethod
    def _backfill_memory_fts(connection: sqlite3.Connection) -> None:
        """Populate an empty memory index without rewriting it on every open.

        Normal memory mutations keep the FTS projection synchronized. Bootstrap
        only needs to cover a pre-index workspace; avoiding an unconditional
        DELETE/INSERT also keeps read-model construction from competing with an
        in-flight command receipt for SQLite's single writer slot.
        """
        from raiker.storage.sqlite import SQLiteStore  # defined after its parts

        try:
            if connection.execute("SELECT 1 FROM approved_memory_fts LIMIT 1").fetchone():
                return
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                raise
            SQLiteStore._rebuild_memory_fts(connection)
            return
        source = connection.execute(
            """SELECT 1 FROM approved_memory
               WHERE deleted_at IS NULL AND archived_at IS NULL
                 AND search_enabled = 1 AND (expires_at IS NULL OR expires_at > ?)
                 AND (valid_from IS NULL OR valid_from <= ?)
                 AND (valid_until IS NULL OR valid_until > ?)
                 AND superseded_at IS NULL LIMIT 1""",
            (utc_now(), utc_now(), utc_now()),
        ).fetchone()
        if source is not None:
            SQLiteStore._rebuild_memory_fts(connection)

    @staticmethod
    def _rebuild_memory_fts(connection: sqlite3.Connection) -> None:
        from raiker.storage.sqlite import SQLiteStore  # defined after its parts

        try:
            connection.execute("DELETE FROM approved_memory_fts")
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                raise
            # Repair an index whose shadow tables did not survive an import —
            # historically an FTS5 dump read by an FTS4-only migration, and now
            # the reverse as well. The FTS table is a rebuildable projection,
            # never source, so re-creating it on the engine this build actually
            # has is always the right answer.
            connection.execute("DROP TABLE IF EXISTS approved_memory_fts")
            connection.execute(
                "CREATE VIRTUAL TABLE approved_memory_fts USING "
                f"{SQLiteStore.text_search_engine(connection)}("
                "memory_id UNINDEXED, text, tags)"
            )
        connection.execute(
            """INSERT INTO approved_memory_fts(memory_id, text, tags)
            SELECT memory_id, text, tags_json FROM approved_memory
            WHERE deleted_at IS NULL AND archived_at IS NULL AND search_enabled = 1
              AND (expires_at IS NULL OR expires_at > ?)
              AND (valid_from IS NULL OR valid_from <= ?) AND (valid_until IS NULL OR valid_until > ?)
              AND superseded_at IS NULL""",
            (utc_now(), utc_now(), utc_now()),
        )

    def search_approved_memory(
        self: SQLiteStore,
        query: str,
        scope: str | None = None,
        limit: int = 20,
        *,
        owner_principal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        terms = self._match_terms(query)
        if not terms:
            return []
        # MEM-05 — relevance first, recency only to break ties.
        #
        # Ordering by recency and truncating drops an old exact answer behind
        # newer partial matches before it is ranked. `bm25()` returns a
        # *negative* score that is more negative the better the match, so
        # ascending order is best-first.
        #
        # **The index is evaluated exactly once.** With `approved_memory` as the
        # outer loop, the full-text match re-runs once per candidate row (16 ms
        # alone, 13 s that way at 800 memories); a correlated scalar subquery
        # for the rank re-scans it per row too (5.2 s). Selecting the rank
        # alongside `memory_id` in a single subquery and joining on it keeps one
        # `SCAN approved_memory_fts` in the plan and a primary-key probe per hit:
        # 23 ms, and the ranking is free.
        #
        # Written as a derived table rather than a `WITH … AS MATERIALIZED` CTE
        # on purpose: both plan identically here, and the hint needs SQLite 3.35
        # while FTS5 itself only needs 3.9 — so the CTE would narrow the set of
        # builds this path works on for no measured gain.
        ranked = self.resolved_text_search_engine() == TEXT_SEARCH_FTS5
        if ranked:
            # `bm25()` resolves its first argument as the FTS table's own name,
            # never a query alias, so the inner select does not alias the table.
            # One weight per declared column: `memory_id` is UNINDEXED and can
            # never match, `text` carries the answer, and `tags` are a weaker
            # signal than the sentence the owner actually approved.
            source = """approved_memory m
        JOIN (SELECT memory_id, bm25(approved_memory_fts, 0.0, 1.0, 0.4) AS relevance
              FROM approved_memory_fts WHERE approved_memory_fts MATCH ?) AS ranked
          ON ranked.memory_id = m.memory_id"""
            selected = "m.*, ranked.relevance AS relevance"
            ordering = "ranked.relevance ASC, m.created_at DESC"
        else:
            # No relevance score to order by, so recency is the only
            # deterministic order available — MEM-05's original situation, kept
            # working for a build that really has no FTS5.
            source = """approved_memory m
        JOIN (SELECT memory_id FROM approved_memory_fts
              WHERE approved_memory_fts MATCH ?) AS ranked
          ON ranked.memory_id = m.memory_id"""
            selected = "m.*, 0.0 AS relevance"
            ordering = "m.created_at DESC"
        sql = f"""SELECT {selected} FROM {source}
        WHERE m.deleted_at IS NULL AND m.archived_at IS NULL
          AND m.search_enabled = 1 AND m.sensitivity NOT IN ('secret_like', 'credential_like')
          AND (m.expires_at IS NULL OR m.expires_at > ?)
          AND (m.valid_from IS NULL OR m.valid_from <= ?) AND (m.valid_until IS NULL OR m.valid_until > ?)
          AND m.superseded_at IS NULL"""
        now = utc_now()
        params: list[Any] = [self._match_expression(terms), now, now, now]
        if scope is not None:
            sql += " AND m.scope = ?"
            params.append(scope)
        if owner_principal_id:
            sql += " AND m.owner_principal_id = ?"
            params.append(owner_principal_id)
        sql += f" ORDER BY {ordering} LIMIT ?"
        params.append(limit)
        rows = self._rows(sql, params)
        return [dict(row) for row in rows]

    def delete_approved_memory(
        self: SQLiteStore, memory_id: str, *, owner_principal_id: str | None = None
    ) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM approved_memory_fts WHERE memory_id = ?", (memory_id,))
            connection.execute(
                "DELETE FROM approved_memory WHERE memory_id = ?"
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (memory_id, *([owner_principal_id] if owner_principal_id else [])),
            )

    def list_approved_memory(
        self: SQLiteStore,
        scope: str | None = None,
        limit: int = 50,
        *,
        include_search_disabled: bool = False,
        owner_principal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        now = utc_now()
        query = """SELECT * FROM approved_memory WHERE deleted_at IS NULL AND archived_at IS NULL
        AND (expires_at IS NULL OR expires_at > ?)
        AND (valid_from IS NULL OR valid_from <= ?) AND (valid_until IS NULL OR valid_until > ?)
        AND superseded_at IS NULL"""
        params: list[Any] = [now, now, now]
        if not include_search_disabled:
            query += " AND search_enabled = 1"
        if scope is not None:
            query += " AND scope = ?"
            params.append(scope)
        if owner_principal_id:
            query += " AND owner_principal_id = ?"
            params.append(owner_principal_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def enqueue_memory_job(self: SQLiteStore, job_type: str, dedup_key: str, max_attempts: int = 3) -> str:
        from raiker.contracts.ids import new_id

        if job_type not in {"reconcile", "integrity_scan"} or not dedup_key or max_attempts < 1:
            raise ValueError("invalid_memory_job")
        now = utc_now()
        job_id = new_id("mjob_")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO memory_jobs VALUES (?, ?, ?, 'queued', 0, ?, NULL, NULL, ?, ?)
                ON CONFLICT(job_type, dedup_key) DO NOTHING""",
                (job_id, job_type, dedup_key, max_attempts, now, now),
            )
            row = connection.execute(
                "SELECT job_id FROM memory_jobs WHERE job_type = ? AND dedup_key = ?",
                (job_type, dedup_key),
            ).fetchone()
        return str(row["job_id"])

    def claim_memory_job(self: SQLiteStore, lease_until: str) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM memory_jobs WHERE status IN ('queued', 'retry')
                OR (status = 'running' AND lease_until < ?) ORDER BY created_at LIMIT 1""",
                (now,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE memory_jobs SET status = 'running', attempts = attempts + 1, lease_until = ?, updated_at = ? WHERE job_id = ?",
                (lease_until, now, row["job_id"]),
            )
            claimed = connection.execute(
                "SELECT * FROM memory_jobs WHERE job_id = ?", (row["job_id"],)
            ).fetchone()
        return dict(claimed) if claimed else None

    def finish_memory_job(self: SQLiteStore, job_id: str, error: str | None = None) -> bool:
        now = utc_now()
        with self.connect() as connection:
            if error is None:
                cursor = connection.execute(
                    "UPDATE memory_jobs SET status = 'completed', lease_until = NULL, updated_at = ? WHERE job_id = ? AND status = 'running'",
                    (now, job_id),
                )
            else:
                cursor = connection.execute(
                    """UPDATE memory_jobs SET status = CASE WHEN attempts >= max_attempts THEN 'dead_letter' ELSE 'retry' END,
                    lease_until = NULL, last_error = ?, updated_at = ? WHERE job_id = ? AND status = 'running'""",
                    (error[:500], now, job_id),
                )
        return cursor.rowcount > 0

    def consume_memory_job_rate_limit(self: SQLiteStore, job_type: str, *, limit_per_minute: int) -> bool:
        if limit_per_minute < 1:
            raise ValueError("invalid_memory_job_rate_limit")
        window = utc_now()[:16] + ":00Z"
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT count FROM memory_job_rate_windows WHERE job_type = ? AND window_started_at = ?",
                (job_type, window),
            ).fetchone()
            count = int(row["count"]) if row else 0
            if count >= limit_per_minute:
                return False
            connection.execute(
                """INSERT INTO memory_job_rate_windows VALUES (?, ?, 1)
                ON CONFLICT(job_type, window_started_at) DO UPDATE SET count = count + 1""",
                (job_type, window),
            )
        return True

    def memory_job_metrics(self: SQLiteStore) -> dict[str, int | float]:
        """Return aggregate, non-sensitive queue and worker health metrics."""
        with self.connect() as connection:
            counts = {
                str(row["status"]): int(row["count"])
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM memory_jobs GROUP BY status"
                ).fetchall()
            }
            completed = connection.execute(
                """SELECT AVG((julianday(updated_at) - julianday(created_at)) * 86400000.0) AS latency_ms
                FROM memory_jobs WHERE status = 'completed'"""
            ).fetchone()
        return {
            "queue_depth": counts.get("queued", 0) + counts.get("retry", 0),
            "running_count": counts.get("running", 0),
            "completed_count": counts.get("completed", 0),
            "dead_letter_count": counts.get("dead_letter", 0),
            "average_completion_latency_ms": float(completed["latency_ms"] or 0.0),
        }

    def record_memory_lifecycle_event(
        self: SQLiteStore, memory_id: str, action: str, actor_id: str, details: dict[str, Any] | None = None
    ) -> str:
        from raiker.contracts.ids import new_id

        if action not in {
            "archive",
            "restore",
            "forget",
            "purge",
            "correct",
            "export",
            "import",
            "recall",
            "approve",
            "reject",
            "edit",
            "pin",
            "unpin",
            "scope_change",
            "expiry_change",
            "legal_hold",
            "backup_access",
            "admin_access",
        }:
            raise ValueError("invalid_memory_lifecycle_action")
        audit_id = new_id("mla_")
        self._execute(
            "INSERT INTO memory_lifecycle_audit VALUES (?, ?, ?, ?, ?, ?)",
            (
                audit_id,
                memory_id,
                action,
                actor_id,
                json.dumps(details or {}, sort_keys=True),
                utc_now(),
            ),
        )
        return audit_id

    def list_memory_lifecycle_events(
        self: SQLiteStore, memory_id: str, *, owner_principal_id: str
    ) -> list[dict[str, Any]]:
        """Return immutable history only while the caller still owns the record."""
        with self.connect() as connection:
            owned = connection.execute(
                "SELECT 1 FROM approved_memory WHERE memory_id = ? AND owner_principal_id = ?",
                (memory_id, owner_principal_id),
            ).fetchone()
            if owned is None:
                return []
            rows = connection.execute(
                """SELECT audit_id, memory_id, action, actor_id, details_json, created_at
                FROM memory_lifecycle_audit WHERE memory_id = ? ORDER BY created_at DESC, audit_id DESC""",
                (memory_id,),
            ).fetchall()
        return [{**dict(row), "details": json.loads(row["details_json"] or "{}")} for row in rows]


    def insert_semantic_memory_write(self: SQLiteStore, record: SemanticMemoryWriteRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO semantic_memory_write_records
            (write_id, content_summary, embedding_model, vector_count, status, approved_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.write_id,
                record.content_summary,
                record.embedding_model,
                record.vector_count,
                record.status,
                record.approved_by,
                record.created_at,
            ),
        )

    def list_semantic_memory_writes(self: SQLiteStore, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM semantic_memory_write_records ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in rows]


    def insert_vector_record(self: SQLiteStore, record: VectorRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO vector_records
            (vector_id, content_hash, content_preview, embedding_model, dimensions, scope, sensitivity, embedding, created_at, owner_principal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.vector_id,
                record.content_hash,
                record.content_preview,
                record.embedding_model,
                record.dimensions,
                record.scope,
                record.sensitivity,
                record.embedding,
                record.created_at,
                record.owner_principal_id,
            ),
        )

    def delete_vector_record(
        self: SQLiteStore, vector_id: str, *, owner_principal_id: str | None = None
    ) -> bool:
        changed = self._execute(
            "DELETE FROM vector_records WHERE vector_id = ?"
            + (" AND owner_principal_id = ?" if owner_principal_id else ""),
            (vector_id, *([owner_principal_id] if owner_principal_id else [])),
        )
        return bool(changed)

    def list_vector_records(
        self: SQLiteStore, scope: str | None = None, limit: int = 50, *, owner_principal_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM vector_records"
        params: list[Any] = []
        conditions: list[str] = []
        if scope:
            conditions.append("scope = ?")
            params.append(scope)
        if owner_principal_id:
            conditions.append("owner_principal_id = ?")
            params.append(owner_principal_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def get_vector_record(
        self: SQLiteStore, vector_id: str, *, owner_principal_id: str | None = None
    ) -> dict[str, Any] | None:
        """Return one vector record by id (or ``None``). Includes the stored preview."""
        row = self._row(
            "SELECT * FROM vector_records WHERE vector_id = ?"
            + (" AND owner_principal_id = ?" if owner_principal_id else ""),
            (vector_id, *([owner_principal_id] if owner_principal_id else [])),
        )
        return dict(row) if row is not None else None

    def list_vector_embeddings(
        self: SQLiteStore,
        embedding_model: str,
        scope: str | None = None,
        *,
        owner_principal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return ``(vector_id, embedding)`` rows for one embedding model.

        Cosine similarity is only meaningful within a single embedding space, so
        retrieval fetches vectors for exactly one ``embedding_model`` (optionally
        narrowed to a ``scope``). Rows with no stored embedding are excluded. No
        row limit — the caller ranks the full corpus for that model.
        """
        query = (
            "SELECT vector_id, embedding FROM vector_records "
            "WHERE embedding_model = ? AND embedding IS NOT NULL"
        )
        params: list[Any] = [embedding_model]
        if scope:
            query += " AND scope = ?"
            params.append(scope)
        if owner_principal_id:
            query += " AND owner_principal_id = ?"
            params.append(owner_principal_id)
        query += " ORDER BY created_at"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def list_active_memory_vector_embeddings(
        self: SQLiteStore,
        embedding_model: str,
        scope: str | None = None,
        *,
        owner_principal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        now = utc_now()
        query = """SELECT v.vector_id, v.embedding, p.memory_id FROM vector_records v
        JOIN memory_projections p ON p.projection_id = v.vector_id
          AND p.projection_type = 'vector' AND p.active = 1
        JOIN approved_memory m ON m.memory_id = p.memory_id
        WHERE v.embedding_model = ? AND v.embedding IS NOT NULL
          AND m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
          AND m.sensitivity NOT IN ('secret_like', 'credential_like')
          AND (m.expires_at IS NULL OR m.expires_at > ?)
          AND (m.valid_from IS NULL OR m.valid_from <= ?)
          AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL"""
        params: list[Any] = [embedding_model, now, now, now]
        if scope:
            query += " AND m.scope = ?"
            params.append(scope)
        if owner_principal_id:
            query += " AND m.owner_principal_id = ? AND v.owner_principal_id = ?"
            params.extend((owner_principal_id, owner_principal_id))
        query += " ORDER BY v.created_at"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def active_memory_vector_revision(self: SQLiteStore) -> int:
        """A durable invalidation generation for the eligible memory-vector corpus.

        It is intentionally global rather than an optimisation that attempts to
        infer an owner/scope from a write. Rebuilding an extra cache after an
        unrelated owner update is cheap; reusing one after an archive or scope
        change could disclose memory that the retrieval SQL would now withhold.
        """
        row = self._row("SELECT revision FROM memory_vector_search_state WHERE singleton = 1")
        return int(row["revision"]) if row is not None else 0
