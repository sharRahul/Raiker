# mypy: disable-error-code="misc"
"""Local accounts, sign-in sessions, per-user settings and account recovery and
purge (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import new_id
from raiker.contracts.models import User

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class AccountStore:

    def original_account_principal_id(self: SQLiteStore) -> str | None:
        """Return the sole destination for unattributed legacy data, if one exists."""
        with self.connect() as connection:
            return self._original_owner_from_connection(connection)

    def claim_initial_account(self: SQLiteStore, principal_id: str) -> bool:
        """Atomically reserve this instance's sole local account."""
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO instance_account_guard (singleton, principal_id) VALUES (1, ?)",
                (principal_id,),
            )
            return cursor.rowcount == 1

    def apply_account_capability_baseline(
        self: SQLiteStore,
        principal_id: str,
        now: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        """Seed a newly created account's versioned capability baseline (BUG-239).

        ``INSERT OR IGNORE``, deliberately: this runs inside account creation,
        where nothing can already be stored, and the weaker write is what makes
        it harmless if it is ever reached twice. A row an owner wrote is never
        replaced by one of these, which is the property the whole decision rests
        on — an expanded default is for accounts that do not exist yet.

        The import is local because ``raiker.runtime.authority`` reaches back
        into this module; the table it reads is pure data with no store of its
        own, so the cycle exists only at import time.
        """
        from raiker.runtime.authority.baseline import baseline_rows

        owns_connection = connection is None
        if connection is None:
            connection = self.connect()
        try:
            for record in baseline_rows(now):
                connection.execute(
                    """INSERT OR IGNORE INTO principal_capability_gate_state
                    (principal_id, capability, state, requested_by, requested_at,
                     activated_by, activated_at, reason, readiness_snapshot_json,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        principal_id,
                        record["capability"],
                        record["state"],
                        record["requested_by"],
                        record["requested_at"],
                        record["activated_by"],
                        record["activated_at"],
                        record["reason"],
                        record["readiness_snapshot_json"],
                        record["created_at"],
                        record["updated_at"],
                    ),
                )
        finally:
            if owns_connection:
                connection.commit()

    def create_initial_account_atomic(
        self: SQLiteStore,
        *,
        user: User,
        principal_id: str,
        role_ids: tuple[str, ...],
        max_runtime_mode: str,
        username: str | None = None,
        password_hash: str | None = None,
        hash_algo: str | None = None,
        fail_after: str | None = None,
    ) -> bool:
        """Create the sole account and all identity state in one transaction."""

        def checkpoint(phase: str) -> None:
            if fail_after == phase:
                raise RuntimeError(f"injected_failure:{phase}")

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                claimed = connection.execute(
                    "INSERT OR IGNORE INTO instance_account_guard (singleton, principal_id) VALUES (1, ?)",
                    (principal_id,),
                )
                if claimed.rowcount != 1:
                    connection.rollback()
                    return False
                checkpoint("guard")
                connection.execute(
                    "INSERT INTO users (user_id, display_name, email, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        user.user_id,
                        user.display_name,
                        user.email,
                        int(user.is_active),
                        user.created_at,
                        user.updated_at,
                    ),
                )
                checkpoint("user")
                connection.execute(
                    """INSERT INTO principals (principal_id, principal_type, display_name, delegated_by_user_id,
                    role_ids, domain_scopes, max_runtime_mode, created_at, is_active)
                    VALUES (?, 'human', ?, ?, ?, '[]', ?, ?, 1)""",
                    (
                        principal_id,
                        user.display_name,
                        user.user_id,
                        json.dumps(list(role_ids)),
                        max_runtime_mode,
                        user.created_at,
                    ),
                )
                checkpoint("principal")
                connection.executemany(
                    "INSERT INTO user_role_assignments (assignment_id, user_id, role_id, granted_at, granted_by) VALUES (?, ?, ?, ?, ?)",
                    [
                        (
                            new_id("ura_"),
                            user.user_id,
                            role_id,
                            user.created_at,
                            "lock_screen_registration",
                        )
                        for role_id in role_ids
                    ],
                )
                if username is not None and password_hash is not None and hash_algo is not None:
                    connection.execute(
                        "INSERT INTO account_credentials (principal_id, username, password_hash, hash_algo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            principal_id,
                            username,
                            password_hash,
                            hash_algo,
                            user.created_at,
                            user.updated_at,
                        ),
                    )
                checkpoint("credential")
                self._backfill_legacy_account_data_owner(connection)
                self._backfill_owned_context_data(connection)
                self._backfill_owned_memory_metadata(connection)
                self.initialize_principal_controls(principal_id, connection=connection)
                self.apply_account_capability_baseline(
                    principal_id, user.created_at, connection=connection
                )
                checkpoint("migration")
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

    def recover_owner_atomic(
        self: SQLiteStore,
        *,
        user: User,
        principal_id: str,
        role_ids: tuple[str, ...],
        old_principal_ids: list[str],
        credential_owner_id: str | None,
        max_runtime_mode: str,
        fail_after: str | None = None,
    ) -> None:
        """Transfer the sole credential and guard to a replacement owner atomically.

        ``credential_owner_id`` is None when no owner has a credential row to
        move — a CLI-bootstrapped owner never has one, and a fresh workspace has
        no owner at all. The principal, guard, and data transfer still run; only
        the credential move is skipped.
        """

        def checkpoint(phase: str) -> None:
            if fail_after == phase:
                raise RuntimeError(f"injected_failure:{phase}")

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if (
                    credential_owner_id is not None
                    and connection.execute(
                        "SELECT 1 FROM account_credentials WHERE principal_id = ?",
                        (credential_owner_id,),
                    ).fetchone()
                    is None
                ):
                    raise ValueError("credential_owner_not_found")
                connection.execute(
                    "INSERT INTO users (user_id, display_name, email, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        user.user_id,
                        user.display_name,
                        user.email,
                        int(user.is_active),
                        user.created_at,
                        user.updated_at,
                    ),
                )
                checkpoint("user")
                connection.execute(
                    """INSERT INTO principals (principal_id, principal_type, display_name, delegated_by_user_id,
                    role_ids, domain_scopes, max_runtime_mode, created_at, is_active)
                    VALUES (?, 'human', ?, ?, ?, '[]', ?, ?, 1)""",
                    (
                        principal_id,
                        user.display_name,
                        user.user_id,
                        json.dumps(list(role_ids)),
                        max_runtime_mode,
                        user.created_at,
                    ),
                )
                connection.executemany(
                    "INSERT INTO user_role_assignments (assignment_id, user_id, role_id, granted_at, granted_by) VALUES (?, ?, ?, ?, ?)",
                    [
                        (new_id("ura_"), user.user_id, role_id, user.created_at, "owner_recovery")
                        for role_id in role_ids
                    ],
                )
                checkpoint("principal")
                old_users = (
                    connection.execute(
                        f"SELECT delegated_by_user_id FROM principals WHERE principal_id IN ({','.join('?' for _ in old_principal_ids)})",
                        old_principal_ids,
                    ).fetchall()
                    if old_principal_ids
                    else []
                )
                self._transfer_owner_scoped_data(
                    connection,
                    old_principal_ids,
                    [
                        str(row["delegated_by_user_id"])
                        for row in old_users
                        if row["delegated_by_user_id"]
                    ],
                    principal_id,
                    user.user_id,
                )
                if credential_owner_id is not None:
                    connection.execute(
                        "UPDATE account_credentials SET principal_id = ? WHERE principal_id = ?",
                        (principal_id, credential_owner_id),
                    )
                # The guard names this instance's sole account either way, and
                # is what the original-owner pointer resolves through.
                connection.execute(
                    "INSERT INTO instance_account_guard (singleton, principal_id) VALUES (1, ?) "
                    "ON CONFLICT(singleton) DO UPDATE SET principal_id = excluded.principal_id",
                    (principal_id,),
                )
                checkpoint("credential")
                if old_principal_ids:
                    marks = ",".join("?" for _ in old_principal_ids)
                    connection.execute(
                        f"UPDATE principals SET is_active = 0 WHERE principal_id IN ({marks})",
                        old_principal_ids,
                    )
                    connection.execute(
                        f"UPDATE api_sessions SET revoked = 1 WHERE principal_id IN ({marks})",
                        old_principal_ids,
                    )
                self.initialize_principal_controls(principal_id, connection=connection)
                checkpoint("finalize")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _transfer_owner_scoped_data(
        connection: sqlite3.Connection,
        old_principal_ids: list[str],
        old_user_ids: list[str],
        principal_id: str,
        user_id: str,
    ) -> None:
        """Move owner-scoped rows without rewriting immutable audit/event history."""
        excluded = {
            "account_credentials",
            "api_sessions",
            "instance_account_guard",
            "migrations",
            "principals",
            "users",
        }
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        for row in tables:
            table = str(row["name"])
            if table.startswith("sqlite_") or table in excluded:
                continue
            columns = {
                str(column["name"])
                for column in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            for column in ("owner_principal_id", "principal_id"):
                if column in columns and old_principal_ids:
                    marks = ",".join("?" for _ in old_principal_ids)
                    connection.execute(
                        f'UPDATE "{table}" SET "{column}" = ? WHERE "{column}" IN ({marks})',
                        [principal_id, *old_principal_ids],
                    )
            for column in ("owner_user_id", "user_id"):
                if column in columns and old_user_ids:
                    marks = ",".join("?" for _ in old_user_ids)
                    connection.execute(
                        f'UPDATE "{table}" SET "{column}" = ? WHERE "{column}" IN ({marks})',
                        [user_id, *old_user_ids],
                    )

    def rollback_initial_registration(self: SQLiteStore, principal_id: str, user_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM user_role_assignments WHERE user_id = ?", (user_id,))
            connection.execute(
                "DELETE FROM account_credentials WHERE principal_id = ?", (principal_id,)
            )
            connection.execute("DELETE FROM principals WHERE principal_id = ?", (principal_id,))
            connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            connection.execute(
                "DELETE FROM instance_account_guard WHERE singleton = 1 AND principal_id = ?",
                (principal_id,),
            )

    def principal_mfa_enrolled(self: SQLiteStore, principal_id: str) -> bool:
        row = self._row(
            "SELECT mfa_enrolled FROM account_credentials WHERE principal_id = ?",
            (principal_id,),
        )
        return bool(row["mfa_enrolled"]) if row else False

    def upsert_account(
        self: SQLiteStore,
        principal_id: str,
        username: str,
        password_hash: str,
        hash_algo: str,
        created_at: str,
        updated_at: str,
    ) -> None:
        self._execute(
            """INSERT INTO account_credentials
               (principal_id, username, password_hash, hash_algo, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(principal_id) DO UPDATE SET
                 username=excluded.username,
                 password_hash=excluded.password_hash,
                 hash_algo=excluded.hash_algo,
                 updated_at=excluded.updated_at""",
            (principal_id, username, password_hash, hash_algo, created_at, updated_at),
        )

    def get_account_by_username(self: SQLiteStore, username: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM account_credentials WHERE username = ?", (username,))
        return dict(row) if row is not None else None

    def get_account(self: SQLiteStore, principal_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM account_credentials WHERE principal_id = ?", (principal_id,))
        return dict(row) if row is not None else None

    def account_scope(self: SQLiteStore, principal_id: str | None) -> str | None:
        """Resolve a real local account for a human or delegated machine actor.

        Reads are owner-scoped for accounts and unscoped otherwise. The terminal
        client sends ``UserMetadata``'s default ``local_user``, which is truthy
        but is not a principal — scoping on mere truthiness silently hides the
        CLI's own project, connectors, memory, and model selection.
        """
        if not principal_id:
            return None
        if self.get_account(principal_id) is not None:
            return principal_id
        principal = self.get_principal(principal_id)
        if principal is None or principal.get("principal_type") != "ai_agent":
            return None
        user_id = principal.get("delegated_by_user_id")
        if not user_id:
            return None
        rows = self._rows(
            """SELECT account_credentials.principal_id
               FROM account_credentials
               JOIN principals
                 ON principals.principal_id = account_credentials.principal_id
               WHERE principals.delegated_by_user_id = ?
               ORDER BY account_credentials.principal_id LIMIT 2""",
            (user_id,),
        )
        return str(rows[0]["principal_id"]) if len(rows) == 1 else None

    def set_account_failed(
        self: SQLiteStore, principal_id: str, failed_attempts: int, locked_until: str | None
    ) -> None:
        self._execute(
            "UPDATE account_credentials SET failed_attempts = ?, locked_until = ? "
            "WHERE principal_id = ?",
            (failed_attempts, locked_until, principal_id),
        )

    def set_account_mfa(
        self: SQLiteStore,
        principal_id: str,
        enrolled: bool,
        secret_encrypted: bytes | None,
        backup_codes_hashed: str | None,
    ) -> None:
        self._execute(
            "UPDATE account_credentials SET mfa_enrolled = ?, mfa_secret_encrypted = ?, "
            "backup_codes_hashed = ? WHERE principal_id = ?",
            (int(enrolled), secret_encrypted, backup_codes_hashed, principal_id),
        )

    def set_account_password(
        self: SQLiteStore, principal_id: str, password_hash: str, hash_algo: str, updated_at: str
    ) -> None:
        self._execute(
            "UPDATE account_credentials SET password_hash = ?, hash_algo = ?, updated_at = ? "
            "WHERE principal_id = ?",
            (password_hash, hash_algo, updated_at, principal_id),
        )

    def delete_account(self: SQLiteStore, principal_id: str) -> None:
        self._execute("DELETE FROM account_credentials WHERE principal_id = ?", (principal_id,))

    @staticmethod
    def _delete_rows_orphaned_by_purge(connection: sqlite3.Connection) -> None:
        """Remove rows whose parent the purge sweep just deleted.

        The sweep can only match tables carrying an owner/session/project column.
        A child that references a swept parent but carries none of those columns
        is unreachable by it and is left pointing at a deleted row, which fails
        the deferred foreign-key check at COMMIT. Five such edges exist today
        (`policy_decisions` and `approvals` -> `tool_actions`, `gist_memories` ->
        `eidetic_observations`, and both `*_relationship*` tables ->
        `approved_memory`), and hardcoding them would rot the next time a table
        is added — so let SQLite name the orphans its own deletes created.

        Callers must hold a transaction whose starting state had no violations,
        or this removes pre-existing orphans too. `purge_account` is such a
        caller: the workspaces it runs against are foreign-key-clean.
        """
        # Deleting an orphan can orphan its own child, so iterate to a fixed
        # point. Bounded because each pass strictly shrinks the FK depth still
        # to be resolved; the cap only stops a pathological cycle from spinning.
        for _ in range(8):
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if not violations:
                return
            for violation in violations:
                connection.execute(f'DELETE FROM "{violation[0]}" WHERE rowid = ?', (violation[1],))
        raise RuntimeError("purge_orphan_cleanup_did_not_converge")

    def purge_account(self: SQLiteStore, principal_id: str) -> None:
        """Irreversibly remove an account and all its per-principal data."""
        with self.connect() as connection:
            # The sweep below walks `sqlite_master`, which is table-creation
            # order — parent before child. `sessions` is created before `turns`,
            # and `turns.session_id` references it, so deleting the owner's
            # sessions raises `FOREIGN KEY constraint failed` on any account that
            # ever held a conversation. Defer enforcement to COMMIT instead of
            # topologically sorting 87 tables: order stops mattering, and a purge
            # that really would orphan a row still fails, just at commit.
            #
            # The pragma only holds for the transaction it is set in — SQLite
            # resets it at each COMMIT/ROLLBACK, and setting it outside a
            # transaction is silently undone when the first DELETE opens one.
            # BEGIN first, so it applies to the sweep and cannot leak past it.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("PRAGMA defer_foreign_keys = ON")
            # Captured before the deletes below: approved_memory_fts and
            # memory_projections are keyed only by memory_id (no owner column),
            # so the owner-keyed sweep never matches them and the FTS row would
            # keep the purged memory's full plaintext. The markdown exports are
            # not rows at all and are unlinked after the transaction commits.
            memory_ids = [
                str(row["memory_id"])
                for row in connection.execute(
                    "SELECT memory_id FROM approved_memory WHERE owner_principal_id = ?",
                    (principal_id,),
                ).fetchall()
            ]
            user_id = self._principal_user_id_from_connection(connection, principal_id)
            session_ids = (
                [
                    str(row["session_id"])
                    for row in connection.execute(
                        "SELECT session_id FROM sessions WHERE user_id = ?", (user_id,)
                    ).fetchall()
                ]
                if user_id
                else []
            )
            project_ids = (
                [
                    str(row["project_id"])
                    for row in connection.execute(
                        "SELECT project_id FROM projects WHERE owner_user_id = ?", (user_id,)
                    ).fetchall()
                ]
                if user_id
                else []
            )
            excluded = {
                "account_credentials",
                "api_sessions",
                "instance_account_guard",
                "migrations",
                "principals",
                "users",
            }
            for table_row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall():
                table = str(table_row["name"])
                if table.startswith("sqlite_") or table in excluded:
                    continue
                columns = {
                    str(column["name"])
                    for column in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
                }
                for column, values in (
                    ("owner_principal_id", [principal_id]),
                    ("principal_id", [principal_id]),
                    ("owner_user_id", [user_id] if user_id else []),
                    ("user_id", [user_id] if user_id else []),
                    ("session_id", session_ids),
                    ("project_id", project_ids),
                ):
                    if column in columns and values:
                        marks = ",".join("?" for _ in values)
                        connection.execute(
                            f'DELETE FROM "{table}" WHERE "{column}" IN ({marks})', values
                        )
            for sql in (
                "DELETE FROM account_credentials WHERE principal_id = ?",
                "DELETE FROM user_settings WHERE principal_id = ?",
                "DELETE FROM trusted_contacts WHERE principal_id = ?",
                "DELETE FROM connector_credentials WHERE principal_id = ?",
                "DELETE FROM connector_installations WHERE principal_id = ?",
                "DELETE FROM api_sessions WHERE principal_id = ?",
                "DELETE FROM principal_model_control WHERE principal_id = ?",
                "DELETE FROM principal_configured_models WHERE principal_id = ?",
                "DELETE FROM principal_model_fallback_sequence WHERE principal_id = ?",
                "DELETE FROM principal_model_advisor WHERE principal_id = ?",
                "DELETE FROM principal_runtime_mode_state WHERE principal_id = ?",
                "DELETE FROM principal_capability_gate_state WHERE principal_id = ?",
                "DELETE FROM principal_capability_decision_mode WHERE principal_id = ?",
            ):
                connection.execute(sql, (principal_id,))
            connection.executemany(
                "DELETE FROM approved_memory_fts WHERE memory_id = ?",
                [(memory_id,) for memory_id in memory_ids],
            )
            connection.executemany(
                "DELETE FROM memory_projections WHERE memory_id = ?",
                [(memory_id,) for memory_id in memory_ids],
            )
            connection.execute(
                "UPDATE principals SET is_active = 0 WHERE principal_id = ?", (principal_id,)
            )
            if user_id:
                connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            self._delete_rows_orphaned_by_purge(connection)
            if connection.execute("SELECT 1 FROM account_credentials LIMIT 1").fetchone() is None:
                connection.execute("DELETE FROM instance_account_guard WHERE singleton = 1")
        # Durable markdown exports are plaintext on disk and outlive the rows.
        memory_dir = self.paths.runtime_dir / "memory"
        for memory_id in memory_ids:
            with contextlib.suppress(OSError):
                (memory_dir / f"{memory_id}.md").unlink(missing_ok=True)

    def list_accounts(self: SQLiteStore) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT principal_id, username, mfa_enrolled, created_at FROM account_credentials "
            "ORDER BY created_at ASC",
        )
        return [dict(r) for r in rows]

    def get_user_settings(self: SQLiteStore, principal_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM user_settings WHERE principal_id = ?", (principal_id,))
        return dict(row) if row is not None else None

    def reasoning_retention_enabled(self: SQLiteStore, principal_id: str) -> bool:
        """Has this owner asked for the model's working to be kept? (BUG-215)

        Fail-closed in the privacy direction: an unreadable, missing, or
        differently-shaped settings blob means *not retained*. The one place the
        runtime and the API both read this from, so the turn that decides whether
        to write reasoning and the screen that says whether it is kept can never
        answer differently.
        """
        row = self.get_user_settings(principal_id)
        if row is None:
            return False
        try:
            parsed = json.loads(str(row["settings_json"]))
        except (ValueError, TypeError):
            return False
        if not isinstance(parsed, dict):
            return False
        # Two shapes are in the blob for historical reasons: the settings screen
        # writes flat dotted keys, the dedicated endpoints write nested objects.
        # Both are read, because a setting the owner turned on in one place must
        # not be invisible to the other.
        if parsed.get("privacy.retain_reasoning") is True:
            return True
        privacy = parsed.get("privacy")
        return isinstance(privacy, dict) and privacy.get("retain_reasoning") is True

    def put_user_settings(self: SQLiteStore, principal_id: str, settings_json: str, updated_at: str) -> None:
        self._execute(
            """INSERT INTO user_settings (principal_id, settings_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(principal_id) DO UPDATE SET
                 settings_json=excluded.settings_json, updated_at=excluded.updated_at""",
            (principal_id, settings_json, updated_at),
        )
