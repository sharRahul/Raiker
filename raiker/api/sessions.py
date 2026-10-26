from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore


def _parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp regardless of ``Z`` vs ``+00:00`` suffix.

    ``utc_now()`` emits ``...Z`` while ``create_session`` persists ``...+00:00``;
    a lexical string compare of the two disagrees at an identical second (``Z`` >
    ``+``), so expiry checks must compare parsed datetimes, not strings.
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class ApiSession:
    session_id: str
    principal_id: str
    scopes: tuple[str, ...] = ()
    created_at: str = ""
    expires_at: str | None = None
    revoked: bool = False
    scope: str = "control"
    absolute_expires_at: str | None = None
    #: BUG-358 — how the session was established: ``password`` or ``mfa``.
    assurance: str = "password"
    #: Where: ``local`` (this computer's listener) or ``remote``.
    origin: str = "local"
    #: The account's MFA enrolment the session was verified against. A session
    #: verified before MFA was reset or turned off no longer counts as MFA.
    mfa_epoch: int | None = None
    last_seen_at: str | None = None

    def is_expired(self, now: str | None = None) -> bool:
        check = _parse_ts(now or utc_now())
        if self.absolute_expires_at is not None and check > _parse_ts(self.absolute_expires_at):
            return True
        if self.expires_at is None:
            return False
        return check > _parse_ts(self.expires_at)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_token() -> tuple[str, str]:
    raw = secrets.token_hex(32)
    return raw, _hash_token(raw)


