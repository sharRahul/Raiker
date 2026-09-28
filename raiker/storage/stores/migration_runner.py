# mypy: disable-error-code="misc"
"""The schema migration runner: bootstrap, the migration catalogue it applies, and
the one-off data backfills that ride on it (GCR-11).

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
import re
from typing import TYPE_CHECKING

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import utc_now
from raiker.storage.migrations import (
    LEGACY_ACCOUNT_BOOTSTRAP_ROLES_MIGRATION_ID,
    MIGRATIONS,
    PHASE_1_MIGRATION_ID,
    PHASE_1_SQL,
    PROJECT_SELF_INCLUSIVE_PATH_MIGRATION_ID,
    Migration,
    SearchMigration,
)

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class MigrationRunner:

    def bootstrap(self: SQLiteStore) -> None:
        self.paths.ensure()
        self._migrate_plaintext_database()
        with self.connect() as connection:
            connection.executescript(PHASE_1_SQL)
            connection.executescript("""
CREATE TABLE IF NOT EXISTS model_session_state (
  session_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  model TEXT,
  reasoning_enabled INTEGER NOT NULL DEFAULT 0,
  reasoning_effort TEXT,
  reasoning_mode TEXT,
  reasoning_budget_tokens INTEGER,
  updated_at TEXT NOT NULL
);
""")
            connection.execute(
                "INSERT OR IGNORE INTO migrations (migration_id, applied_at) VALUES (?, ?)",
                (PHASE_1_MIGRATION_ID, utc_now()),
            )

            # Read once, before anything in this pass applies, which is what
            # makes it equivalent to asking per migration: an id absent here is
            # applied and then recorded, and `INSERT OR IGNORE` keeps that safe
            # either way.
            self._applied = {
                str(row["migration_id"])
                for row in connection.execute("SELECT migration_id FROM migrations")
            }
            for step in MIGRATIONS:
                if isinstance(step, Migration):
                    self._apply_migration(step.id, step.sql, connection)
                elif isinstance(step, SearchMigration):
                    self._apply_migration(
                        step.id, step.sql_for(self.text_search_engine(connection)), connection
                    )
                else:
                    getattr(self, step.method)(connection)
        # The pass is over; anything that asks again asks the table.
        self._applied = None

    def _add_early_columns(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Columns added before migrations were recorded by id: vector embeddings, the event hash chain and session ownership."""
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute("ALTER TABLE vector_records ADD COLUMN embedding TEXT")
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute("ALTER TABLE events_index ADD COLUMN prev_event_sha256 TEXT")
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute(
                "ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(user_id)"
            )

    def _add_reminder_delivery_columns(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Reminder delivery state, added in place before migrations were recorded by id."""
        for _col in (
            "ALTER TABLE reminders ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'active'",
            "ALTER TABLE reminders ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE reminders ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 3",
            "ALTER TABLE reminders ADD COLUMN delivered_at TEXT",
        ):
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute(_col)

    def _add_project_columns(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Session and project columns, and the index that keeps one folder in one project."""
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute(
                "ALTER TABLE sessions ADD COLUMN project_id TEXT REFERENCES projects(project_id)"
            )
        # Conversation organisation: a per-session pin/bookmark flag. It is
        # an organizing label only (like projects) — it grants nothing and
        # changes no gate, policy, or authority. Default 0 (unpinned).
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute(
                "ALTER TABLE sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"
            )
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute(
                "ALTER TABLE projects ADD COLUMN owner_user_id TEXT REFERENCES users(user_id)"
            )
        # A project's root is now one of two things. `root_kind` says which,
        # and `root_grant_id` names the owner's grant when the root is a
        # folder they already had. Defaulting to 'managed' makes this a
        # no-op for every project that exists today.
        for _root_column in (
            "ALTER TABLE projects ADD COLUMN root_kind TEXT NOT NULL DEFAULT 'managed'",
            "ALTER TABLE projects ADD COLUMN root_grant_id TEXT",
            # Bytes Raiker discovered rather than wrote need a cheap change
            # signal, or every reconcile re-hashes the whole tree.
            "ALTER TABLE managed_files ADD COLUMN source_mtime_ns INTEGER",
        ):
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute(_root_column)
        # Two projects over one folder would put a single file inside two
        # mutually exclusive "only this project" boundaries, so the database
        # refuses it rather than trusting every caller to check.
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_attached_root "
                "ON projects(root_grant_id) WHERE root_grant_id IS NOT NULL"
            )

    def _add_source_grant_write_column(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Whether a source grant allows writing, once the grants table exists."""
        # The grant stops implying read-only and starts saying what it
        # allows, so one record can serve the Knowledge Map's read-only
        # folders and a project's writable root. Applied here rather than in
        # the projects block above, because that runs before this table
        # exists.
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute(
                "ALTER TABLE brain_source_grants "
                "ADD COLUMN write_enabled INTEGER NOT NULL DEFAULT 0"
            )

    def _backfill_memory_content_checksums(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Checksum every approved memory that predates the checksum column."""
        rows = connection.execute(
            "SELECT memory_id, text FROM approved_memory WHERE content_checksum IS NULL"
        ).fetchall()
        connection.executemany(
            "UPDATE approved_memory SET content_checksum = ? WHERE memory_id = ?",
            (
                (hashlib.sha256(str(row["text"]).encode()).hexdigest(), row["memory_id"])
                for row in rows
            ),
        )

    def _add_session_and_task_columns(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """API-session and task columns added in place before migrations were recorded by id."""
        for _alter_sql in (
            "ALTER TABLE api_sessions ADD COLUMN scope TEXT NOT NULL DEFAULT 'control'",
            "ALTER TABLE api_sessions ADD COLUMN absolute_expires_at TEXT",
            "ALTER TABLE api_sessions ADD COLUMN last_seen_at TEXT",
            "ALTER TABLE api_sessions ADD COLUMN device_label TEXT",
            "ALTER TABLE tasks ADD COLUMN priority TEXT",
            "ALTER TABLE tasks ADD COLUMN scheduled_at TEXT",
            "ALTER TABLE tasks ADD COLUMN recurrence TEXT",
            "ALTER TABLE tasks ADD COLUMN reminder_at TEXT",
            # Project-scoped schedules (backlog item 1): a task/schedule
            # belongs to the project it was created under, so project work
            # stays project-scoped. Organizing scope only — grants nothing.
            "ALTER TABLE tasks ADD COLUMN project_id TEXT REFERENCES projects(project_id)",
        ):
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute(_alter_sql)

    def _migrate_plaintext_database(self: SQLiteStore) -> None:
        """Convert a legacy stdlib-SQLite file before SQLCipher opens it."""
        if not self.db_path.exists() or not self.db_path.read_bytes()[:16].startswith(
            b"SQLite format 3"
        ):
            return
        import sqlite3 as plaintext_sqlite

        legacy_path = self.db_path.with_suffix(".plaintext-backup")
        self.db_path.replace(legacy_path)
        try:
            # `with connection:` commits but does not close, and Windows refuses
            # to unlink/replace a file that still has an open handle. Both
            # connections are therefore closed explicitly before this function
            # touches either file again.
            source = plaintext_sqlite.connect(legacy_path)
            encrypted = self.connect()
            try:
                with source, encrypted:
                    # SQLite dumps do not guarantee parent-before-child INSERT order.
                    # Import under the legacy database's existing integrity state, then
                    # restore enforcement for every normal Raiker connection.
                    encrypted.execute("PRAGMA foreign_keys = OFF")
                    # FTS virtual-table shadow rows are engine-specific. Rebuild this
                    # disposable projection from approved memory after importing,
                    # on whichever engine the destination build has — the source
                    # file's engine is not necessarily available here.
                    engine = self.text_search_engine(encrypted)
                    dump = "\n".join(
                        line for line in source.iterdump() if "approved_memory_fts" not in line
                    )
                    for candidate in ("fts5", "fts4"):
                        dump = dump.replace(f"USING {candidate}(", f"USING {engine}(")
                    encrypted.executescript(dump)
                    encrypted.execute("PRAGMA foreign_keys = ON")
            finally:
                source.close()
                encrypted.close()
            legacy_path.unlink()
        except Exception:
            if self.db_path.exists():
                self.db_path.unlink()
            legacy_path.replace(self.db_path)
            raise

    _ADD_COLUMN_RE = re.compile(
        r"^\s*ALTER\s+TABLE\s+(?P<table>\w+)\s+ADD\s+COLUMN\s+(?P<column>\w+)\b",
        re.IGNORECASE,
    )

    @classmethod
    def _skip_existing_add_columns(cls: type[SQLiteStore], connection: sqlite3.Connection, sql: str) -> str:
        """Drop ADD COLUMN statements whose column is already present.

        SQLite has no ``ADD COLUMN IF NOT EXISTS``, so re-running a migration
        that added columns raises "duplicate column name" on the first one and
        strands every statement after it. Filtering those makes such a script
        idempotent, which is what lets a partially-applied migration resume.
        Splitting on ``;`` is lossless here because the parts are rejoined with
        ``;`` and only whole leading ADD COLUMN statements are dropped.
        """
        kept: list[str] = []
        for statement in sql.split(";"):
            match = cls._ADD_COLUMN_RE.match(statement)
            if match is not None:
                columns = {
                    str(row["name"])
                    for row in connection.execute(
                        f'PRAGMA table_info("{match["table"]}")'
                    ).fetchall()
                }
                if match["column"] in columns:
                    continue
            kept.append(statement)
        return ";".join(kept)

    def _apply_migration(self: SQLiteStore, migration_id: str, sql: str, connection: sqlite3.Connection) -> None:
        if self._applied is not None:
            if migration_id in self._applied:
                return
        else:
            row = connection.execute(
                "SELECT applied_at FROM migrations WHERE migration_id = ?", (migration_id,)
            ).fetchone()
            if row is not None:
                return
        # `executescript` commits implicitly, so a script cannot share a
        # transaction with its own bookkeeping row: a crash between the two is
        # always possible. Idempotency is what makes that safe — the re-run
        # skips whatever already landed and completes the rest. Errors are
        # deliberately not suppressed: a migration whose script did not apply
        # must not be recorded as applied, or it never runs again.
        connection.executescript(self._skip_existing_add_columns(connection, sql))
        connection.execute(
            "INSERT OR IGNORE INTO migrations (migration_id, applied_at) VALUES (?, ?)",
            (migration_id, utc_now()),
        )
        if self._applied is not None:
            self._applied.add(migration_id)

    def _backfill_legacy_account_bootstrap_roles(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        try:
            if (
                connection.execute(
                    "SELECT 1 FROM migrations WHERE migration_id = ?",
                    (LEGACY_ACCOUNT_BOOTSTRAP_ROLES_MIGRATION_ID,),
                ).fetchone()
                is not None
            ):
                connection.commit()
                return

            principals = connection.execute(
                "SELECT p.principal_id, p.delegated_by_user_id, p.role_ids "
                "FROM principals AS p "
                "JOIN account_credentials AS ac ON ac.principal_id = p.principal_id "
                "JOIN users AS u ON u.user_id = p.delegated_by_user_id "
                "WHERE p.principal_type = 'human' AND p.is_active = 1 AND u.is_active = 1 "
                "AND p.delegated_by_user_id IS NOT NULL AND p.delegated_by_user_id != ''"
            ).fetchall()
            required_role_ids = ("rl_admin", "rl_approver", "rl_rgm")
            for principal in principals:
                role_ids = json.loads(principal["role_ids"] or "[]")
                missing_role_ids = [
                    role_id for role_id in required_role_ids if role_id not in role_ids
                ]
                if missing_role_ids:
                    connection.execute(
                        "UPDATE principals SET role_ids = ? WHERE principal_id = ?",
                        (
                            json.dumps([*role_ids, *missing_role_ids], sort_keys=True),
                            principal["principal_id"],
                        ),
                    )
                for role_id in required_role_ids:
                    assignments = connection.execute(
                        "SELECT assignment_id FROM user_role_assignments "
                        "WHERE user_id = ? AND role_id = ? ORDER BY rowid",
                        (principal["delegated_by_user_id"], role_id),
                    ).fetchall()
                    if assignments:
                        connection.executemany(
                            "DELETE FROM user_role_assignments WHERE assignment_id = ?",
                            [(assignment["assignment_id"],) for assignment in assignments[1:]],
                        )
                        continue
                    connection.execute(
                        "INSERT INTO user_role_assignments "
                        "(assignment_id, user_id, role_id, granted_at, granted_by) VALUES (?, ?, ?, ?, ?)",
                        (
                            f"ura_backfill_{principal['principal_id']}_{role_id}",
                            principal["delegated_by_user_id"],
                            role_id,
                            utc_now(),
                            "legacy_account_role_migration",
                        ),
                    )
            connection.execute(
                "INSERT INTO migrations (migration_id, applied_at) VALUES (?, ?)",
                (LEGACY_ACCOUNT_BOOTSTRAP_ROLES_MIGRATION_ID, utc_now()),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _migrate_legacy_controls_to_original_owner(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Copy shared legacy controls once, exclusively to the oldest account."""
        owner = connection.execute(
            "SELECT principal_id FROM account_credentials ORDER BY created_at, principal_id LIMIT 1"
        ).fetchone()
        if owner is not None:
            connection.execute(
                "INSERT OR IGNORE INTO instance_account_guard (singleton, principal_id) VALUES (1, ?)",
                (owner["principal_id"],),
            )
            self.initialize_principal_controls(str(owner["principal_id"]), connection=connection)

    def _backfill_legacy_account_data_owner(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        principal_id = self._original_owner_from_connection(connection)
        if principal_id is None:
            return
        principal = connection.execute(
            "SELECT delegated_by_user_id FROM principals WHERE principal_id = ?", (principal_id,)
        ).fetchone()
        user_id = (
            str(principal["delegated_by_user_id"] or principal_id.removeprefix("principal_"))
            if principal
            else ""
        )
        if (
            not user_id
            or connection.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone()
            is None
        ):
            return
        connection.execute("UPDATE sessions SET user_id = ? WHERE user_id IS NULL", (user_id,))
        connection.execute(
            "UPDATE projects SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,)
        )
        legacy_active = connection.execute(
            "SELECT project_id FROM active_project WHERE scope_id IN ('local_single_user', 'project_scope:legacy') "
            "ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if legacy_active is not None and legacy_active["project_id"] is not None:
            connection.execute(
                "INSERT OR REPLACE INTO active_project (scope_id, project_id, updated_at) VALUES (?, ?, ?)",
                (f"project_scope:{user_id}", legacy_active["project_id"], utc_now()),
            )

    @staticmethod
    def _backfill_owned_context_data(connection: sqlite3.Connection) -> None:
        """Assign pre-account prompt data to the original account, never a later one.

        Resolution belongs to `_original_owner_from_connection`, which prefers
        the guard row and skips deactivated principals. A local copy of that
        query silently files new data against the owner a recovery replaced.
        """
        from raiker.storage.sqlite import SQLiteStore  # defined after its parts

        owner = SQLiteStore._original_owner_from_connection(connection)
        if owner is None:
            return
        principal_id = owner
        connection.execute(
            "UPDATE approved_memory SET owner_principal_id = ? WHERE owner_principal_id IS NULL",
            (principal_id,),
        )
        connection.execute(
            "UPDATE vector_records SET owner_principal_id = ? WHERE owner_principal_id IS NULL",
            (principal_id,),
        )
        connection.execute(
            "UPDATE attachments SET owner_principal_id = ? WHERE owner_principal_id IS NULL",
            (principal_id,),
        )

    @staticmethod
    def _backfill_owned_memory_metadata(connection: sqlite3.Connection) -> None:
        from raiker.storage.sqlite import SQLiteStore  # defined after its parts

        owner = SQLiteStore._original_owner_from_connection(connection)
        if owner is not None:
            connection.execute(
                "UPDATE memory_candidates SET owner_principal_id = ? WHERE owner_principal_id IS NULL",
                (owner,),
            )

    def _backfill_legacy_brain_sources(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Migrate the former shared source list to the original account once."""
        owner = self._original_owner_from_connection(connection)
        legacy_path = self.paths.runtime_dir / "brain-sources.json"
        if owner is None or not legacy_path.exists():
            return
        try:
            raw = json.loads(legacy_path.read_text(encoding="utf-8"))
            sources = [item for item in raw if isinstance(item, str) and item]
        except (OSError, ValueError, TypeError):
            return
        connection.executemany(
            "INSERT OR IGNORE INTO brain_sources (owner_principal_id, path, created_at) VALUES (?, ?, ?)",
            [(owner, source, utc_now()) for source in sources],
        )
        with contextlib.suppress(OSError):
            legacy_path.unlink()

    def _backfill_self_inclusive_project_paths(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Derive paths from the authoritative adjacency list once per database."""
        if (
            connection.execute(
                "SELECT 1 FROM migrations WHERE migration_id = ?",
                (PROJECT_SELF_INCLUSIVE_PATH_MIGRATION_ID,),
            ).fetchone()
            is not None
        ):
            return
        rows = connection.execute("SELECT project_id, parent_id FROM projects").fetchall()
        parents = {str(row[0]): str(row[1]) if row[1] is not None else None for row in rows}
        paths: dict[str, str] = {}

        def resolve(project_id: str, visiting: set[str]) -> str:
            if project_id in paths:
                return paths[project_id]
            if project_id in visiting:
                raise RuntimeError("project_parent_cycle_detected")
            parent_id = parents[project_id]
            parent_path = "/" if parent_id is None else resolve(parent_id, visiting | {project_id})
            paths[project_id] = f"{parent_path}{project_id}/"
            return paths[project_id]

        for project_id in parents:
            resolve(project_id, set())
        connection.executemany(
            "UPDATE projects SET path = ?, updated_at = ? WHERE project_id = ?",
            [(path, utc_now(), project_id) for project_id, path in paths.items()],
        )
        connection.execute(
            "INSERT INTO migrations (migration_id, applied_at) VALUES (?, ?)",
            (PROJECT_SELF_INCLUSIVE_PATH_MIGRATION_ID, utc_now()),
        )
