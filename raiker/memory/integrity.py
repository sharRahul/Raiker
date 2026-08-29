"""Owner-started, read-only integrity checks for the hybrid memory store."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from raiker.contracts.ids import utc_now
from raiker.storage.internal_paths import internal_io_path
from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class MemoryIntegrityReport:
    active_memory_count: int
    fts_count: int
    stale_fts_count: int
    missing_markdown_count: int
    stale_projection_count: int
    stale_graph_edge_count: int
    checksum_mismatch_count: int
    orphaned_markdown_count: int
    failed_purge_location_count: int
    project_path_inconsistency_count: int
    #: RAIKER-2025 — the engine each text index is actually built on, and the
    #: engine this build supports. They differ exactly when a workspace has been
    #: carried to a host whose SQLite is older, which is a real condition an
    #: owner can act on (upgrade, or accept recency ordering) and which nothing
    #: else would surface: an FTS4 index on an FTS5 host answers every query.
    text_search_engine: str = "fts5"
    index_engine_mismatch_count: int = 0
    #: MEM-09 — the conversation index is a projection of ``turns`` in exactly
    #: the way the memory index is a projection of ``approved_memory``, and it
    #: was the one projection this report did not know about. A divergence has
    #: no symptom an owner can see: search simply stops finding conversations it
    #: found last week. ``rebuild_conversation_fts()`` is the stated repair.
    conversation_index_count: int = 0
    stale_conversation_index_count: int = 0

    @property
    def clean(self) -> bool:
        return not any((
            self.index_engine_mismatch_count,
            self.stale_fts_count,
            self.stale_conversation_index_count,
            self.missing_markdown_count,
            self.stale_projection_count,
            self.stale_graph_edge_count,
            self.checksum_mismatch_count,
            self.orphaned_markdown_count,
            self.failed_purge_location_count,
            self.project_path_inconsistency_count,
        ))


def inspect_memory_integrity(*, store: SQLiteStore, workspace_root: str | Path) -> MemoryIntegrityReport:
    now = utc_now()
    with store.connect() as connection:
        active_memory_count = int(connection.execute(
            """SELECT COUNT(*) FROM approved_memory WHERE deleted_at IS NULL AND archived_at IS NULL
            AND search_enabled = 1 AND (expires_at IS NULL OR expires_at > ?)
            AND (valid_from IS NULL OR valid_from <= ?)
            AND (valid_until IS NULL OR valid_until > ?) AND superseded_at IS NULL""", (now, now, now)
        ).fetchone()[0])
        fts_count = int(connection.execute("SELECT COUNT(*) FROM approved_memory_fts").fetchone()[0])
        # MEM-09 — the same comparison, for the index behind Search chats. The
        # expected count is what `_rebuild_conversation_fts` would insert: one
        # row per non-empty prompt and one per non-empty answer.
        conversation_index_count = int(
            connection.execute("SELECT COUNT(*) FROM conversation_fts").fetchone()[0]
        )
        indexable_turn_rows = int(connection.execute(
            """SELECT
                 (SELECT COUNT(*) FROM turns WHERE prompt_text IS NOT NULL AND TRIM(prompt_text) != '')
               + (SELECT COUNT(*) FROM turns WHERE summary IS NOT NULL AND TRIM(summary) != '')"""
        ).fetchone()[0])
        engine = SQLiteStore.text_search_engine(connection)
        index_engine_mismatch_count = sum(
            SQLiteStore._index_engine(connection, table) not in (None, engine)  # noqa: SLF001
            for table in ("approved_memory_fts", "conversation_fts")
        )
        stale_projection_count = int(connection.execute(
            """SELECT COUNT(*) FROM memory_projections p WHERE p.active = 1 AND NOT EXISTS (
            SELECT 1 FROM approved_memory m WHERE m.memory_id = p.memory_id AND m.deleted_at IS NULL
            AND m.archived_at IS NULL AND m.search_enabled = 1 AND (m.expires_at IS NULL OR m.expires_at > ?)
            AND (m.valid_from IS NULL OR m.valid_from <= ?)
            AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL)""", (now, now, now)
        ).fetchone()[0])
        stale_graph_edge_count = int(connection.execute(
            """SELECT COUNT(*) FROM memory_entity_relationships r WHERE r.active = 1 AND NOT EXISTS (
            SELECT 1 FROM approved_memory m WHERE m.memory_id = r.evidence_memory_id AND m.deleted_at IS NULL
            AND m.archived_at IS NULL AND m.search_enabled = 1 AND (m.expires_at IS NULL OR m.expires_at > ?)
            AND (m.valid_from IS NULL OR m.valid_from <= ?)
            AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL)""", (now, now, now)
        ).fetchone()[0])
        rows = connection.execute(
            "SELECT memory_id, text, content_checksum FROM approved_memory"
        ).fetchall()
        purge_rows = connection.execute("SELECT disposition_json FROM memory_purge_records").fetchall()
        project_rows = connection.execute("SELECT project_id, parent_id, path FROM projects").fetchall()
    memory_dir = internal_io_path(Path(workspace_root).resolve() / ".raiker" / "memory")
    missing_markdown_count = sum(not (memory_dir / f"{row['memory_id']}.md").exists() for row in rows)
    known_memory_ids = {str(row["memory_id"]) for row in rows}
    orphaned_markdown_count = sum(
        path.stem not in known_memory_ids for path in memory_dir.glob("*.md")
    ) if memory_dir.exists() else 0
    checksum_mismatch_count = sum(
        str(row["content_checksum"] or "") != hashlib.sha256(str(row["text"]).encode()).hexdigest()
        for row in rows
    )
    failed_purge_location_count = sum(
        len(json.loads(str(row["disposition_json"])).get("failed_storage_locations", []))
        for row in purge_rows
    )
    projects = {
        str(row["project_id"]): (str(row["parent_id"]) if row["parent_id"] is not None else None, str(row["path"]))
        for row in project_rows
    }
    expected_paths: dict[str, str] = {}

    def expected_path(project_id: str, visiting: set[str]) -> str | None:
        if project_id in expected_paths:
            return expected_paths[project_id]
        if project_id in visiting or project_id not in projects:
            return None
        parent_id, _ = projects[project_id]
        parent_path = "/" if parent_id is None else expected_path(parent_id, visiting | {project_id})
        if parent_path is None:
            return None
        expected_paths[project_id] = f"{parent_path}{project_id}/"
        return expected_paths[project_id]

    project_path_inconsistency_count = sum(
        expected_path(project_id, set()) != path for project_id, (_, path) in projects.items()
    )
    return MemoryIntegrityReport(
        active_memory_count,
        fts_count,
        abs(active_memory_count - fts_count),
        missing_markdown_count,
        stale_projection_count,
        stale_graph_edge_count,
        checksum_mismatch_count,
        orphaned_markdown_count,
        failed_purge_location_count,
        project_path_inconsistency_count,
        text_search_engine=engine,
        index_engine_mismatch_count=index_engine_mismatch_count,
        conversation_index_count=conversation_index_count,
        stale_conversation_index_count=abs(indexable_turn_rows - conversation_index_count),
    )
