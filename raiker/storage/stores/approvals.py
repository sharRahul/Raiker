# mypy: disable-error-code="misc"
"""Approvals and everything that stands in for one: standing grants, risk
acceptances, git credential grants and owner questions (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ApprovalRelayRecord, ToolAction

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class ApprovalStore:

    def save_approval_decision_scope(self: SQLiteStore, approval_id: str, hunk_ids: list[str]) -> None:
        """Record which hunks of an approved change set the owner accepted (B14).

        Written before the relay runs, so what executes is decided by a row and
        not by an argument travelling alongside a request. It narrows only: the
        relay refuses anything not already in the approved patch.
        """
        self._execute(
            "UPDATE approvals SET decision_scope_json = ? WHERE approval_id = ?",
            (json.dumps({"accepted_hunks": list(hunk_ids)}, sort_keys=True), approval_id),
        )

    @staticmethod
    def approval_accepted_hunks(approval: dict[str, Any]) -> list[str] | None:
        """The hunks this approval was narrowed to, or ``None`` for all of them.

        ``None`` and ``[]`` are different answers and both are real: nothing
        recorded means the owner accepted the whole change set, which is what
        every approval decided before B14 and what most still decide; an empty
        list means they accepted no part of it.
        """
        raw = approval.get("decision_scope_json")
        if not raw:
            return None
        try:
            parsed = json.loads(str(raw))
        except (TypeError, ValueError):
            return None
        if not isinstance(parsed, dict) or "accepted_hunks" not in parsed:
            return None
        value = parsed.get("accepted_hunks")
        return [str(item) for item in value] if isinstance(value, list) else None


    def create_git_credential_grant(
        self: SQLiteStore,
        *,
        principal_id: str,
        scope: str,
        expires_at: str,
        session_id: str | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        """Record one owner decision to lend the git credential.

        ``scope`` is ``once`` or ``session``. Creating a grant supersedes any
        active one for the same principal: two live grants would mean the owner
        could not tell which decision was in force, and revoking one would leave
        the other standing.
        """
        grant_id = new_id("grant_")
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """UPDATE git_credential_grants SET status = 'superseded', revoked_at = ?
                   WHERE owner_principal_id = ? AND status = 'active'""",
                (now, principal_id),
            )
            connection.execute(
                """INSERT INTO git_credential_grants
                   (grant_id, owner_principal_id, session_id, scope, status, reason,
                    granted_at, expires_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?, ?)""",
                (grant_id, principal_id, session_id, scope, reason[:500], now, expires_at),
            )
        return {
            "grant_id": grant_id,
            "scope": scope,
            "status": "active",
            "granted_at": now,
            "expires_at": expires_at,
            "session_id": session_id,
        }

    def active_git_credential_grant(
        self: SQLiteStore, principal_id: str, *, session_id: str | None = None, now: str | None = None
    ) -> dict[str, Any] | None:
        """The grant that would authorise a git command right now, if any.

        Expiry is evaluated here rather than by a sweep: a grant the owner set to
        last an hour must stop working an hour later whether or not anything has
        run since.
        """
        moment = now or utc_now()
        row = self._row(
            """SELECT * FROM git_credential_grants
               WHERE owner_principal_id = ? AND status = 'active' AND expires_at > ?
               ORDER BY granted_at DESC LIMIT 1""",
            (principal_id, moment),
        )
        if row is None:
            return None
        grant = dict(row)
        # A session grant is exactly that: it does not carry into another chat.
        if (
            str(grant.get("scope")) == "session"
            and grant.get("session_id")
            and session_id is not None
            and str(grant["session_id"]) != session_id
        ):
            return None
        return grant

    def consume_git_credential_grant(
        self: SQLiteStore, grant_id: str, operation: str | None = None
    ) -> None:
        """Count a use, record when and for what, and close a one-shot grant behind it."""
        now = utc_now()
        self._execute(
            """UPDATE git_credential_grants
               SET uses = uses + 1,
                   consumed_at = COALESCE(consumed_at, ?),
                   last_used_at = ?,
                   last_operation = COALESCE(?, last_operation),
                   status = CASE WHEN scope = 'once' THEN 'consumed' ELSE status END
               WHERE grant_id = ?""",
            (now, now, operation, grant_id),
        )

    def last_git_credential_use(self: SQLiteStore, principal_id: str) -> dict[str, Any] | None:
        """DEC-21 Git credential — the most recent loan under any grant, active or not."""
        row = self._row(
            """SELECT last_used_at, last_operation, scope FROM git_credential_grants
               WHERE owner_principal_id = ? AND last_used_at IS NOT NULL
               ORDER BY last_used_at DESC LIMIT 1""",
            (principal_id,),
        )
        return dict(row) if row is not None else None

    def revoke_git_credential_grants(self: SQLiteStore, principal_id: str) -> int:
        return self._execute(
            """UPDATE git_credential_grants SET status = 'revoked', revoked_at = ?
               WHERE owner_principal_id = ? AND status = 'active'""",
            (utc_now(), principal_id),
        )

    def insert_approval(
        self: SQLiteStore,
        approval_id: str,
        action: ToolAction | str,
        status: str = "pending",
        *,
        ttl_hours: float | None = 24.0,
        critical: bool = False,
    ) -> None:
        if isinstance(action, ToolAction):
            action_id = action.action_id
            payload_hash = self.tool_action_payload_sha256(
                action.tool_name,
                json.dumps(action.arguments, sort_keys=True),
                action.risk_level,
            )
        else:
            action_id = action
            row = self.load_tool_action(action_id)
            if row is None:
                raise ValueError(f"unknown_tool_action:{action_id}")
            payload_hash = self.tool_action_payload_sha256(
                str(row["tool_name"]),
                str(row["arguments_json"]),
                str(row["risk_level"]),
            )
        # The approval carries an immutable intent snapshot: the SHA-256 of the
        # proposed action's canonical payload (TOCTOU defense) plus a bounded
        # lifetime. A pending approval that is never resolved expires — its
        # resting state becomes "expired", so a stale grant can never execute.
        created = datetime.now(UTC).replace(microsecond=0)
        created_at = created.isoformat().replace("+00:00", "Z")
        expires_at: str | None = None
        if ttl_hours is not None and ttl_hours > 0:
            expires_at = (created + timedelta(hours=ttl_hours)).isoformat().replace("+00:00", "Z")
        self._execute(
            """
            INSERT INTO approvals
            (approval_id, action_id, status, approval_scope, created_at, expires_at, action_payload_sha256, critical)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval_id,
                action_id,
                status,
                "critical" if critical else "action",
                created_at,
                expires_at,
                payload_hash,
                1 if critical else 0,
            ),
        )

    def expire_approval(self: SQLiteStore, approval_id: str) -> bool:
        """Resolve a still-pending approval to ``expired``.

        Returns True when this call performed the transition. The
        ``status = 'pending'`` guard makes it a no-op (returning False) once the
        approval has already been approved, denied, or expired, so an expiry
        sweep can never clobber a real human decision.
        """
        changed = self._execute(
            "UPDATE approvals SET status = 'expired', resolved_at = ? "
            "WHERE approval_id = ? AND status = 'pending'",
            (utc_now(), approval_id),
        )
        return changed == 1

    def claim_approval_for_execution(self: SQLiteStore, approval_id: str) -> bool:
        """Atomically claim a pending approval for execution (pending → executing).

        Returns True only for the single caller that wins the race. The
        ``WHERE status = 'pending'`` guard on a single UPDATE is the
        single-execution primitive: two concurrent relays cannot both claim the
        same approval, so an approved action executes at most once.
        """
        changed = self._execute(
            "UPDATE approvals SET status = 'executing' "
            "WHERE approval_id = ? AND status = 'pending'",
            (approval_id,),
        )
        return changed == 1

    def finalize_approval_execution(
        self: SQLiteStore, approval_id: str, *, status: str, resolved_by: str
    ) -> bool:
        """Resolve a claimed approval to a terminal outcome (executing → status).

        ``status`` is the terminal state — ``executed`` on success or
        ``execution_failed`` when the target executor ran but failed. The
        ``executing`` guard means only a claimed approval can be finalized.
        """
        changed = self._execute(
            "UPDATE approvals SET status = ?, approved_by = ?, resolved_at = ? "
            "WHERE approval_id = ? AND status = 'executing'",
            (status, resolved_by, utc_now(), approval_id),
        )
        return changed == 1

    def release_approval_claim(self: SQLiteStore, approval_id: str) -> bool:
        """Return a claimed approval to ``pending`` (executing → pending).

        Used only when the re-governed action was blocked *before* any executor
        ran (gate disabled, policy deny, no executor), so nothing was committed
        and a later retry — after the owner fixes the gate — is safe. Clears the
        claim's bookkeeping so the approval looks untouched.
        """
        changed = self._execute(
            "UPDATE approvals SET status = 'pending', approved_by = NULL, resolved_at = NULL "
            "WHERE approval_id = ? AND status = 'executing'",
            (approval_id,),
        )
        return changed == 1


    def insert_standing_grant(self: SQLiteStore, record: dict[str, Any]) -> None:
        """Persist a scoped standing grant. All fields are metadata only.

        The caller (the grant engine) is responsible for the invariants — a
        human ``granted_by``, a sub-critical ``risk_ceiling``, and a mandatory
        ``expires_at``. This method only writes the row it is given.
        """
        self._execute(
            """
            INSERT INTO standing_grants
            (grant_id, principal_id, granted_by, action_type, tool_name,
             scope_pattern, risk_ceiling, reason, created_at, expires_at,
             revoked, revoked_at, revoked_by, use_count, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL, 0, NULL)
            """,
            (
                record["grant_id"],
                record["principal_id"],
                record["granted_by"],
                record["action_type"],
                record.get("tool_name", ""),
                record.get("scope_pattern", "*"),
                record["risk_ceiling"],
                record.get("reason", ""),
                record["created_at"],
                record["expires_at"],
            ),
        )

    def load_standing_grant(self: SQLiteStore, grant_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM standing_grants WHERE grant_id = ?", (grant_id,))
        return dict(row) if row else None

    def list_standing_grants(
        self: SQLiteStore, *, granted_by: str | None = None, include_inactive: bool = True
    ) -> list[dict[str, Any]]:
        """Grants for Security Settings, newest first.

        ``granted_by`` scopes to a single owner (isolation). ``include_inactive``
        controls whether revoked/expired grants are listed — the Security
        Settings surface lists everything so the owner sees the full history.
        """
        conditions: list[str] = []
        params: list[Any] = []
        if granted_by is not None:
            conditions.append("granted_by = ?")
            params.append(granted_by)
        if not include_inactive:
            conditions.append("revoked = 0")
            conditions.append("expires_at > ?")
            params.append(utc_now())
        where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
        rows = self._rows(
            f"SELECT * FROM standing_grants {where}ORDER BY created_at DESC, rowid DESC",
            params,
        )
        return [dict(row) for row in rows]

    def find_active_standing_grants(
        self: SQLiteStore, principal_id: str, action_type: str
    ) -> list[dict[str, Any]]:
        """Active (non-revoked, unexpired) grants for a principal + action type."""
        rows = self._rows(
            """
            SELECT * FROM standing_grants
            WHERE principal_id = ? AND action_type = ?
              AND revoked = 0 AND expires_at > ?
            ORDER BY created_at DESC
            """,
            (principal_id, action_type, utc_now()),
        )
        return [dict(row) for row in rows]

    def revoke_standing_grant(
        self: SQLiteStore, grant_id: str, *, revoked_by: str, granted_by: str | None = None
    ) -> bool:
        """Owner-scoped revoke. Returns False if missing, already revoked, or
        owned by another principal (isolation)."""
        conditions = ["grant_id = ?", "revoked = 0"]
        params: list[Any] = [utc_now(), revoked_by, grant_id]
        if granted_by is not None:
            conditions.append("granted_by = ?")
            params.append(granted_by)
        changed = self._execute(
            f"UPDATE standing_grants SET revoked = 1, revoked_at = ?, revoked_by = ? "
            f"WHERE {' AND '.join(conditions)}",
            params,
        )
        return changed == 1

    def record_standing_grant_use(self: SQLiteStore, grant_id: str) -> None:
        """Increment a grant's use counter (every use is logged with the id)."""
        self._execute(
            "UPDATE standing_grants SET use_count = use_count + 1, last_used_at = ? "
            "WHERE grant_id = ?",
            (utc_now(), grant_id),
        )

    def count_pending_approvals(self: SQLiteStore, session_id: str | None = None) -> int:
        row = self._row(
            "SELECT COUNT(*) AS cnt FROM approvals WHERE status = 'pending'"
            + (
                " AND action_id IN (SELECT action_id FROM tool_actions WHERE session_id = ?)"
                if session_id
                else ""
            ),
            (session_id,) if session_id else (),
        )
        return int(row["cnt"]) if row else 0

    def list_approvals(
        self: SQLiteStore,
        status: str | None = None,
        *,
        user_id: str | None = None,
        principal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        # Most approvals inherit their owner through a chat session. Connector
        # store writes are deliberately sessionless, so their immutable intent
        # binds ownership to the proposing principal instead.
        query = """
            SELECT approvals.*, tool_actions.session_id, tool_actions.turn_id,
                   tool_actions.tool_name, tool_actions.arguments_json,
                   tool_actions.risk_level, tool_actions.proposed_by,
                   tool_actions.owner_principal_id, tool_actions.machine_subject,
                   tool_actions.machine_token_id,
                   proposer.principal_type AS proposer_principal_type,
                   proposer.display_name AS proposer_display_name,
                   tool_actions.machine_key_id,
                   tool_actions.machine_issued_at,
                   tool_actions.machine_expires_at,
                   machine.is_active AS machine_is_active,
                   authorizer.principal_type AS authorizer_principal_type,
                   authorizer.display_name AS authorizer_display_name
            FROM approvals
            JOIN tool_actions ON approvals.action_id = tool_actions.action_id
            LEFT JOIN principals AS proposer
              ON proposer.principal_id = tool_actions.proposed_by
            LEFT JOIN turn_machine_identities AS machine
              ON machine.principal_id = tool_actions.proposed_by
            LEFT JOIN principals AS authorizer
              ON authorizer.principal_id = approvals.approved_by
        """
        params: list[Any] = []
        clauses: list[str] = []
        if principal_id is not None:
            query += """
                LEFT JOIN sessions ON tool_actions.session_id = sessions.session_id
                LEFT JOIN connector_write_intents
                    ON connector_write_intents.approval_id = approvals.approval_id
            """
            if user_id is None:
                clauses.append("connector_write_intents.principal_id = ?")
                params.append(principal_id)
            else:
                clauses.append("(sessions.user_id = ? OR connector_write_intents.principal_id = ?)")
                params.extend((user_id, principal_id))
        elif user_id is not None:
            query += " JOIN sessions ON tool_actions.session_id = sessions.session_id AND sessions.user_id = ?"
            params.append(user_id)
        if status is not None:
            clauses.append("approvals.status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY approvals.created_at DESC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def load_approval(
        self: SQLiteStore,
        approval_id: str,
        *,
        user_id: str | None = None,
        principal_id: str | None = None,
    ) -> dict[str, Any] | None:
        # The normal owner filter is session-based. Connector-store writes have
        # no session row, so their immutable intent is the owner binding.
        owner_join = ""
        owner_filter = ""
        params: tuple[Any, ...]
        if principal_id is not None:
            owner_join = """
                LEFT JOIN sessions ON tool_actions.session_id = sessions.session_id
                LEFT JOIN connector_write_intents
                    ON connector_write_intents.approval_id = approvals.approval_id
            """
            if user_id is None:
                owner_filter = " AND connector_write_intents.principal_id = ?"
                params = (approval_id, principal_id)
            else:
                owner_filter = (
                    " AND (sessions.user_id = ? OR connector_write_intents.principal_id = ?)"
                )
                params = (approval_id, user_id, principal_id)
        elif user_id is not None:
            owner_join = (
                " JOIN sessions ON tool_actions.session_id = sessions.session_id"
                " AND sessions.user_id = ?"
            )
            params = (user_id, approval_id)
        else:
            params = (approval_id,)
        row = self._row(
            """
            SELECT approvals.*, tool_actions.session_id, tool_actions.turn_id,
                   tool_actions.tool_name, tool_actions.arguments_json,
                   tool_actions.risk_level, tool_actions.proposed_by,
                   tool_actions.owner_principal_id, tool_actions.machine_subject,
                   tool_actions.machine_token_id,
                   proposer.principal_type AS proposer_principal_type,
                   proposer.display_name AS proposer_display_name,
                   tool_actions.machine_key_id,
                   tool_actions.machine_issued_at,
                   tool_actions.machine_expires_at,
                   machine.is_active AS machine_is_active,
                   authorizer.principal_type AS authorizer_principal_type,
                   authorizer.display_name AS authorizer_display_name
            FROM approvals
            JOIN tool_actions ON approvals.action_id = tool_actions.action_id
            LEFT JOIN principals AS proposer
              ON proposer.principal_id = tool_actions.proposed_by
            LEFT JOIN turn_machine_identities AS machine
              ON machine.principal_id = tool_actions.proposed_by
            LEFT JOIN principals AS authorizer
              ON authorizer.principal_id = approvals.approved_by
            """
            + owner_join
            + """
            WHERE approvals.approval_id = ?
            """
            + owner_filter,
            params,
        )
        return dict(row) if row else None

    def resolve_approval(
        self: SQLiteStore, approval_id: str, *, status: str, resolved_by: str, resolved_at: str
    ) -> None:
        self._execute(
            "UPDATE approvals SET status = ?, approved_by = ?, resolved_at = ? WHERE approval_id = ? AND status = 'pending'",
            (status, resolved_by, resolved_at, approval_id),
        )

    def answer_owner_question(
        self: SQLiteStore, approval_id: str, *, answers_json: str, answered_by: str, answered_at: str
    ) -> bool:
        """Record the owner's answer to a mid-turn question (ADD-22).

        Resolves the row to ``answered`` rather than ``approved``: nothing was
        permitted, so a status that says it was would make the audit trail read
        as an approval nobody granted. Returns False when the row was not
        pending, which is how a second answer to the same question is refused
        rather than silently overwriting the first.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE approvals SET status = 'answered', answer_json = ?, approved_by = ?, "
                "resolved_at = ? WHERE approval_id = ? AND status = 'pending'",
                (answers_json, answered_by, answered_at, approval_id),
            )
            return cursor.rowcount > 0

    def insert_approval_relay(self: SQLiteStore, relay: ApprovalRelayRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO approval_relay_records
            (relay_id, pairing_id, action_id, status, requested_at, resolved_at, resolved_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relay.relay_id,
                relay.pairing_id,
                relay.action_id,
                relay.status,
                relay.requested_at,
                relay.resolved_at,
                relay.resolved_by,
            ),
        )

    def get_approval_relay(self: SQLiteStore, relay_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM approval_relay_records WHERE relay_id = ?", (relay_id,))
        return dict(row) if row is not None else None

    def resolve_approval_relay(
        self: SQLiteStore, relay_id: str, *, status: str, resolved_by: str
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE approval_relay_records
                   SET status = ?, resolved_at = ?, resolved_by = ?
                   WHERE relay_id = ? AND status = 'pending'""",
                (status, utc_now(), resolved_by, relay_id),
            )
            return cursor.rowcount == 1

    def insert_risk_acceptance(self: SQLiteStore, acceptance: dict[str, Any]) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO risk_acceptances
            (risk_acceptance_id, accepted_by, accepted_for_principal_id, action_id,
             action_type, domain_scope, risk_level, risk_summary, data_involved,
             expected_effect, one_time_or_reusable, expires_at, created_at,
             policy_decision_id, approval_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                acceptance["risk_acceptance_id"],
                acceptance["accepted_by"],
                acceptance["accepted_for_principal_id"],
                acceptance["action_id"],
                acceptance["action_type"],
                acceptance["domain_scope"],
                acceptance["risk_level"],
                acceptance["risk_summary"],
                acceptance["data_involved"],
                acceptance["expected_effect"],
                acceptance.get("one_time_or_reusable", "one_time"),
                acceptance.get("expires_at"),
                acceptance["created_at"],
                acceptance.get("policy_decision_id"),
                acceptance.get("approval_id"),
            ),
        )

    def find_valid_risk_acceptance(
        self: SQLiteStore, principal_id: str, action_type: str, domain_scope: str, risk_level: str
    ) -> dict[str, Any] | None:
        now = utc_now()
        row = self._row(
            """
            SELECT * FROM risk_acceptances
            WHERE accepted_for_principal_id = ?
              AND action_type = ?
              AND domain_scope = ?
              AND risk_level = ?
              AND (expires_at IS NULL OR expires_at >= ?)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (principal_id, action_type, domain_scope, risk_level, now),
        )
        return dict(row) if row else None

    def consume_risk_acceptance(self: SQLiteStore, risk_acceptance_id: str) -> None:
        self._execute(
            "DELETE FROM risk_acceptances WHERE risk_acceptance_id = ?",
            (risk_acceptance_id,),
        )

    def list_risk_acceptances(self: SQLiteStore, principal_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM risk_acceptances"
        params: list[Any] = []
        if principal_id:
            query += " WHERE accepted_for_principal_id = ?"
            params.append(principal_id)
        query += " ORDER BY created_at DESC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]