class ApiSessionStore:
    def __init__(self, workspace_root: str | Path) -> None:
        self._store = SQLiteStore(workspace_root)

    def create_session(
        self,
        principal_id: str,
        scopes: tuple[str, ...] = ("control",),
        expires_in_seconds: int = 86400 * 30,
        scope: str = "control",
        absolute_expires_in_seconds: int | None = None,
        device_label: str | None = None,
        *,
        assurance: str = "password",
        origin: str = "local",
        mfa_epoch: int | None = None,
        client_hint: str | None = None,
    ) -> tuple[str, ApiSession]:
        from datetime import datetime, timedelta

        raw_token, token_hash = _generate_token()
        session_id = f"api_ses_{secrets.token_hex(12)}"
        now = utc_now()
        expires_at = None
        if expires_in_seconds > 0:
            expires_at = (
                datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
            ).isoformat(timespec="seconds")
        absolute_expires_at = None
        if absolute_expires_in_seconds is not None:
            absolute_expires_at = (
                datetime.now(UTC) + timedelta(seconds=absolute_expires_in_seconds)
            ).isoformat(timespec="seconds")
        import json
        scopes_json = json.dumps(list(scopes))
        with self._store.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO api_sessions
                   (session_id, principal_id, token_hash, scopes, created_at, expires_at,
                    revoked, scope, absolute_expires_at, device_label, assurance, origin,
                    mfa_epoch, client_hint)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    principal_id,
                    token_hash,
                    scopes_json,
                    now,
                    expires_at,
                    scope,
                    absolute_expires_at,
                    device_label,
                    assurance,
                    origin,
                    mfa_epoch,
                    client_hint,
                ),
            )
        session = ApiSession(
            session_id=session_id,
            principal_id=principal_id,
            scopes=scopes,
            created_at=now,
            expires_at=expires_at,
            scope=scope,
            absolute_expires_at=absolute_expires_at,
            assurance=assurance,
            origin=origin,
            mfa_epoch=mfa_epoch,
        )
        return raw_token, session

    def revoke_others_for_principal(self, principal_id: str, keep_session_id: str) -> int:
        with self._store.connect() as connection:
            cursor = connection.execute(
                "UPDATE api_sessions SET revoked = 1 "
                "WHERE principal_id = ? AND session_id != ? AND revoked = 0",
                (principal_id, keep_session_id),
            )
            return cursor.rowcount

    def revoke_all_for_principal(self, principal_id: str) -> int:
        with self._store.connect() as connection:
            cursor = connection.execute(
                "UPDATE api_sessions SET revoked = 1 WHERE principal_id = ? AND revoked = 0",
                (principal_id,),
            )
            return cursor.rowcount

    def touch(self, session_id: str, when: str, *, slide_seconds: int | None = None) -> None:
        """Record activity; with ``slide_seconds``, also push the idle expiry forward.

        The idle expiry never passes the absolute one: a session that is used
        every minute still ends when its hard limit says.
        """
        if slide_seconds is None:
            with self._store.connect() as connection:
                connection.execute(
                    "UPDATE api_sessions SET last_seen_at = ? WHERE session_id = ?",
                    (when, session_id),
                )
            return
        from datetime import timedelta

        slid = (_parse_ts(when) + timedelta(seconds=slide_seconds)).isoformat(timespec="seconds")
        with self._store.connect() as connection:
            connection.execute(
                "UPDATE api_sessions SET last_seen_at = ?, expires_at = CASE "
                "WHEN absolute_expires_at IS NOT NULL AND absolute_expires_at < ? "
                "THEN absolute_expires_at ELSE ? END WHERE session_id = ?",
                (when, slid, slid, session_id),
            )

    def raise_assurance(self, session_id: str, mfa_epoch: int) -> None:
        """Mark a session MFA-verified against the account's current enrolment."""
        with self._store.connect() as connection:
            connection.execute(
                "UPDATE api_sessions SET assurance = 'mfa', mfa_epoch = ? WHERE session_id = ?",
                (mfa_epoch, session_id),
            )

    def get_by_token(self, raw_token: str) -> ApiSession | None:
        token_hash = _hash_token(raw_token)
        return self._row_to_session(token_hash, by_hash=True)

    def get_by_session_id(self, session_id: str) -> ApiSession | None:
        return self._row_to_session(session_id, by_hash=False)

    def _row_to_session(self, value: str, by_hash: bool) -> ApiSession | None:
        col = "token_hash" if by_hash else "session_id"
        with self._store.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM api_sessions WHERE {col} = ?", (value,)
            ).fetchone()
        if row is None:
            return None
        return self._deserialize(dict(row))

    def revoke_session(self, session_id: str) -> bool:
        with self._store.connect() as connection:
            cursor = connection.execute(
                "UPDATE api_sessions SET revoked = 1 WHERE session_id = ?",
                (session_id,),
            )
            return cursor.rowcount > 0

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._store.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM api_sessions ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_for_principal(self, principal_id: str) -> list[dict[str, Any]]:
        """Device sessions for one account (no token material)."""
        with self._store.connect() as connection:
            rows = connection.execute(
                "SELECT session_id, created_at, last_seen_at, device_label, revoked, "
                "expires_at, absolute_expires_at, scope, assurance, origin, mfa_epoch, "
                "client_hint FROM api_sessions WHERE principal_id = ? "
                "ORDER BY created_at DESC",
                (principal_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def owns_session(self, principal_id: str, session_id: str) -> bool:
        with self._store.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM api_sessions WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            ).fetchone()
        return row is not None

    def _deserialize(self, row: dict[str, Any]) -> ApiSession:
        import json
        scopes = tuple(json.loads(row.get("scopes", "[]")))
        return ApiSession(
            session_id=str(row["session_id"]),
            principal_id=str(row["principal_id"]),
            scopes=scopes,
            created_at=str(row.get("created_at", "")),
            expires_at=str(row["expires_at"]) if row.get("expires_at") else None,
            revoked=bool(row.get("revoked", 0)),
            scope=str(row.get("scope") or "control"),
            absolute_expires_at=(
                str(row["absolute_expires_at"]) if row.get("absolute_expires_at") else None
            ),
            assurance=str(row.get("assurance") or "password"),
            origin=str(row.get("origin") or "local"),
            mfa_epoch=int(row["mfa_epoch"]) if row.get("mfa_epoch") is not None else None,
            last_seen_at=str(row["last_seen_at"]) if row.get("last_seen_at") else None,
        )
