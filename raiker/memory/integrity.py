"""Owner-started, read-only integrity checks for the hybrid memory store."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class MemoryIntegrityReport:
    active_memory_count: int
    fts_count: int
    stale_fts_count: int
    missing_markdown_count: int
    stale_projection_count: int
    stale_graph_edge_count: int

    @property
    def clean(self) -> bool:
        return not any((self.stale_fts_count, self.missing_markdown_count, self.stale_projection_count, self.stale_graph_edge_count))


def inspect_memory_integrity(*, store: SQLiteStore, workspace_root: str | Path) -> MemoryIntegrityReport:
    now = utc_now()
    with store.connect() as connection:
        active_memory_count = int(connection.execute(
            """SELECT COUNT(*) FROM approved_memory WHERE deleted_at IS NULL AND archived_at IS NULL
            AND search_enabled = 1 AND (expires_at IS NULL OR expires_at > ?)
            AND (valid_until IS NULL OR valid_until > ?) AND superseded_at IS NULL""", (now, now)
        ).fetchone()[0])
        fts_count = int(connection.execute("SELECT COUNT(*) FROM approved_memory_fts").fetchone()[0])
        stale_projection_count = int(connection.execute(
            """SELECT COUNT(*) FROM memory_projections p WHERE p.active = 1 AND NOT EXISTS (
            SELECT 1 FROM approved_memory m WHERE m.memory_id = p.memory_id AND m.deleted_at IS NULL
            AND m.archived_at IS NULL AND m.search_enabled = 1 AND (m.expires_at IS NULL OR m.expires_at > ?)
            AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL)""", (now, now)
        ).fetchone()[0])
        stale_graph_edge_count = int(connection.execute(
            """SELECT COUNT(*) FROM memory_entity_relationships r WHERE r.active = 1 AND NOT EXISTS (
            SELECT 1 FROM approved_memory m WHERE m.memory_id = r.evidence_memory_id AND m.deleted_at IS NULL
            AND m.archived_at IS NULL AND m.search_enabled = 1 AND (m.expires_at IS NULL OR m.expires_at > ?)
            AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL)""", (now, now)
        ).fetchone()[0])
        rows = connection.execute("SELECT memory_id FROM approved_memory WHERE deleted_at IS NULL").fetchall()
    memory_dir = Path(workspace_root).resolve() / ".raiker" / "memory"
    missing_markdown_count = sum(not (memory_dir / f"{row['memory_id']}.md").exists() for row in rows)
    return MemoryIntegrityReport(active_memory_count, fts_count, abs(active_memory_count - fts_count), missing_markdown_count, stale_projection_count, stale_graph_edge_count)
