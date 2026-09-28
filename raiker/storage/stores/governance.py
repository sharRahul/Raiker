# mypy: disable-error-code="misc"
"""Principals, users and roles, runtime modes, capability gates and decision modes,
managed policy, machine identities and the web blocklist (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ManagedPolicyRule, Role, User, UserRoleAssignment

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class GovernanceStore:

    @staticmethod
    def _principal_user_id_from_connection(
        connection: sqlite3.Connection, principal_id: str
    ) -> str | None:
        """Resolve a principal's user id on an existing connection.

        A CLI-bootstrapped owner is created with no ``delegated_by_user_id``, so
        the delegation column alone resolves to NULL and every user-keyed query
        silently matches nothing. The ``principal_<user_id>`` naming convention
        is the fallback, confirmed against ``users`` so an unrelated principal id
        cannot conjure a user that does not exist.
        """
        row = connection.execute(
            "SELECT delegated_by_user_id FROM principals WHERE principal_id = ?", (principal_id,)
        ).fetchone()
        if row is None:
            return None
        delegated = row["delegated_by_user_id"]
        if delegated:
            return str(delegated)
        inferred = principal_id.removeprefix("principal_")
        exists = connection.execute("SELECT 1 FROM users WHERE user_id = ?", (inferred,)).fetchone()
        return inferred if exists is not None else None

    def principal_user_id(self: SQLiteStore, principal_id: str) -> str | None:
        with self.connect() as connection:
            return self._principal_user_id_from_connection(connection, principal_id)

    def initialize_principal_controls(
        self: SQLiteStore, principal_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None:
        """Seed only the original account from legacy global controls.

        Later accounts intentionally receive no rows: missing gate/model rows are
        interpreted as disabled/unselected by scoped callers.
        """
        owns_connection = connection is None
        if connection is None:
            connection = self.connect()
        try:
            owner = connection.execute(
                "SELECT principal_id FROM account_credentials ORDER BY created_at, principal_id LIMIT 1"
            ).fetchone()
            if owner is None:
                owner = connection.execute(
                    "SELECT principal_id FROM instance_account_guard WHERE singleton = 1"
                ).fetchone()
            if owner is None or str(owner["principal_id"]) != principal_id:
                return
            connection.execute(
                """INSERT OR IGNORE INTO principal_model_control
                SELECT ?, profile_id, model, reasoning_enabled, reasoning_effort, reasoning_mode,
                       reasoning_budget_tokens, updated_at
                FROM model_session_state WHERE session_id = 'terminal-local'""",
                (principal_id,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO principal_model_fallback_sequence
                SELECT ?, profile_ids_json, updated_at FROM model_fallback_sequence
                WHERE session_id = 'terminal-local'""",
                (principal_id,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO principal_model_advisor
                SELECT ?, profile_id, updated_at FROM model_advisor WHERE session_id = 'terminal-local'""",
                (principal_id,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO principal_runtime_mode_state
                SELECT ?, mode_name, status, activated_by, activated_at, reason, updated_at
                FROM runtime_mode_state WHERE status = 'active' ORDER BY created_at DESC LIMIT 1""",
                (principal_id,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO principal_capability_gate_state
                SELECT ?, capability, state, requested_by, requested_at, activated_by, activated_at,
                       reason, readiness_snapshot_json, created_at, updated_at
                FROM capability_gate_state""",
                (principal_id,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO principal_capability_decision_mode
                SELECT ?, capability, decision_mode, set_by, set_at, reason, created_at, updated_at
                FROM capability_decision_mode""",
                (principal_id,),
            )
        finally:
            if owns_connection:
                connection.commit()
                connection.close()


    def list_web_blocklist_rules(self: SQLiteStore, *, principal_id: str | None = None) -> list[str]:
        """Just the rule strings, for the policy layer to compile."""
        return [str(row["rule"]) for row in self.list_web_blocklist(principal_id=principal_id)]

    def list_web_blocklist(self: SQLiteStore, *, principal_id: str | None = None) -> list[dict[str, Any]]:
        """Owner rules, plus any that predate per-owner scoping.

        A row with a NULL owner is included for everyone: it was written before
        the column existed, and dropping it silently would *unblock* something.
        """
        sql = "SELECT * FROM web_egress_blocklist"
        params: list[Any] = []
        if principal_id:
            sql += " WHERE owner_principal_id = ? OR owner_principal_id IS NULL"
            params.append(principal_id)
        sql += " ORDER BY created_at DESC"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def add_web_blocklist_rule(
        self: SQLiteStore,
        rule: str,
        kind: str,
        *,
        principal_id: str | None = None,
        note: str = "",
        created_by: str = "",
    ) -> str:
        rule_id = new_id("wbl_")
        with self.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO web_egress_blocklist
                   (rule_id, owner_principal_id, rule, kind, note, created_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (rule_id, principal_id, rule, kind, note[:500], utc_now(), created_by),
            )
        return rule_id

    def delete_web_blocklist_rule(self: SQLiteStore, rule_id: str, *, principal_id: str | None = None) -> bool:
        sql = "DELETE FROM web_egress_blocklist WHERE rule_id = ?"
        params: list[Any] = [rule_id]
        if principal_id:
            sql += " AND (owner_principal_id = ? OR owner_principal_id IS NULL)"
            params.append(principal_id)
        with self.connect() as connection:
            return connection.execute(sql, params).rowcount > 0

    def insert_managed_policy(self: SQLiteStore, rule: ManagedPolicyRule) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO managed_policies
                (rule_id, effect, tool_pattern, arguments_json, priority, enabled, reason, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.rule_id,
                    rule.effect,
                    rule.tool_pattern,
                    rule.arguments_json,
                    rule.priority,
                    int(rule.enabled),
                    rule.reason,
                    rule.created_by,
                    rule.created_at,
                    rule.updated_at,
                ),
            )

    def list_managed_policies(self: SQLiteStore, enabled_only: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM managed_policies"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY priority ASC, created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def insert_user(self: SQLiteStore, user: User) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO users
                (user_id, display_name, email, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user.user_id,
                    user.display_name,
                    user.email,
                    int(user.is_active),
                    user.created_at,
                    user.updated_at,
                ),
            )

    def list_users(self: SQLiteStore, active_only: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM users"
        params: list[Any] = []
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def load_user(self: SQLiteStore, user_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def deactivate_user(self: SQLiteStore, user_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE users SET is_active = 0, updated_at = ? WHERE user_id = ? AND is_active = 1",
                (utc_now(), user_id),
            )
        return cursor.rowcount > 0

    def insert_role(self: SQLiteStore, role: Role) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO roles
                (role_id, name, description, is_system_role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    role.role_id,
                    role.name,
                    role.description,
                    int(role.is_system_role),
                    role.created_at,
                ),
            )

    def list_roles(self: SQLiteStore) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM roles ORDER BY is_system_role DESC, name ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def load_role(self: SQLiteStore, role_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM roles WHERE role_id = ?", (role_id,)).fetchone()
        return dict(row) if row else None

    def delete_role(self: SQLiteStore, role_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM roles WHERE role_id = ? AND is_system_role = 0",
                (role_id,),
            )
        return cursor.rowcount > 0

    def insert_user_role_assignment(self: SQLiteStore, assignment: UserRoleAssignment) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO user_role_assignments
                (assignment_id, user_id, role_id, granted_at, granted_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    assignment.assignment_id,
                    assignment.user_id,
                    assignment.role_id,
                    assignment.granted_at,
                    assignment.granted_by,
                ),
            )

    def list_user_roles(self: SQLiteStore, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT ura.*, r.name AS role_name, r.description AS role_description
                FROM user_role_assignments ura
                JOIN roles r ON ura.role_id = r.role_id
                WHERE ura.user_id = ?
                ORDER BY ura.granted_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_user_role_assignment(self: SQLiteStore, assignment_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM user_role_assignments WHERE assignment_id = ?",
                (assignment_id,),
            )
        return cursor.rowcount > 0

    def delete_managed_policy(self: SQLiteStore, rule_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM managed_policies WHERE rule_id = ?", (rule_id,)
            )
        return cursor.rowcount > 0


    def get_active_machine_issuer_key(self: SQLiteStore) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM machine_identity_issuers
                   WHERE is_active=1 ORDER BY created_at, key_id LIMIT 1"""
            ).fetchone()
        return dict(row) if row is not None else None

    def get_machine_issuer_key(self: SQLiteStore, key_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM machine_identity_issuers WHERE key_id=? AND is_active=1",
                (key_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_machine_issuer_key_if_absent(
        self: SQLiteStore,
        *,
        workspace_id: str,
        key_id: str,
        public_key: bytes,
        private_key_encrypted: bytes,
    ) -> dict[str, Any]:
        """Atomically install the one active embedded issuer for this workspace."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM machine_identity_issuers
                   WHERE is_active=1 ORDER BY created_at, key_id LIMIT 1"""
            ).fetchone()
            if row is None:
                connection.execute(
                    """INSERT INTO machine_identity_issuers
                       (workspace_id, key_id, public_key, private_key_encrypted,
                        created_at, rotated_at, is_active)
                       VALUES (?, ?, ?, ?, ?, NULL, 1)""",
                    (
                        workspace_id,
                        key_id,
                        public_key,
                        private_key_encrypted,
                        utc_now(),
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM machine_identity_issuers WHERE key_id=?", (key_id,)
                ).fetchone()
            assert row is not None
            return dict(row)

    def list_active_machine_issuer_keys(self: SQLiteStore) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM machine_identity_issuers
                   WHERE is_active=1 ORDER BY created_at, key_id"""
            ).fetchall()
        return [dict(row) for row in rows]

    def insert_turn_machine_identity(self: SQLiteStore, identity: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO turn_machine_identities
                   (principal_id, owner_principal_id, workspace_id, session_id,
                    turn_id, subject, key_id, token_id, issued_at, expires_at,
                    parent_principal_id, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    identity["principal_id"],
                    identity["owner_principal_id"],
                    identity["workspace_id"],
                    identity["session_id"],
                    identity["turn_id"],
                    identity["subject"],
                    identity["key_id"],
                    identity["token_id"],
                    identity["issued_at"],
                    identity["expires_at"],
                    identity.get("parent_principal_id"),
                ),
            )

    def get_turn_machine_identity(self: SQLiteStore, principal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM turn_machine_identities WHERE principal_id=?",
                (principal_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["is_active"] = bool(result["is_active"])
        return result

    def get_turn_machine_identity_for_turn(
        self: SQLiteStore, *, owner_principal_id: str, session_id: str, turn_id: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM turn_machine_identities
                   WHERE owner_principal_id=? AND session_id=? AND turn_id=?
                   ORDER BY issued_at DESC LIMIT 1""",
                (owner_principal_id, session_id, turn_id),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["is_active"] = bool(result["is_active"])
        return result

    def rotate_turn_machine_identity(
        self: SQLiteStore, principal_id: str, *, token_id: str, issued_at: str, expires_at: str
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE turn_machine_identities
                   SET token_id=?, issued_at=?, expires_at=?, is_active=1
                   WHERE principal_id=?""",
                (token_id, issued_at, expires_at, principal_id),
            )
        return cursor.rowcount == 1

    def reactivate_machine_principal(self: SQLiteStore, principal_id: str, *, expires_at: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE principals SET expires_at=?, is_active=1 WHERE principal_id=?",
                (expires_at, principal_id),
            )
        return cursor.rowcount == 1

    def deactivate_turn_machine_identity(self: SQLiteStore, principal_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE turn_machine_identities SET is_active=0 WHERE principal_id=?",
                (principal_id,),
            )
        return cursor.rowcount == 1

    def insert_principal(
        self: SQLiteStore,
        principal_id: str,
        principal_type: str,
        display_name: str,
        delegated_by_user_id: str | None = None,
        model_profile_id: str | None = None,
        session_id: str | None = None,
        role_ids: tuple[str, ...] = (),
        domain_scopes: tuple[str, ...] = (),
        max_runtime_mode: str = "raiker_runtime",
        expires_at: str | None = None,
        is_active: bool = True,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO principals
                (principal_id, principal_type, display_name, delegated_by_user_id,
                 model_profile_id, session_id, role_ids, domain_scopes,
                 max_runtime_mode, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    principal_id,
                    principal_type,
                    display_name,
                    delegated_by_user_id,
                    model_profile_id,
                    session_id,
                    json.dumps(list(role_ids), sort_keys=True),
                    json.dumps(list(domain_scopes), sort_keys=True),
                    max_runtime_mode,
                    utc_now(),
                    expires_at,
                    int(is_active),
                ),
            )

    def record_threat_model_ack(
        self: SQLiteStore, capability: str, acked_by: str, acked_at: str, doc_ref: str = ""
    ) -> None:
        """Record (idempotently) that a human acknowledged a capability's threat model.

        This is the persisted precondition for activating threat-ack-gated
        capabilities (e.g. hosted model runtimes). Recording an acknowledgement
        grants nothing on its own — it only satisfies one activation requirement;
        the transition still runs through the full governed gate.
        """
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(capability) DO UPDATE SET
                     acked_by=excluded.acked_by,
                     acked_at=excluded.acked_at,
                     doc_ref=excluded.doc_ref""",
                (capability, acked_by, acked_at, doc_ref),
            )

    def get_principal(self: SQLiteStore, principal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM principals WHERE principal_id = ?", (principal_id,)
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["role_ids"] = tuple(json.loads(result.get("role_ids", "[]")))
        result["domain_scopes"] = tuple(json.loads(result.get("domain_scopes", "[]")))
        result["is_active"] = bool(result.get("is_active", 1))
        return result

    def list_principals(
        self: SQLiteStore, active_only: bool = True, principal_type: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM principals"
        params: list[Any] = []
        conditions: list[str] = []
        if active_only:
            conditions.append("is_active = 1")
        if principal_type:
            conditions.append("principal_type = ?")
            params.append(principal_type)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["role_ids"] = tuple(json.loads(d.get("role_ids", "[]")))
            d["domain_scopes"] = tuple(json.loads(d.get("domain_scopes", "[]")))
            d["is_active"] = bool(d.get("is_active", 1))
            results.append(d)
        return results

    def deactivate_principal(self: SQLiteStore, principal_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE principals SET is_active = 0 WHERE principal_id = ? AND is_active = 1",
                (principal_id,),
            )
        return cursor.rowcount > 0

    def get_role_name(self: SQLiteStore, role_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT name FROM roles WHERE role_id = ?", (role_id,)
            ).fetchone()
        return str(row["name"]) if row else None


    def get_runtime_mode_state(self: SQLiteStore) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_mode_state ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def get_active_runtime_mode(self: SQLiteStore) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_mode_state WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def get_latest_runtime_mode(self: SQLiteStore) -> dict[str, Any] | None:
        """The most recent runtime state row, active or not.

        ``get_active_runtime_mode`` filters on ``status = 'active'``, so it
        cannot tell "never configured" from "the owner switched the runtime
        off" — both come back as ``None``. With one runtime that distinction is
        the whole of the remaining runtime question, so the authority reads the
        latest row and looks at its status itself.
        """
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_mode_state ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def get_principal_runtime_mode(self: SQLiteStore, principal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM principal_runtime_mode_state WHERE principal_id = ?", (principal_id,)
            ).fetchone()
        return dict(row) if row else None

    def upsert_principal_runtime_mode(self: SQLiteStore, principal_id: str, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO principal_runtime_mode_state
                (principal_id, mode_name, status, activated_by, activated_at, reason, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    principal_id,
                    record["mode_name"],
                    record["status"],
                    record.get("activated_by"),
                    record.get("activated_at"),
                    record.get("reason"),
                    record["updated_at"],
                ),
            )

    def insert_runtime_mode_state(self: SQLiteStore, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_mode_state
                  (runtime_mode_id, mode_name, status, activated_by, activated_at,
                   disabled_by, disabled_at, reason, risk_acceptance_id, approval_id,
                   policy_decision_id, validation_evidence_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["runtime_mode_id"],
                    record["mode_name"],
                    record["status"],
                    record.get("activated_by"),
                    record.get("activated_at"),
                    record.get("disabled_by"),
                    record.get("disabled_at"),
                    record.get("reason"),
                    record.get("risk_acceptance_id"),
                    record.get("approval_id"),
                    record.get("policy_decision_id"),
                    record.get("validation_evidence_id"),
                    record["created_at"],
                    record["updated_at"],
                ),
            )

    def update_runtime_mode_state(self: SQLiteStore, runtime_mode_id: str, updates: dict[str, Any]) -> None:
        sets: list[str] = []
        params: list[Any] = []
        for key in (
            "status",
            "mode_name",
            "activated_by",
            "activated_at",
            "disabled_by",
            "disabled_at",
            "reason",
            "risk_acceptance_id",
            "approval_id",
            "policy_decision_id",
            "validation_evidence_id",
            "updated_at",
        ):
            if key in updates:
                sets.append(f"{key} = ?")
                params.append(updates[key])
        if not sets:
            return
        params.append(runtime_mode_id)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE runtime_mode_state SET {', '.join(sets)} WHERE runtime_mode_id = ?",
                params,
            )

    def disable_all_runtime_modes(self: SQLiteStore, disabled_by: str, reason: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """UPDATE runtime_mode_state SET status = 'disabled', disabled_by = ?,
                   disabled_at = ?, reason = ?, updated_at = ? WHERE status = 'active'""",
                (disabled_by, now, reason, now),
            )


    def get_capability_gate_state(self: SQLiteStore, capability: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM capability_gate_state WHERE capability = ?",
                (capability,),
            ).fetchone()
        return dict(row) if row else None

    def get_principal_capability_gate_state(
        self: SQLiteStore, principal_id: str, capability: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM principal_capability_gate_state WHERE principal_id = ? AND capability = ?",
                (principal_id, capability),
            ).fetchone()
        return dict(row) if row else None

    def list_principal_capability_gate_states(self: SQLiteStore, principal_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM principal_capability_gate_state WHERE principal_id = ? ORDER BY capability",
                (principal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_principal_capability_gate_state(
        self: SQLiteStore, principal_id: str, record: dict[str, Any]
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO principal_capability_gate_state
                (principal_id, capability, state, requested_by, requested_at, activated_by, activated_at,
                 reason, readiness_snapshot_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    principal_id,
                    record["capability"],
                    record["state"],
                    record.get("requested_by"),
                    record.get("requested_at"),
                    record.get("activated_by"),
                    record.get("activated_at"),
                    record.get("reason"),
                    record.get("readiness_snapshot_json"),
                    record["created_at"],
                    record["updated_at"],
                ),
            )

    def list_capability_gate_states(self: SQLiteStore) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM capability_gate_state ORDER BY capability"
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_capability_gate_state(self: SQLiteStore, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO capability_gate_state
                  (capability, state, runtime_mode, requested_by, requested_at,
                   activated_by, activated_at, disabled_by, disabled_at, reason,
                   readiness_snapshot_json, risk_acceptance_id, approval_id,
                   policy_decision_id, event_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["capability"],
                    record["state"],
                    record.get("runtime_mode"),
                    record.get("requested_by"),
                    record.get("requested_at"),
                    record.get("activated_by"),
                    record.get("activated_at"),
                    record.get("disabled_by"),
                    record.get("disabled_at"),
                    record.get("reason"),
                    record.get("readiness_snapshot_json"),
                    record.get("risk_acceptance_id"),
                    record.get("approval_id"),
                    record.get("policy_decision_id"),
                    record.get("event_id"),
                    record["created_at"],
                    record["updated_at"],
                ),
            )

    def delete_capability_gate_state(self: SQLiteStore, capability: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM capability_gate_state WHERE capability = ?",
                (capability,),
            )


    def get_capability_decision_mode(self: SQLiteStore, capability: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT decision_mode FROM capability_decision_mode WHERE capability = ?",
                (capability,),
            ).fetchone()
        return str(row["decision_mode"]) if row else None

    def get_principal_capability_decision_mode(
        self: SQLiteStore, principal_id: str, capability: str
    ) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT decision_mode FROM principal_capability_decision_mode "
                "WHERE principal_id = ? AND capability = ?",
                (principal_id, capability),
            ).fetchone()
        return str(row["decision_mode"]) if row else None

    def list_principal_capability_decision_modes(self: SQLiteStore, principal_id: str) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT capability, decision_mode FROM principal_capability_decision_mode WHERE principal_id = ?",
                (principal_id,),
            ).fetchall()
        return {str(row["capability"]): str(row["decision_mode"]) for row in rows}

    def upsert_principal_capability_decision_mode(
        self: SQLiteStore, principal_id: str, record: dict[str, Any]
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO principal_capability_decision_mode
                (principal_id, capability, decision_mode, set_by, set_at, reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    principal_id,
                    record["capability"],
                    record["decision_mode"],
                    record.get("set_by"),
                    record.get("set_at"),
                    record.get("reason"),
                    record["created_at"],
                    record["updated_at"],
                ),
            )

    def list_capability_decision_modes(self: SQLiteStore) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT capability, decision_mode FROM capability_decision_mode"
            ).fetchall()
        return {str(r["capability"]): str(r["decision_mode"]) for r in rows}

    def upsert_capability_decision_mode(self: SQLiteStore, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO capability_decision_mode
                  (capability, decision_mode, set_by, set_at, reason, event_id,
                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["capability"],
                    record["decision_mode"],
                    record.get("set_by"),
                    record.get("set_at"),
                    record.get("reason"),
                    record.get("event_id"),
                    record["created_at"],
                    record["updated_at"],
                ),
            )
