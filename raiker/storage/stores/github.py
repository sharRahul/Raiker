# mypy: disable-error-code="misc"
"""Rows for the GitHub connection (ADD-27). No secret is ever stored here.

Secrets live in the vault (``connector_credentials``) under a reference these
rows carry; a credential the owner keeps elsewhere — gh CLI, an OS keychain, an
SSH key file — is named by its selector and never copied.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id, utc_now

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


def _with_json(row: dict[str, Any] | None, *fields: str) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    for name in fields:
        raw = out.get(name)
        try:
            out[name] = json.loads(raw) if isinstance(raw, str) and raw else {}
        except ValueError:
            out[name] = {}
    return out


class GitHubStore:
    # ── credentials ─────────────────────────────────────────────────────
    def create_git_credential(
        self: SQLiteStore,
        *,
        principal_id: str,
        method: str,
        status: str,
        label: str | None = None,
        account_id: str | None = None,
        account_login: str | None = None,
        selector: str | None = None,
        secret_ref: str | None = None,
        key_path: str | None = None,
        app_ref: str | None = None,
        permissions: dict[str, Any] | None = None,
        expires_at: str | None = None,
        refresh_expires_at: str | None = None,
        credential_id: str | None = None,
    ) -> dict[str, Any]:
        cid = credential_id or new_id("gcred_")
        now = utc_now()
        self._execute(
            """INSERT INTO git_credentials
               (credential_id, principal_id, method, label, account_id, account_login,
                selector, secret_ref, key_path, app_ref, permissions_json, expires_at,
                refresh_expires_at, status, selected, created_at, validated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (
                cid, principal_id, method, label, account_id, account_login, selector,
                secret_ref, key_path, app_ref, json.dumps(permissions or {}, sort_keys=True),
                expires_at, refresh_expires_at, status, now,
                now if account_id else None,
            ),
        )
        row = self.load_git_credential(cid)
        assert row is not None
        return row

    def load_git_credential(self: SQLiteStore, credential_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM git_credentials WHERE credential_id = ?", (credential_id,))
        return _with_json(dict(row) if row is not None else None, "permissions_json")

    def list_git_credentials(self: SQLiteStore, principal_id: str) -> list[dict[str, Any]]:
        rows = self._rows(
            """SELECT * FROM git_credentials WHERE principal_id = ?
               ORDER BY selected DESC, created_at DESC""",
            (principal_id,),
        )
        return [r for r in (_with_json(dict(row), "permissions_json") for row in rows) if r]

    def selected_git_credential(self: SQLiteStore, principal_id: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM git_credentials WHERE principal_id = ? AND selected = 1 LIMIT 1",
            (principal_id,),
        )
        return _with_json(dict(row) if row is not None else None, "permissions_json")

    def select_git_credential(self: SQLiteStore, principal_id: str, credential_id: str) -> bool:
        """Make *credential_id* the one in use; every other one of the owner's stops being it."""
        with self.connect() as connection:
            found = connection.execute(
                "SELECT 1 FROM git_credentials WHERE credential_id = ? AND principal_id = ?",
                (credential_id, principal_id),
            ).fetchone()
            if found is None:
                return False
            connection.execute(
                "UPDATE git_credentials SET selected = 0 WHERE principal_id = ?", (principal_id,)
            )
            connection.execute(
                "UPDATE git_credentials SET selected = 1 WHERE credential_id = ?", (credential_id,)
            )
        return True

    def clear_git_credential_selection(self: SQLiteStore, principal_id: str) -> None:
        self._execute("UPDATE git_credentials SET selected = 0 WHERE principal_id = ?", (principal_id,))

    def update_git_credential(self: SQLiteStore, credential_id: str, **fields: Any) -> None:
        allowed = {
            "label", "account_id", "account_login", "selector", "secret_ref", "key_path",
            "expires_at", "refresh_expires_at", "status", "validated_at", "last_error",
            "permissions_json",
        }
        columns = {key: value for key, value in fields.items() if key in allowed}
        if "permissions_json" in columns and not isinstance(columns["permissions_json"], str):
            columns["permissions_json"] = json.dumps(columns["permissions_json"], sort_keys=True)
        if not columns:
            return
        assignments = ", ".join(f"{key} = ?" for key in columns)
        self._execute(
            f"UPDATE git_credentials SET {assignments} WHERE credential_id = ?",  # noqa: S608 — keys from the allow-list above
            (*columns.values(), credential_id),
        )

    def delete_git_credential(self: SQLiteStore, credential_id: str) -> bool:
        return bool(
            self._execute("DELETE FROM git_credentials WHERE credential_id = ?", (credential_id,))
        )

    # ── sign-in attempts ───────────────────────────────────────────────
    def create_github_auth_attempt(
        self: SQLiteStore,
        *,
        principal_id: str,
        session_ref: str,
        method: str,
        app_ref: str,
        expires_at: str,
        state_hash: str | None = None,
        redirect_uri: str | None = None,
        user_code: str | None = None,
        verification_uri: str | None = None,
        poll_interval: int | None = None,
    ) -> dict[str, Any]:
        attempt_id = new_id("ghauth_")
        now = utc_now()
        self._execute(
            """INSERT INTO github_auth_attempts
               (attempt_id, principal_id, session_ref, method, app_ref, state_hash,
                redirect_uri, user_code, verification_uri, poll_interval, next_poll_at,
                created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                attempt_id, principal_id, session_ref, method, app_ref, state_hash,
                redirect_uri, user_code, verification_uri, poll_interval, now, now, expires_at,
            ),
        )
        row = self.load_github_auth_attempt(attempt_id)
        assert row is not None
        return row

    def load_github_auth_attempt(self: SQLiteStore, attempt_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM github_auth_attempts WHERE attempt_id = ?", (attempt_id,))
        return dict(row) if row is not None else None

    def find_github_auth_attempt_by_state(self: SQLiteStore, state_hash: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM github_auth_attempts WHERE state_hash = ? LIMIT 1", (state_hash,)
        )
        return dict(row) if row is not None else None

    def claim_github_auth_attempt(self: SQLiteStore, attempt_id: str) -> bool:
        """Move a pending attempt to ``redeeming`` once: a second redemption finds nothing."""
        return bool(
            self._execute(
                """UPDATE github_auth_attempts SET outcome = 'redeeming'
                   WHERE attempt_id = ? AND outcome = 'pending'""",
                (attempt_id,),
            )
        )

    def release_github_auth_attempt(self: SQLiteStore, attempt_id: str) -> None:
        """Put a claimed attempt back to ``pending``: GitHub said not yet."""
        self._execute(
            "UPDATE github_auth_attempts SET outcome = 'pending' WHERE attempt_id = ? AND outcome = 'redeeming'",
            (attempt_id,),
        )

    def close_github_auth_attempt(
        self: SQLiteStore,
        attempt_id: str,
        outcome: str,
        reason: str | None = None,
        credential_id: str | None = None,
    ) -> None:
        self._execute(
            """UPDATE github_auth_attempts
               SET outcome = ?, outcome_reason = ?, credential_id = COALESCE(?, credential_id),
                   closed_at = ?
               WHERE attempt_id = ?""",
            (outcome, reason, credential_id, utc_now(), attempt_id),
        )

    def set_github_auth_poll(self: SQLiteStore, attempt_id: str, *, interval: int, next_poll_at: str) -> None:
        self._execute(
            "UPDATE github_auth_attempts SET poll_interval = ?, next_poll_at = ? WHERE attempt_id = ?",
            (interval, next_poll_at, attempt_id),
        )

    # ── App configuration ───────────────────────────────────────────────
    def upsert_github_app(self: SQLiteStore, app_ref: str, *, updated_by: str | None, **fields: Any) -> None:
        allowed = {
            "app_id", "client_id", "slug", "private_key_ref", "client_secret_ref",
            "webhook_secret_ref", "callback_url", "setup_url", "webhooks_enabled",
            "validated_at", "validation_json",
        }
        values = {key: value for key, value in fields.items() if key in allowed}
        if "validation_json" in values and not isinstance(values["validation_json"], str):
            values["validation_json"] = json.dumps(values["validation_json"], sort_keys=True)
        now = utc_now()
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM github_apps WHERE app_ref = ?", (app_ref,)
            ).fetchone()
            if exists is None:
                connection.execute(
                    "INSERT INTO github_apps (app_ref, updated_at, updated_by) VALUES (?, ?, ?)",
                    (app_ref, now, updated_by),
                )
            if values:
                assignments = ", ".join(f"{key} = ?" for key in values)
                connection.execute(
                    f"UPDATE github_apps SET {assignments}, updated_at = ?, updated_by = ? WHERE app_ref = ?",  # noqa: S608 — keys from the allow-list above
                    (*values.values(), now, updated_by, app_ref),
                )

    def load_github_app(self: SQLiteStore, app_ref: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM github_apps WHERE app_ref = ?", (app_ref,))
        return _with_json(dict(row) if row is not None else None, "validation_json")

    def delete_github_app(self: SQLiteStore, app_ref: str) -> bool:
        return bool(self._execute("DELETE FROM github_apps WHERE app_ref = ?", (app_ref,)))

    # ── installations and repositories ──────────────────────────────────
    def upsert_github_installation(
        self: SQLiteStore,
        installation_id: str,
        *,
        app_ref: str,
        status: str,
        principal_id: str | None = None,
        account_id: str | None = None,
        account_login: str | None = None,
        account_type: str | None = None,
        repository_selection: str | None = None,
        permissions: dict[str, Any] | None = None,
    ) -> None:
        self._execute(
            """INSERT INTO github_installations
               (installation_id, app_ref, principal_id, account_id, account_login, account_type,
                repository_selection, permissions_json, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(installation_id) DO UPDATE SET
                 app_ref = excluded.app_ref,
                 principal_id = COALESCE(excluded.principal_id, github_installations.principal_id),
                 account_id = COALESCE(excluded.account_id, github_installations.account_id),
                 account_login = COALESCE(excluded.account_login, github_installations.account_login),
                 account_type = COALESCE(excluded.account_type, github_installations.account_type),
                 repository_selection = COALESCE(excluded.repository_selection, github_installations.repository_selection),
                 permissions_json = CASE WHEN excluded.permissions_json = '{}'
                                         THEN github_installations.permissions_json
                                         ELSE excluded.permissions_json END,
                 status = excluded.status,
                 updated_at = excluded.updated_at""",
            (
                installation_id, app_ref, principal_id, account_id, account_login, account_type,
                repository_selection, json.dumps(permissions or {}, sort_keys=True), status, utc_now(),
            ),
        )

    def load_github_installation(self: SQLiteStore, installation_id: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM github_installations WHERE installation_id = ?", (installation_id,)
        )
        return _with_json(dict(row) if row is not None else None, "permissions_json")

    def list_github_installations(self: SQLiteStore, *, principal_id: str | None = None) -> list[dict[str, Any]]:
        if principal_id is None:
            rows = self._rows("SELECT * FROM github_installations ORDER BY updated_at DESC", ())
        else:
            rows = self._rows(
                "SELECT * FROM github_installations WHERE principal_id = ? ORDER BY updated_at DESC",
                (principal_id,),
            )
        return [r for r in (_with_json(dict(row), "permissions_json") for row in rows) if r]

    def replace_github_repositories(
        self: SQLiteStore,
        principal_id: str,
        credential_id: str,
        repositories: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Record what *credential_id* can reach now; anything it no longer can is marked removed.

        Selection survives a refresh by repository id, so a rename keeps it and a
        repository that left keeps its row (status ``removed``) for the record.
        """
        now = utc_now()
        seen: set[str] = set()
        with self.connect() as connection:
            for repo in repositories:
                repository_id = str(repo["repository_id"])
                seen.add(repository_id)
                connection.execute(
                    """INSERT INTO github_repositories
                       (principal_id, credential_id, repository_id, full_name, installation_id,
                        permissions_json, private, selected, status, checked_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'available', ?)
                       ON CONFLICT(principal_id, credential_id, repository_id) DO UPDATE SET
                         full_name = excluded.full_name,
                         installation_id = excluded.installation_id,
                         permissions_json = excluded.permissions_json,
                         private = excluded.private,
                         status = 'available',
                         checked_at = excluded.checked_at""",
                    (
                        principal_id, credential_id, repository_id, str(repo["full_name"]),
                        repo.get("installation_id"),
                        json.dumps(repo.get("permissions") or {}, sort_keys=True),
                        1 if repo.get("private") else 0, now,
                    ),
                )
            existing = connection.execute(
                """SELECT repository_id FROM github_repositories
                   WHERE principal_id = ? AND credential_id = ? AND status = 'available'""",
                (principal_id, credential_id),
            ).fetchall()
            removed = 0
            for row in existing:
                if str(row[0]) not in seen:
                    connection.execute(
                        """UPDATE github_repositories SET status = 'removed', selected = 0, checked_at = ?
                           WHERE principal_id = ? AND credential_id = ? AND repository_id = ?""",
                        (now, principal_id, credential_id, str(row[0])),
                    )
                    removed += 1
        return {"available": len(seen), "removed": removed}

    def list_github_repositories(
        self: SQLiteStore, principal_id: str, *, credential_id: str | None = None
    ) -> list[dict[str, Any]]:
        if credential_id is None:
            rows = self._rows(
                """SELECT * FROM github_repositories WHERE principal_id = ?
                   ORDER BY selected DESC, full_name""",
                (principal_id,),
            )
        else:
            rows = self._rows(
                """SELECT * FROM github_repositories WHERE principal_id = ? AND credential_id = ?
                   ORDER BY selected DESC, full_name""",
                (principal_id, credential_id),
            )
        return [r for r in (_with_json(dict(row), "permissions_json") for row in rows) if r]

    def set_github_repository_selected(
        self: SQLiteStore, principal_id: str, credential_id: str, repository_id: str, selected: bool
    ) -> bool:
        return bool(
            self._execute(
                """UPDATE github_repositories SET selected = ?
                   WHERE principal_id = ? AND credential_id = ? AND repository_id = ?
                     AND status = 'available'""",
                (1 if selected else 0, principal_id, credential_id, repository_id),
            )
        )

    def github_repository_by_name(
        self: SQLiteStore, principal_id: str, full_name: str
    ) -> dict[str, Any] | None:
        row = self._row(
            """SELECT * FROM github_repositories
               WHERE principal_id = ? AND lower(full_name) = lower(?)
               ORDER BY status = 'available' DESC, checked_at DESC LIMIT 1""",
            (principal_id, full_name),
        )
        return _with_json(dict(row) if row is not None else None, "permissions_json")

    # ── webhook deliveries ──────────────────────────────────────────────
    def claim_github_delivery(
        self: SQLiteStore, delivery_id: str, event: str, installation_id: str | None
    ) -> bool:
        """True the first time a delivery id is seen; a replay claims nothing."""
        return bool(
            self._execute(
                """INSERT OR IGNORE INTO github_webhook_deliveries
                   (delivery_id, event, installation_id, received_at, outcome)
                   VALUES (?, ?, ?, ?, 'received')""",
                (delivery_id, event, installation_id, utc_now()),
            )
        )

    def settle_github_delivery(self: SQLiteStore, delivery_id: str, outcome: str) -> None:
        self._execute(
            "UPDATE github_webhook_deliveries SET outcome = ? WHERE delivery_id = ?",
            (outcome, delivery_id),
        )

    # ── delegations ─────────────────────────────────────────────────────
    def create_repository_delegation(
        self: SQLiteStore,
        *,
        principal_id: str,
        repository: str,
        operations: list[str],
        expires_at: str,
        created_by: str,
        repository_id: str | None = None,
        branch_pattern: str | None = None,
        allow_pull_request: bool = False,
        max_actions: int | None = None,
        credential_id: str | None = None,
        parent_delegation_id: str | None = None,
        task_id: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        delegation_id = new_id("deleg_")
        self._execute(
            """INSERT INTO repository_delegations
               (delegation_id, principal_id, repository, repository_id, operations_json,
                branch_pattern, allow_pull_request, expires_at, max_actions, credential_id,
                parent_delegation_id, task_id, created_by, created_at, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                delegation_id, principal_id, repository, repository_id,
                json.dumps(sorted(set(operations))), branch_pattern,
                1 if allow_pull_request else 0, expires_at, max_actions, credential_id,
                parent_delegation_id, task_id, created_by, utc_now(), note,
            ),
        )
        row = self.load_repository_delegation(delegation_id)
        assert row is not None
        return row

    def load_repository_delegation(self: SQLiteStore, delegation_id: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM repository_delegations WHERE delegation_id = ?", (delegation_id,)
        )
        if row is None:
            return None
        out = dict(row)
        try:
            out["operations"] = list(json.loads(out.get("operations_json") or "[]"))
        except ValueError:
            out["operations"] = []
        return out

    def list_repository_delegations(
        self: SQLiteStore, principal_id: str, *, include_ended: bool = False
    ) -> list[dict[str, Any]]:
        query = "SELECT delegation_id FROM repository_delegations WHERE principal_id = ?"
        if not include_ended:
            query += " AND revoked_at IS NULL AND expires_at > ?"
            rows = self._rows(query + " ORDER BY created_at DESC", (principal_id, utc_now()))
        else:
            rows = self._rows(query + " ORDER BY created_at DESC", (principal_id,))
        found = [self.load_repository_delegation(str(row[0])) for row in rows]
        return [row for row in found if row is not None]

    def revoke_repository_delegation(self: SQLiteStore, delegation_id: str, principal_id: str) -> list[str]:
        """Revoke a delegation and everything narrowed from it, at any depth.

        Returns the ids revoked, the delegation itself first; empty when it was
        not this principal's or had already ended.
        """
        now = utc_now()
        with self.connect() as connection:
            changed = connection.execute(
                """UPDATE repository_delegations SET revoked_at = ?
                   WHERE delegation_id = ? AND principal_id = ? AND revoked_at IS NULL""",
                (now, delegation_id, principal_id),
            ).rowcount
            if not changed:
                return []
            revoked = [delegation_id]
            frontier = [delegation_id]
            while frontier:
                parent = frontier.pop()
                children = [
                    str(row[0])
                    for row in connection.execute(
                        """SELECT delegation_id FROM repository_delegations
                           WHERE parent_delegation_id = ? AND revoked_at IS NULL""",
                        (parent,),
                    ).fetchall()
                ]
                for child in children:
                    connection.execute(
                        "UPDATE repository_delegations SET revoked_at = ? WHERE delegation_id = ?",
                        (now, child),
                    )
                revoked.extend(children)
                frontier.extend(children)
        return revoked

    def count_repository_delegation_action(self: SQLiteStore, delegation_id: str) -> bool:
        """Spend one action of a bounded delegation; False when none is left."""
        return bool(
            self._execute(
                """UPDATE repository_delegations SET actions_used = actions_used + 1
                   WHERE delegation_id = ?
                     AND (max_actions IS NULL OR actions_used < max_actions)""",
                (delegation_id,),
            )
        )
