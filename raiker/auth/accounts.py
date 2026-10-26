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
from typing import Literal

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
# BUG-358 — a session from another device is shorter-lived: idle for twelve
# hours or seven days old, it signs in again with the password and a code.
REMOTE_SESSION_IDLE_TTL = 3600 * 12
REMOTE_SESSION_ABSOLUTE_TTL = 86400 * 7
ELEVATED_TTL = 300  # 5 minutes
GENERIC_AUTH_ERROR = "Invalid username or password"


class AuthError(Exception):
    """Raised for any authentication failure. Message is safe to surface."""


Origin = Literal["local", "remote"]


@dataclass(frozen=True)
class LoginResult:
    stage: Literal["session", "mfa_required"]
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
    def login(
        self,
        username: str,
        password: str,
        device_label: str | None = None,
        *,
        origin: Origin = "local",
        client_hint: str | None = None,
    ) -> LoginResult:
        """Password first; then MFA when enrolled, and always from another device.

        BUG-358 — a password alone never opens a session for a remote request:
        an account without MFA gets the generic failure there, after the same
        password work, so the answer does not say which half was missing.
        """
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
        if origin == "remote" and not account["mfa_enrolled"]:
            raise AuthError(GENERIC_AUTH_ERROR)
        # With MFA on, the password is only half the sign-in, so it must not
        # clear the failure counter: otherwise signing in again between wrong
        # codes reset it every time and a known password bought unlimited code
        # guesses (found while building BUG-358). Only a verified code clears it.
        if not account["mfa_enrolled"]:
            self._reset_failures(account["principal_id"])
        self._maybe_rehash(account, password)
        if account["mfa_enrolled"]:
            ticket, _ = self._sessions.create_session(
                account["principal_id"],
                scope="mfa_pending",
                expires_in_seconds=MFA_TICKET_TTL,
                device_label=device_label,
                origin=origin,
                client_hint=client_hint,
            )
            return LoginResult(stage="mfa_required", principal_id=account["principal_id"], ticket=ticket)
        token = self._issue_control_session(
            account["principal_id"], device_label, origin=origin, client_hint=client_hint
        )
        return LoginResult(stage="session", principal_id=account["principal_id"], token=token)

    def verify_mfa(self, ticket_token: str, code: str, *, origin: Origin = "local") -> LoginResult:
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
                epoch = int(account["mfa_epoch"] or 0)
                client_hint = ticket["client_hint"]
                device_label = ticket["device_label"]
        except AuthError:
            raise
        except Exception as exc:
            raise AuthError("MFA verification failed") from exc
        # The session is where the code was entered: a ticket started on one
        # listener and finished on another takes the second one's origin.
        token = self._issue_control_session(
            principal_id,
            device_label,
            origin=origin,
            assurance="mfa",
            mfa_epoch=epoch,
            client_hint=client_hint,
        )
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
        self,
        principal_id: str,
        password: str | None = None,
        mfa_code: str | None = None,
        *,
        origin: Origin = "local",
    ) -> str:
        """A five-minute session for one sensitive action, after fresh proof.

        On this computer the password, or a code, is enough. From another
        device (BUG-358) both are required. The elevated session records which
        was given: an action that needs fresh MFA (turning MFA off or resetting
        it, changing remote access) refuses one granted on the password alone.
        """
        account = self._store.get_account(principal_id)
        if account is None:
            raise AuthError(GENERIC_AUTH_ERROR)
        if not self._account_principal_is_active(principal_id):
            raise AuthError(GENERIC_AUTH_ERROR)
        password_ok = password is not None and passwords.verify_password(
            password, account["password_hash"], account["hash_algo"]
        )
        # A code is checked only when one was given: `_check_mfa` charges the
        # lockout counter on a wrong code, so a stray empty field must not.
        mfa_ok = (
            bool(mfa_code)
            and bool(account["mfa_enrolled"])
            and self._check_mfa(account, str(mfa_code))
        )
        granted = (password_ok and mfa_ok) if origin == "remote" else (password_ok or mfa_ok)
        if not granted:
            raise AuthError(GENERIC_AUTH_ERROR)
        token, _ = self._sessions.create_session(
            principal_id,
            scope="elevated",
            expires_in_seconds=ELEVATED_TTL,
            assurance="mfa" if mfa_ok else "password",
            origin=origin,
            mfa_epoch=int(account.get("mfa_epoch") or 0) if mfa_ok else None,
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
        if account["mfa_enrolled"]:
            # BUG-358 — a reset is staged beside the active enrolment, which
            # keeps working (and keeps remote access up) until the new
            # authenticator's first code is confirmed in `activate_mfa`.
            with self._store.connect() as connection:
                connection.execute(
                    "UPDATE account_credentials SET mfa_pending_secret_encrypted = ?, "
                    "mfa_pending_backup_codes = ?, updated_at = ? WHERE principal_id = ?",
                    (encrypted, mfa.hash_backup_codes(codes), utc_now(), principal_id),
                )
        else:
            # Persist the (not-yet-active) secret; mfa_enrolled stays 0 until verified.
            self._store.set_account_mfa(principal_id, False, encrypted, mfa.hash_backup_codes(codes))
        uri = mfa.provisioning_uri(secret, account["username"])
        return secret, uri, codes

    def activate_mfa(self, principal_id: str, code: str, keep_session_id: str = "") -> None:
        with self._store.connect() as connection:
            account = connection.execute(
                "SELECT * FROM account_credentials WHERE principal_id = ?", (principal_id,)
            ).fetchone()
            if account is None:
                raise AuthError("MFA enrollment not started")
            staged = account["mfa_pending_secret_encrypted"]
            blob = staged if staged is not None else account["mfa_secret_encrypted"]
            if blob is None or (staged is None and account["mfa_enrolled"]):
                raise AuthError("MFA enrollment not started")
            secret = mfa.decrypt_secret(self._workspace_root, blob)
            if not mfa.verify_totp(secret, code):
                raise AuthError("Invalid verification code")
            epoch = int(account["mfa_epoch"] or 0) + 1
            if staged is not None:
                # The reset's new authenticator replaces the old one, codes and all.
                connection.execute(
                    "UPDATE account_credentials SET mfa_enrolled = 1, mfa_epoch = ?, "
                    "mfa_secret_encrypted = mfa_pending_secret_encrypted, "
                    "backup_codes_hashed = mfa_pending_backup_codes, "
                    "mfa_pending_secret_encrypted = NULL, mfa_pending_backup_codes = NULL, "
                    "updated_at = ? WHERE principal_id = ?",
                    (epoch, utc_now(), principal_id),
                )
            else:
                connection.execute(
                    "UPDATE account_credentials SET mfa_enrolled = 1, mfa_epoch = ?, updated_at = ? "
                    "WHERE principal_id = ?",
                    (epoch, utc_now(), principal_id),
                )
            connection.execute(
                "UPDATE api_sessions SET revoked = 1 WHERE principal_id = ? AND session_id != ?",
                (principal_id, keep_session_id),
            )
            # The session that just entered a valid code is verified by it.
            if keep_session_id:
                connection.execute(
                    "UPDATE api_sessions SET assurance = 'mfa', mfa_epoch = ? WHERE session_id = ?",
                    (epoch, keep_session_id),
                )

    def mfa_epoch(self, principal_id: str) -> int:
        account = self._store.get_account(principal_id)
        return int(account.get("mfa_epoch") or 0) if account else 0

    def mfa_reset_pending(self, principal_id: str) -> bool:
        account = self._store.get_account(principal_id)
        return bool(account and account.get("mfa_pending_secret_encrypted") is not None)

    def mfa_enrolled(self, principal_id: str) -> bool:
        account = self._store.get_account(principal_id)
        return bool(account and account["mfa_enrolled"])

    def verify_mfa_code(self, principal_id: str, code: str) -> bool:
        account = self._store.get_account(principal_id)
        if account is None or not account["mfa_enrolled"]:
            return False
        return self._check_mfa(account, code)

    def disable_mfa(
        self, principal_id: str, keep_session_id: str = "", also_keep: str = ""
    ) -> None:
        """Turn MFA off and sign out every session but the one(s) doing it."""
        with self._store.connect() as connection:
            connection.execute(
                "UPDATE account_credentials SET mfa_enrolled = 0, mfa_secret_encrypted = NULL, "
                "backup_codes_hashed = NULL, mfa_pending_secret_encrypted = NULL, "
                "mfa_pending_backup_codes = NULL, mfa_epoch = mfa_epoch + 1, updated_at = ? "
                "WHERE principal_id = ?",
                (utc_now(), principal_id),
            )
            connection.execute(
                "UPDATE api_sessions SET revoked = 1 WHERE principal_id = ? "
                "AND session_id NOT IN (?, ?)",
                (principal_id, keep_session_id, also_keep or keep_session_id),
            )

    # ── Internals ───────────────────────────────────────────────────────────
    def _account_principal_is_active(self, principal_id: str) -> bool:
        principal = self._store.get_principal(principal_id)
        return bool(principal and principal["is_active"])

    def _issue_control_session(
        self,
        principal_id: str,
        device_label: str | None,
        *,
        origin: Origin = "local",
        assurance: str = "password",
        mfa_epoch: int | None = None,
        client_hint: str | None = None,
    ) -> str:
        remote = origin == "remote"
        token, _ = self._sessions.create_session(
            principal_id,
            scope="control",
            expires_in_seconds=REMOTE_SESSION_IDLE_TTL if remote else SESSION_TTL,
            absolute_expires_in_seconds=REMOTE_SESSION_ABSOLUTE_TTL if remote else SESSION_ABSOLUTE_TTL,
            device_label=device_label,
            assurance=assurance,
            origin=origin,
            mfa_epoch=mfa_epoch,
            client_hint=client_hint,
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
