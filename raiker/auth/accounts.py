"""Local account service and the server-authoritative login state machine.

One local account maps to one ``principal_id``; all per-user data (connector
credentials, sessions, chats, tasks, settings) already keys on ``principal_id``,
so accounts are fully isolated from one another.

Login is a server-driven state machine: password -> (optional) MFA -> session.
A password-only success yields a ``mfa_pending`` ticket that cannot reach any
governed API; only MFA verification upgrades it to a ``control`` session. Failed
attempts are rate-limited and the account locks after a threshold. All failures
return one generic error to prevent username enumeration.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.api.sessions import ApiSessionStore
from raiker.auth import mfa, passwords
from raiker.cli.principal_resolver import (
    OWNER_BOOTSTRAP_ROLES,
    _ensure_bootstrap_roles,
)
from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.runtime.authority.models import RAIKER_RUNTIME
from raiker.storage.sqlite import SQLiteStore

LOCKOUT_THRESHOLD = 5
LOCKOUT_SECONDS = 900  # 15 minutes
MFA_TICKET_TTL = 300  # 5 minutes
PASSWORD_RECOVERY_TICKET_TTL = 300  # 5 minutes
SESSION_TTL = 86400 * 7  # sliding 7 days
SESSION_ABSOLUTE_TTL = 86400 * 30  # hard 30-day cap
ELEVATED_TTL = 300  # 5 minutes
GENERIC_AUTH_ERROR = "Invalid username or password"


class AuthError(Exception):
    """Raised for any authentication failure. Message is safe to surface."""


@dataclass(frozen=True)
class LoginResult:
    stage: str  # "session" | "mfa_required"
    principal_id: str
    token: str | None = None
    ticket: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class AccountService:
    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root)
        passwords.prepare_dummy_hashes()
        self._store = SQLiteStore(workspace_root)
        self._sessions = ApiSessionStore(workspace_root)

    # ── Registration ────────────────────────────────────────────────────────
    def register(self, username: str, password: str) -> str:
        username = username.strip()
        if not username or not password:
            raise AuthError("Username and password are required")
        _ensure_bootstrap_roles(self._store)
        now = utc_now()
        user_id = f"user_{secrets.token_hex(8)}"
        principal_id = f"principal_{user_id}"
        encoded, algo = passwords.hash_password(password)
        created = self._store.create_initial_account_atomic(
            user=User(user_id, username, None, True, now, now), principal_id=principal_id,
            username=username, password_hash=encoded, hash_algo=algo,
            role_ids=OWNER_BOOTSTRAP_ROLES, max_runtime_mode=RAIKER_RUNTIME,
        )
        if not created:
            raise AuthError("Create new user and separate Raiker instance instead")
        return principal_id

    # ── Login state machine ─────────────────────────────────────────────────
    def login(self, username: str, password: str, device_label: str | None = None) -> LoginResult:
        account = self._store.get_account_by_username(username.strip())
        if account is None:
            # Spend comparable work so a missing user is indistinguishable by timing.
            passwords.spend_dummy_verify(password)
            raise AuthError(GENERIC_AUTH_ERROR)
        password_valid = passwords.verify_password(
            password, account["password_hash"], account["hash_algo"]
        )
        verified_algo = passwords.verification_algorithm(
            account["password_hash"], account["hash_algo"]
        )
        denied = (
            not self._account_principal_is_active(account["principal_id"])
            or self._is_locked(account)
            or not password_valid
        )
        if denied:
            passwords.spend_dummy_verify(password, exclude_algo=verified_algo)
        if not self._account_principal_is_active(account["principal_id"]):
            raise AuthError(GENERIC_AUTH_ERROR)
        if self._is_locked(account):
            raise AuthError(GENERIC_AUTH_ERROR)
        if not password_valid:
            self._register_failure(account)
            raise AuthError(GENERIC_AUTH_ERROR)
        self._reset_failures(account["principal_id"])
        self._maybe_rehash(account, password)
        if account["mfa_enrolled"]:
            ticket, _ = self._sessions.create_session(
                account["principal_id"],
                scope="mfa_pending",
                expires_in_seconds=MFA_TICKET_TTL,
                device_label=device_label,
            )
            return LoginResult(stage="mfa_required", principal_id=account["principal_id"], ticket=ticket)
        token = self._issue_control_session(account["principal_id"], device_label)
        return LoginResult(stage="session", principal_id=account["principal_id"], token=token)

    def verify_mfa(self, ticket_token: str, code: str) -> LoginResult:
        # Claim the pending ticket and consume a backup code under one writer
        # lock. A control session is minted only after that claim commits.
        token_hash = hashlib.sha256(ticket_token.encode()).hexdigest()
        try:
            with self._store.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                ticket = connection.execute(
                    "SELECT * FROM api_sessions WHERE token_hash = ?", (token_hash,)
                ).fetchone()
                if (
                    ticket is None or bool(ticket["revoked"])
                    or str(ticket["scope"] or "") != "mfa_pending"
                    or (ticket["expires_at"] and _parse(str(ticket["expires_at"])) <= _now())
                    or (ticket["absolute_expires_at"] and _parse(str(ticket["absolute_expires_at"])) <= _now())
                ):
                    raise AuthError("MFA verification failed")
                principal_id = str(ticket["principal_id"])
                account = connection.execute(
                    "SELECT * FROM account_credentials WHERE principal_id = ?", (principal_id,)
                ).fetchone()
                principal = connection.execute(
                    "SELECT is_active FROM principals WHERE principal_id = ?", (principal_id,)
                ).fetchone()
                if account is None or principal is None or not bool(principal["is_active"]) or not bool(account["mfa_enrolled"]):
                    raise AuthError("MFA verification failed")
                # A live mfa_pending ticket must not absorb unlimited TOTP
                # guesses, so this code gate shares login's lockout counter — a
                # locked account is locked here too (matches login's is_locked).
                locked_until = account["locked_until"]
                if locked_until and _parse(str(locked_until)) > _now():
                    raise AuthError("MFA verification failed")
                verified = False
                updated_backup: str | None = None
                blob = account["mfa_secret_encrypted"]
                if blob is not None:
                    verified = mfa.verify_totp(mfa.decrypt_secret(self._workspace_root, blob), code)
                if not verified and account["backup_codes_hashed"]:
                    verified, updated = mfa.consume_backup_code(str(account["backup_codes_hashed"]), code)
                    if verified:
                        updated_backup = updated
                if not verified:
                    # Charge the shared counter and lock at the threshold, then
                    # commit so the cost survives the raise (the rollback the
                    # with-block would otherwise apply must not erase it).
                    attempts = int(account["failed_attempts"] or 0) + 1
                    lock_at = (
                        (_now() + timedelta(seconds=LOCKOUT_SECONDS)).isoformat(timespec="seconds")
                        if attempts >= LOCKOUT_THRESHOLD
                        else None
                    )
                    connection.execute(
                        "UPDATE account_credentials SET failed_attempts = ?, locked_until = ? "
                        "WHERE principal_id = ?",
                        (attempts, lock_at, principal_id),
                    )
                    connection.commit()
                    raise AuthError("MFA verification failed")
                # Success clears the counter; a spent backup code is consumed in
                # the same write.
                if updated_backup is not None:
                    connection.execute(
                        "UPDATE account_credentials SET backup_codes_hashed = ?, "
                        "failed_attempts = 0, locked_until = NULL WHERE principal_id = ?",
                        (updated_backup, principal_id),
                    )
                else:
                    connection.execute(
                        "UPDATE account_credentials SET failed_attempts = 0, "
                        "locked_until = NULL WHERE principal_id = ?",
                        (principal_id,),
                    )
                claimed = connection.execute(
                    "UPDATE api_sessions SET revoked = 1 WHERE session_id = ? AND revoked = 0",
                    (str(ticket["session_id"]),),
                )
                if claimed.rowcount != 1:
                    raise AuthError("MFA verification failed")
                connection.commit()
        except AuthError:
            raise
        except Exception as exc:
            raise AuthError("MFA verification failed") from exc
        token = self._issue_control_session(principal_id, None)
        return LoginResult(stage="session", principal_id=principal_id, token=token)

    # ── Password & elevation ────────────────────────────────────────────────
    def change_password(
        self, principal_id: str, old_password: str, new_password: str, keep_session_id: str = ""
    ) -> None:
        account = self._store.get_account(principal_id)
        if account is None or not passwords.verify_password(
            old_password, account["password_hash"], account["hash_algo"]
        ):
            raise AuthError(GENERIC_AUTH_ERROR)
        if not new_password:
            raise AuthError("New password is required")
        encoded, algo = passwords.hash_password(new_password)
        self._store.set_account_password(principal_id, encoded, algo, utc_now())
        self._sessions.revoke_others_for_principal(principal_id, keep_session_id)

    def begin_password_recovery(self, username: str) -> str:
        """Issue an opaque local recovery ticket without disclosing account existence."""
        account = self._store.get_account_by_username(username.strip())
        if account is None or not self._account_principal_is_active(account["principal_id"]):
            # The caller receives an indistinguishable opaque value, but no
            # server-side ticket exists to complete a reset for this username.
            return secrets.token_hex(32)
        token, _ = self._sessions.create_session(
            account["principal_id"],
            scope="password_recovery",
            expires_in_seconds=PASSWORD_RECOVERY_TICKET_TTL,
        )
        return token

    def complete_password_recovery(self, ticket_token: str, code: str, new_password: str) -> None:
        if not new_password:
            raise AuthError("Password recovery failed")
        token_hash = hashlib.sha256(ticket_token.encode()).hexdigest()
        # The ticket check, MFA/backup-code consume, password write, and session
        # revocation share one write transaction. A completed ticket can never be
        # replayed, even by concurrent requests.
        with self._store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            ticket = connection.execute(
                "SELECT * FROM api_sessions WHERE token_hash = ?", (token_hash,)
            ).fetchone()
            if (
                ticket is None
                or bool(ticket["revoked"])
                or str(ticket["scope"] or "") != "password_recovery"
                or (ticket["expires_at"] and _parse(str(ticket["expires_at"])) <= _now())
                or (ticket["absolute_expires_at"] and _parse(str(ticket["absolute_expires_at"])) <= _now())
            ):
                raise AuthError("Password recovery failed")
            principal_id = str(ticket["principal_id"])
            account = connection.execute(
                "SELECT * FROM account_credentials WHERE principal_id = ?", (principal_id,)
            ).fetchone()
            principal = connection.execute(
                "SELECT is_active FROM principals WHERE principal_id = ?", (principal_id,)
            ).fetchone()
            if account is None or principal is None or not bool(principal["is_active"]) or not bool(account["mfa_enrolled"]):
                raise AuthError("Password recovery failed")
            # This call resets the password, so its code gate needs the same
            # lockout `login` has. Without it one ticket absorbs unlimited
            # guesses against a 6-digit TOTP — and `valid_window=1` keeps three
            # codes live at once — which is a takeover primitive, not a
            # nuisance. The counter is shared with `login`, so a locked account
            # is locked for both.
            locked_until = account["locked_until"]
            if locked_until and _parse(str(locked_until)) > _now():
                raise AuthError("Password recovery failed")
            blob = account["mfa_secret_encrypted"]
            verified = False
            if blob is not None:
                verified = mfa.verify_totp(mfa.decrypt_secret(self._workspace_root, blob), code)
            if not verified and account["backup_codes_hashed"]:
                verified, updated = mfa.consume_backup_code(account["backup_codes_hashed"], code)
                if verified:
                    connection.execute(
                        "UPDATE account_credentials SET backup_codes_hashed = ? WHERE principal_id = ?",
                        (updated, principal_id),
                    )
            if not verified:
                # The counter has to outlive the raise, and raising inside the
                # transaction would roll it back — so commit it first. A failed
                # attempt must cost the attacker something even though nothing
                # else about this call is allowed to persist.
                attempts = int(account["failed_attempts"] or 0) + 1
                lock_at = (
                    (_now() + timedelta(seconds=LOCKOUT_SECONDS)).isoformat(timespec="seconds")
                    if attempts >= LOCKOUT_THRESHOLD
                    else None
                )
                connection.execute(
                    "UPDATE account_credentials SET failed_attempts = ?, locked_until = ? "
                    "WHERE principal_id = ?",
                    (attempts, lock_at, principal_id),
                )
                connection.execute("COMMIT")
                raise AuthError("Password recovery failed")
            encoded, algo = passwords.hash_password(new_password)
            connection.execute(
                "UPDATE account_credentials SET password_hash = ?, hash_algo = ?, updated_at = ?, "
                "failed_attempts = 0, locked_until = NULL WHERE principal_id = ?",
                (encoded, algo, utc_now(), principal_id),
            )
            connection.execute("UPDATE api_sessions SET revoked = 1 WHERE principal_id = ?", (principal_id,))

    def grant_elevated(
        self, principal_id: str, password: str | None = None, mfa_code: str | None = None
    ) -> str:
        account = self._store.get_account(principal_id)
        if account is None:
            raise AuthError(GENERIC_AUTH_ERROR)
        if not self._account_principal_is_active(principal_id):
            raise AuthError(GENERIC_AUTH_ERROR)
        password_ok = password is not None and passwords.verify_password(
            password, account["password_hash"], account["hash_algo"]
        )
        # Only reach `_check_mfa` when the password did not already satisfy the
        # gate — it now charges the lockout counter on a wrong code, so a valid
        # password paired with a stray/wrong code must not spuriously lock out.
        mfa_ok = (
            not password_ok
            and mfa_code is not None
            and bool(account["mfa_enrolled"])
            and self._check_mfa(account, mfa_code)
        )
        if not (password_ok or mfa_ok):
            raise AuthError(GENERIC_AUTH_ERROR)
        token, _ = self._sessions.create_session(
            principal_id, scope="elevated", expires_in_seconds=ELEVATED_TTL
        )
        return token

    # ── MFA enrollment ──────────────────────────────────────────────────────
    def begin_enroll_mfa(self, principal_id: str) -> tuple[str, str, list[str]]:
        account = self._store.get_account(principal_id)
        if account is None:
            raise AuthError("Account not found")
        secret = mfa.generate_secret()
        codes = mfa.generate_backup_codes()
        encrypted = mfa.encrypt_secret(self._workspace_root, secret)
        # Persist the (not-yet-active) secret; mfa_enrolled stays 0 until verified.
        self._store.set_account_mfa(principal_id, False, encrypted, mfa.hash_backup_codes(codes))
        uri = mfa.provisioning_uri(secret, account["username"])
        return secret, uri, codes

    def activate_mfa(self, principal_id: str, code: str, keep_session_id: str = "") -> None:
        with self._store.connect() as connection:
            account = connection.execute(
                "SELECT * FROM account_credentials WHERE principal_id = ?", (principal_id,)
            ).fetchone()
            if account is None or account["mfa_secret_encrypted"] is None:
                raise AuthError("MFA enrollment not started")
            secret = mfa.decrypt_secret(self._workspace_root, account["mfa_secret_encrypted"])
            if not mfa.verify_totp(secret, code):
                raise AuthError("Invalid verification code")
            connection.execute(
                "UPDATE account_credentials SET mfa_enrolled = 1, updated_at = ? WHERE principal_id = ?",
                (utc_now(), principal_id),
            )
            connection.execute(
                "UPDATE api_sessions SET revoked = 1 WHERE principal_id = ? AND session_id != ?",
                (principal_id, keep_session_id),
            )

    def mfa_enrolled(self, principal_id: str) -> bool:
        account = self._store.get_account(principal_id)
        return bool(account and account["mfa_enrolled"])

    def verify_mfa_code(self, principal_id: str, code: str) -> bool:
        account = self._store.get_account(principal_id)
        if account is None or not account["mfa_enrolled"]:
            return False
        return self._check_mfa(account, code)

    def disable_mfa(self, principal_id: str, keep_session_id: str = "") -> None:
        with self._store.connect() as connection:
            connection.execute(
                "UPDATE account_credentials SET mfa_enrolled = 0, mfa_secret_encrypted = NULL, "
                "backup_codes_hashed = NULL, updated_at = ? WHERE principal_id = ?",
                (utc_now(), principal_id),
            )
            connection.execute(
                "UPDATE api_sessions SET revoked = 1 WHERE principal_id = ? AND session_id != ?",
                (principal_id, keep_session_id),
            )

    # ── Internals ───────────────────────────────────────────────────────────
    def _account_principal_is_active(self, principal_id: str) -> bool:
        principal = self._store.get_principal(principal_id)
        return bool(principal and principal["is_active"])

    def _issue_control_session(self, principal_id: str, device_label: str | None) -> str:
        token, _ = self._sessions.create_session(
            principal_id,
            scope="control",
            expires_in_seconds=SESSION_TTL,
            absolute_expires_in_seconds=SESSION_ABSOLUTE_TTL,
            device_label=device_label,
        )
        return token

    def _is_locked(self, account: dict) -> bool:
        locked_until = account.get("locked_until")
        if not locked_until:
            return False
        return _parse(locked_until) > _now()

    def _register_failure(self, account: dict) -> None:
        attempts = int(account.get("failed_attempts", 0)) + 1
        locked_until = None
        if attempts >= LOCKOUT_THRESHOLD:
            locked_until = (_now() + timedelta(seconds=LOCKOUT_SECONDS)).isoformat(timespec="seconds")
        self._store.set_account_failed(account["principal_id"], attempts, locked_until)

    def _reset_failures(self, principal_id: str) -> None:
        self._store.set_account_failed(principal_id, 0, None)

    def _maybe_rehash(self, account: dict, password: str) -> None:
        if passwords.needs_rehash(account["password_hash"], account["hash_algo"]):
            encoded, algo = passwords.hash_password(password)
            self._store.set_account_password(account["principal_id"], encoded, algo, utc_now())

    def _check_mfa(self, account: dict, code: str) -> bool:
        # Verifying a second factor resets a password, elevates, or completes
        # login, so it needs the same lockout `login` enforces — otherwise a
        # ticket/session absorbs unlimited guesses against a 6-digit TOTP (with
        # valid_window=1 keeping three codes live), which is an account-takeover
        # primitive, not a nuisance. Everything runs under one writer lock so the
        # counter, the TOTP check, and the single-use backup-code consume are
        # atomic: `account` is a stale snapshot, so concurrent callers must not
        # all consume from it (each would be granted and the last write would
        # restore a spent code). This is the shared path `grant_elevated` and
        # `verify_mfa_code` reach; `verify_mfa` claims its ticket the same way.
        principal_id = str(account["principal_id"])
        with self._store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT failed_attempts, locked_until, mfa_secret_encrypted, "
                    "backup_codes_hashed FROM account_credentials WHERE principal_id = ?",
                    (principal_id,),
                ).fetchone()
                if row is None:
                    connection.execute("ROLLBACK")
                    return False
                locked_until = row["locked_until"]
                if locked_until and _parse(str(locked_until)) > _now():
                    connection.execute("ROLLBACK")
                    return False
                verified = False
                updated_backup: str | None = None
                blob = row["mfa_secret_encrypted"]
                if blob is not None and mfa.verify_totp(
                    mfa.decrypt_secret(self._workspace_root, blob), code
                ):
                    verified = True
                if not verified and row["backup_codes_hashed"]:
                    ok, updated = mfa.consume_backup_code(str(row["backup_codes_hashed"]), code)
                    if ok:
                        verified = True
                        updated_backup = updated
                if verified:
                    if updated_backup is not None:
                        connection.execute(
                            "UPDATE account_credentials SET backup_codes_hashed = ?, "
                            "failed_attempts = 0, locked_until = NULL WHERE principal_id = ?",
                            (updated_backup, principal_id),
                        )
                    else:
                        connection.execute(
                            "UPDATE account_credentials SET failed_attempts = 0, "
                            "locked_until = NULL WHERE principal_id = ?",
                            (principal_id,),
                        )
                    connection.commit()
                    return True
                # Wrong code: charge the shared counter and lock at the
                # threshold, exactly as `login` and `complete_password_recovery`
                # do, then commit so the cost outlives this failed call.
                attempts = int(row["failed_attempts"] or 0) + 1
                lock_at = (
                    (_now() + timedelta(seconds=LOCKOUT_SECONDS)).isoformat(timespec="seconds")
                    if attempts >= LOCKOUT_THRESHOLD
                    else None
                )
                connection.execute(
                    "UPDATE account_credentials SET failed_attempts = ?, locked_until = ? "
                    "WHERE principal_id = ?",
                    (attempts, lock_at, principal_id),
                )
                connection.commit()
                return False
            except Exception:
                connection.execute("ROLLBACK")
                raise
