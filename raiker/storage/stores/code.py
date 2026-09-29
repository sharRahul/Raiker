# mypy: disable-error-code="misc"
"""Code workspace repositories, the repository code map and the symbol/dependency
graph records (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import utc_now
from raiker.contracts.models import DependencyEdge, GraphIndexRecord, ProjectGraph, SymbolNode

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class CodeStore:

    # Account-scoped references the Build workspace points a coding chat at: a
    # workspace-contained local folder, or a `owner/repo` GitHub coordinate read
    # through the governed `github_read` tool. A row is a reference only — it
    # holds no credential and grants no capability.

    def list_code_repos(self: SQLiteStore, owner_principal_id: str) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM code_repos WHERE owner_principal_id = ? ORDER BY created_at, repo_id",
            (owner_principal_id,),
        )
        return [dict(row) for row in rows]

    def load_code_repo(self: SQLiteStore, owner_principal_id: str, repo_id: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM code_repos WHERE owner_principal_id = ? AND repo_id = ?",
            (owner_principal_id, repo_id),
        )
        return dict(row) if row is not None else None

    def insert_code_repo(
        self: SQLiteStore,
        *,
        repo_id: str,
        owner_principal_id: str,
        kind: str,
        label: str,
        local_subpath: str | None = None,
        github_owner: str | None = None,
        github_repo: str | None = None,
        branch: str | None = None,
    ) -> bool:
        """Store one repository reference, or return False if it already exists.

        The unique indexes make "already connected" a storage-layer fact, so the
        duplicate is reported as a value rather than surfacing a driver exception
        to the service layer.
        """
        return bool(
            self._execute(
                """INSERT OR IGNORE INTO code_repos
                   (repo_id, owner_principal_id, kind, label, local_subpath,
                    github_owner, github_repo, branch, selected, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    repo_id,
                    owner_principal_id,
                    kind,
                    label,
                    local_subpath,
                    github_owner,
                    github_repo,
                    branch,
                    utc_now(),
                ),
            )
        )

    def delete_code_repo(self: SQLiteStore, owner_principal_id: str, repo_id: str) -> bool:
        return bool(
            self._execute(
                "DELETE FROM code_repos WHERE owner_principal_id = ? AND repo_id = ?",
                (owner_principal_id, repo_id),
            )
        )

    def select_code_repo(self: SQLiteStore, owner_principal_id: str, repo_id: str | None) -> None:
        """Point the account's Build workspace at one repository, or none."""
        with self.connect() as connection:
            connection.execute(
                "UPDATE code_repos SET selected = 0 WHERE owner_principal_id = ?",
                (owner_principal_id,),
            )
            if repo_id is not None:
                connection.execute(
                    "UPDATE code_repos SET selected = 1 WHERE owner_principal_id = ? AND repo_id = ?",
                    (owner_principal_id, repo_id),
                )

    # A derived projection of files the agent may already read: what each file
    # is and what it declares, keyed by owner and by the workspace-relative
    # repository path the turn works in. It is storage for *coordinates* — the
    # rows say where to look, and looking still goes through `read_file`, the
    # workspace containment check, and the policy engine.

    def load_code_map_index(self: SQLiteStore, owner_principal_id: str, repo_path: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM code_map_indexes WHERE owner_principal_id = ? AND repo_path = ?",
            (owner_principal_id, repo_path),
        )
        return dict(row) if row is not None else None

    def list_code_map_indexes(self: SQLiteStore, owner_principal_id: str) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM code_map_indexes WHERE owner_principal_id = ? ORDER BY repo_path",
            (owner_principal_id,),
        )
        return [dict(row) for row in rows]

    def record_code_map_index(
        self: SQLiteStore,
        *,
        owner_principal_id: str,
        repo_path: str,
        repo_id: str,
        label: str,
        status: str,
        reason_code: str,
        file_count: int,
        symbol_count: int,
        edge_count: int,
        skipped: str,
        limits_hit: str,
        languages: str,
        schema_version: str,
    ) -> None:
        """Write the index's own state row, preserving the first ``built_at``."""
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT built_at FROM code_map_indexes WHERE owner_principal_id = ? AND repo_path = ?",
                (owner_principal_id, repo_path),
            ).fetchone()
            built_at = str(existing["built_at"]) if existing is not None else now
            connection.execute(
                """INSERT INTO code_map_indexes
                   (owner_principal_id, repo_path, repo_id, label, status, reason_code,
                    file_count, symbol_count, edge_count, skipped, limits_hit, languages,
                    schema_version, built_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(owner_principal_id, repo_path) DO UPDATE SET
                     repo_id=excluded.repo_id, label=excluded.label, status=excluded.status,
                     reason_code=excluded.reason_code, file_count=excluded.file_count,
                     symbol_count=excluded.symbol_count, edge_count=excluded.edge_count,
                     skipped=excluded.skipped, limits_hit=excluded.limits_hit,
                     languages=excluded.languages, schema_version=excluded.schema_version,
                     updated_at=excluded.updated_at""",
                (
                    owner_principal_id,
                    repo_path,
                    repo_id,
                    label,
                    status,
                    reason_code,
                    file_count,
                    symbol_count,
                    edge_count,
                    skipped,
                    limits_hit,
                    languages,
                    schema_version,
                    built_at,
                    now,
                ),
            )

    def replace_code_map(
        self: SQLiteStore,
        *,
        owner_principal_id: str,
        repo_path: str,
        files: list[tuple[Any, ...]],
        symbols: list[tuple[Any, ...]],
        edges: list[tuple[Any, ...]],
    ) -> None:
        """Swap a repository's whole map in one transaction.

        All-or-nothing on purpose: a half-written map would answer some searches
        from the new scan and some from the old one, and nothing in the result
        would say which.
        """
        with self.connect() as connection:
            self._delete_code_map_rows(connection, owner_principal_id, repo_path)
            self._insert_code_map_rows(
                connection, owner_principal_id, repo_path, files, symbols, edges
            )

    def refresh_code_map_paths(
        self: SQLiteStore,
        *,
        owner_principal_id: str,
        repo_path: str,
        paths: list[str],
        files: list[tuple[Any, ...]],
        symbols: list[tuple[Any, ...]],
        edges: list[tuple[Any, ...]],
    ) -> None:
        """Replace the rows for exactly *paths*, in one transaction.

        A path in *paths* with no row in *files* was deleted or became
        unreadable, so its rows go and nothing replaces them.
        """
        if not paths:
            return
        with self.connect() as connection:
            for path in paths:
                connection.execute(
                    "DELETE FROM code_map_files WHERE owner_principal_id = ? AND repo_path = ? AND path = ?",
                    (owner_principal_id, repo_path, path),
                )
                connection.execute(
                    "DELETE FROM code_map_symbols WHERE owner_principal_id = ? AND repo_path = ? AND path = ?",
                    (owner_principal_id, repo_path, path),
                )
                connection.execute(
                    "DELETE FROM code_map_edges WHERE owner_principal_id = ? AND repo_path = ? AND from_path = ?",
                    (owner_principal_id, repo_path, path),
                )
            self._insert_code_map_rows(
                connection, owner_principal_id, repo_path, files, symbols, edges
            )

    def delete_code_map(self: SQLiteStore, owner_principal_id: str, repo_path: str) -> None:
        with self.connect() as connection:
            self._delete_code_map_rows(connection, owner_principal_id, repo_path)
            connection.execute(
                "DELETE FROM code_map_indexes WHERE owner_principal_id = ? AND repo_path = ?",
                (owner_principal_id, repo_path),
            )

    @staticmethod
    def _delete_code_map_rows(
        connection: sqlite3.Connection, owner_principal_id: str, repo_path: str
    ) -> None:
        for table in ("code_map_files", "code_map_symbols", "code_map_edges"):
            connection.execute(
                f"DELETE FROM {table} WHERE owner_principal_id = ? AND repo_path = ?",  # noqa: S608 — fixed table names
                (owner_principal_id, repo_path),
            )

    @staticmethod
    def _insert_code_map_rows(
        connection: sqlite3.Connection,
        owner_principal_id: str,
        repo_path: str,
        files: list[tuple[Any, ...]],
        symbols: list[tuple[Any, ...]],
        edges: list[tuple[Any, ...]],
    ) -> None:
        now = utc_now()
        connection.executemany(
            """INSERT OR REPLACE INTO code_map_files
               (owner_principal_id, repo_path, path, language, sha256, size_bytes,
                line_count, symbol_count, title, extractor, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(owner_principal_id, repo_path, *row, now) for row in files],
        )
        connection.executemany(
            """INSERT INTO code_map_symbols
               (owner_principal_id, repo_path, path, kind, name, name_lower,
                qualified_name, line_start, line_end, parent, signature, doc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(owner_principal_id, repo_path, *row) for row in symbols],
        )
        connection.executemany(
            """INSERT INTO code_map_edges
               (owner_principal_id, repo_path, from_path, relationship, target, line)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(owner_principal_id, repo_path, *row) for row in edges],
        )

    def code_map_file_hashes(self: SQLiteStore, owner_principal_id: str, repo_path: str) -> dict[str, str]:
        """``path -> sha256`` for every indexed file, so a refresh can skip the unchanged."""
        rows = self._rows(
            "SELECT path, sha256 FROM code_map_files WHERE owner_principal_id = ? AND repo_path = ?",
            (owner_principal_id, repo_path),
        )
        return {str(row["path"]): str(row["sha256"]) for row in rows}

    def match_code_map_symbols(
        self: SQLiteStore, owner_principal_id: str, repo_path: str, term: str, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Candidate symbol rows for one search term. Ranking happens above this."""
        like = f"%{term.lower()}%"
        rows = self._rows(
            """SELECT * FROM code_map_symbols
               WHERE owner_principal_id = ? AND repo_path = ?
                 AND (name_lower LIKE ? OR LOWER(qualified_name) LIKE ? OR LOWER(doc) LIKE ?)
               ORDER BY LENGTH(name), path, line_start
               LIMIT ?""",
            (owner_principal_id, repo_path, like, like, like, limit),
        )
        return [dict(row) for row in rows]

    def find_code_map_symbols(
        self: SQLiteStore, owner_principal_id: str, repo_path: str, name: str, *, limit: int = 40
    ) -> list[dict[str, Any]]:
        """Declarations of **exactly** *name* — the definition question (B10).

        `match_code_map_symbols` is a substring search whose job is to rank a
        fuzzy query; asking it "where is `Config` defined" returns every
        `ConfigLoader` and `parse_config` too, which is right for a search box
        and wrong for a definition lookup. This matches the name a caller wrote,
        and lets the service above decide which of the real candidates is the
        one they meant.
        """
        rows = self._rows(
            """SELECT * FROM code_map_symbols
               WHERE owner_principal_id = ? AND repo_path = ?
                 AND (name = ? OR qualified_name = ?)
               ORDER BY path, line_start
               LIMIT ?""",
            (owner_principal_id, repo_path, name, name, limit),
        )
        return [dict(row) for row in rows]

    def match_code_map_files(
        self: SQLiteStore, owner_principal_id: str, repo_path: str, term: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        like = f"%{term.lower()}%"
        rows = self._rows(
            """SELECT * FROM code_map_files
               WHERE owner_principal_id = ? AND repo_path = ?
                 AND (LOWER(path) LIKE ? OR LOWER(title) LIKE ?)
               ORDER BY symbol_count DESC, path
               LIMIT ?""",
            (owner_principal_id, repo_path, like, like, limit),
        )
        return [dict(row) for row in rows]

    def list_code_map_files(
        self: SQLiteStore, owner_principal_id: str, repo_path: str, *, limit: int = 5000
    ) -> list[dict[str, Any]]:
        """Every indexed file of one map, largest first.

        The set a reference scan is allowed to read: exactly the files the owner's
        indexing run already accepted, so a scan can never reach outside what the
        map itself covers.
        """
        rows = self._rows(
            """SELECT path, language, line_count, size_bytes FROM code_map_files
               WHERE owner_principal_id = ? AND repo_path = ?
               ORDER BY symbol_count DESC, path LIMIT ?""",
            (owner_principal_id, repo_path, limit),
        )
        return [dict(row) for row in rows]

    def code_map_declarations(
        self: SQLiteStore, owner_principal_id: str, repo_path: str, name: str, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Exact-name declarations, so a reference scan can exclude them."""
        rows = self._rows(
            """SELECT path, name, kind, qualified_name, line_start, line_end, signature
               FROM code_map_symbols
               WHERE owner_principal_id = ? AND repo_path = ? AND name_lower = ?
               ORDER BY path, line_start LIMIT ?""",
            (owner_principal_id, repo_path, name.lower(), limit),
        )
        return [dict(row) for row in rows]

    def top_code_map_files(
        self: SQLiteStore, owner_principal_id: str, repo_path: str, *, limit: int = 12
    ) -> list[dict[str, Any]]:
        """The files with the most declarations — the overview when nothing matched."""
        rows = self._rows(
            """SELECT * FROM code_map_files
               WHERE owner_principal_id = ? AND repo_path = ?
               ORDER BY symbol_count DESC, path LIMIT ?""",
            (owner_principal_id, repo_path, limit),
        )
        return [dict(row) for row in rows]

    def code_map_totals(self: SQLiteStore, owner_principal_id: str, repo_path: str) -> dict[str, Any]:
        """File/symbol totals and a language histogram, aggregated in SQL.

        An incremental refresh has to re-derive the index's counts, and doing
        that by loading every file row would make a one-file write cost a scan of
        the whole table.
        """
        with self.connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS files, COALESCE(SUM(symbol_count), 0) AS symbols
                   FROM code_map_files WHERE owner_principal_id = ? AND repo_path = ?""",
                (owner_principal_id, repo_path),
            ).fetchone()
            languages = connection.execute(
                """SELECT language, COUNT(*) AS files FROM code_map_files
                   WHERE owner_principal_id = ? AND repo_path = ?
                   GROUP BY language""",
                (owner_principal_id, repo_path),
            ).fetchall()
        return {
            "file_count": int(row["files"]) if row else 0,
            "symbol_count": int(row["symbols"]) if row else 0,
            "languages": {str(item["language"]): int(item["files"]) for item in languages},
        }

    def code_map_file_symbols(
        self: SQLiteStore, owner_principal_id: str, repo_path: str, path: str, *, limit: int = 40
    ) -> list[dict[str, Any]]:
        rows = self._rows(
            """SELECT * FROM code_map_symbols
               WHERE owner_principal_id = ? AND repo_path = ? AND path = ?
               ORDER BY line_start LIMIT ?""",
            (owner_principal_id, repo_path, path, limit),
        )
        return [dict(row) for row in rows]

    def code_map_dependents(
        self: SQLiteStore, owner_principal_id: str, repo_path: str, target: str, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Files whose imports name *target* — the impact-analysis question."""
        like = f"%{target}%"
        rows = self._rows(
            """SELECT DISTINCT from_path, relationship, target FROM code_map_edges
               WHERE owner_principal_id = ? AND repo_path = ? AND target LIKE ?
               ORDER BY from_path LIMIT ?""",
            (owner_principal_id, repo_path, like, limit),
        )
        return [dict(row) for row in rows]


    def insert_graph_index_record(self: SQLiteStore, record: GraphIndexRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO graph_index_records
            (index_id, workspace_root, status, nodes_count, edges_count, started_at, completed_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.index_id,
                record.workspace_root,
                record.status,
                record.nodes_count,
                record.edges_count,
                record.started_at,
                record.completed_at,
                record.created_by,
            ),
        )

    def list_graph_index_records(self: SQLiteStore, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM graph_index_records ORDER BY COALESCE(started_at, index_id) DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in rows]


    def insert_symbol_node(self: SQLiteStore, node: SymbolNode) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO symbol_nodes
            (symbol_id, name, kind, file_path, line_number, module, parent_symbol_id, doc_preview)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node.symbol_id,
                node.name,
                node.kind,
                node.file_path,
                node.line_number,
                node.module,
                node.parent_symbol_id,
                node.doc_preview,
            ),
        )

    def list_symbol_nodes(self: SQLiteStore, kind: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = "SELECT * FROM symbol_nodes"
        params: list[Any] = []
        if kind:
            query += " WHERE kind = ?"
            params.append(kind)
        query += " ORDER BY file_path, line_number LIMIT ?"
        params.append(limit)
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def insert_dependency_edge(self: SQLiteStore, edge: DependencyEdge) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO dependency_edges
            (edge_id, source_symbol_id, target_symbol_id, dep_type, file_path, line_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edge.edge_id,
                edge.source_symbol_id,
                edge.target_symbol_id,
                edge.dep_type,
                edge.file_path,
                edge.line_number,
                edge.created_at,
            ),
        )


    def insert_project_graph(self: SQLiteStore, graph: ProjectGraph) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO project_graphs
            (graph_id, workspace_root, module_count, dependency_count, built_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                graph.graph_id,
                graph.workspace_root,
                graph.module_count,
                graph.dependency_count,
                graph.built_at,
            ),
        )

    def list_project_graphs(self: SQLiteStore, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._rows("SELECT * FROM project_graphs ORDER BY built_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in rows]
