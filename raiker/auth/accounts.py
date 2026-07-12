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

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.api.sessions import ApiSessionStore
from raiker.auth import mfa, passwords
from raiker.cli.principal_resolver import (
    ADMIN_ROLE_ID,
    APPROVER_ROLE_ID,
    OWNER_BOOTSTRAP_ROLES,
    OWNER_ROLE_ID,
    _ensure_bootstrap_roles,
)
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import User, UserRoleAssignment
from raiker.storage.sqlite import SQLiteStore

# Additional accounts (after the first/owner) get self-contained authority over
# their own isolated data, but not owner/gate-manager, so a single gate manager
# governs the device.
_ADDITIONAL_ACCOUNT_ROLES = (ADMIN_ROLE_ID, APPROVER_ROLE_ID)

LOCKOUT_THRESHOLD = 5
LOCKOUT_SECONDS = 900  # 15 minutes
MFA_TICKET_TTL = 300  # 5 minutes
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
        self._store = SQLiteStore(workspace_root)
        self._sessions = ApiSessionStore(workspace_root)

    # ── Registration ────────────────────────────────────────────────────────
    def register(self, username: str, password: str) -> str:
        username = username.strip()
        if not username or not password:
            raise AuthError("Username and password are required")
        if self._store.get_account_by_username(username) is not None:
            raise AuthError("Username is already taken")
        _ensure_bootstrap_roles(self._store)
        now = utc_now()
        user_id = f"user_{secrets.token_hex(8)}"
        principal_id = f"principal_{user_id}"
        roles = OWNER_BOOTSTRAP_ROLES if not self._owner_exists() else _ADDITIONAL_ACCOUNT_ROLES
        self._store.insert_user(
            User(
                user_id=user_id,
                display_name=username,
                email=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        self._store.insert_principal(
            principal_id=principal_id,
            principal_type="human",
            display_name=username,
            delegated_by_user_id=user_id,
            role_ids=roles,
            max_runtime_mode="multi_user_local_runtime",
            is_active=True,
        )
        for role_id in roles:
            self._store.insert_user_role_assignment(
                UserRoleAssignment(
                    assignment_id=new_id("ura_"),
                    user_id=user_id,
                    role_id=role_id,
                    granted_at=now,
                    granted_by="lock_screen_registration",
                )
            )
        encoded, algo = passwords.hash_password(password)
        self._store.upsert_account(principal_id, username, encoded, algo, now, now)
        return principal_id

    def _owner_exists(self) -> bool:
        for principal in self._store.list_principals(active_only=False):
            if OWNER_ROLE_ID in principal.get("role_ids", ()):
                return True
        return False

    # ── Login state machine ─────────────────────────────────────────────────
    def login(self, username: str, password: str, device_label: str | None = None) -> LoginResult:
        account = self._store.get_account_by_username(username.strip())
        if account is None:
            # Spend comparable work so a missing user is indistinguishable by timing.
            passwords.spend_dummy_verify(password)
            raise AuthError(GENERIC_AUTH_ERROR)
        if self._is_locked(account):
            raise AuthError(GENERIC_AUTH_ERROR)
        if not passwords.verify_password(password, account["password_hash"], account["hash_algo"]):
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
        ticket = self._sessions.get_by_token(ticket_token)
        if ticket is None or ticket.revoked or ticket.is_expired() or ticket.scope != "mfa_pending":
            raise AuthError("MFA verification failed")
        account = self._store.get_account(ticket.principal_id)
        if account is None or not account["mfa_enrolled"]:
            raise AuthError("MFA verification failed")
        if not self._check_mfa(account, code):
            raise AuthError("MFA verification failed")
        self._sessions.revoke_session(ticket.session_id)
        token = self._issue_control_session(ticket.principal_id, None)
        return LoginResult(stage="session", principal_id=ticket.principal_id, token=token)

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

    def grant_elevated(
        self, principal_id: str, password: str | None = None, mfa_code: str | None = None
    ) -> str:
        account = self._store.get_account(principal_id)
        if account is None:
            raise AuthError(GENERIC_AUTH_ERROR)
        password_ok = password is not None and passwords.verify_password(
            password, account["password_hash"], account["hash_algo"]
        )
        mfa_ok = mfa_code is not None and account["mfa_enrolled"] and self._check_mfa(account, mfa_code)
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

    def activate_mfa(self, principal_id: str, code: str) -> None:
        account = self._store.get_account(principal_id)
        if account is None or account["mfa_secret_encrypted"] is None:
            raise AuthError("MFA enrollment not started")
        secret = mfa.decrypt_secret(self._workspace_root, account["mfa_secret_encrypted"])
        if not mfa.verify_totp(secret, code):
            raise AuthError("Invalid verification code")
        self._store.set_account_mfa(
            principal_id, True, account["mfa_secret_encrypted"], account["backup_codes_hashed"]
        )

    def disable_mfa(self, principal_id: str, keep_session_id: str = "") -> None:
        self._store.set_account_mfa(principal_id, False, None, None)
        self._sessions.revoke_others_for_principal(principal_id, keep_session_id)

    # ── Internals ───────────────────────────────────────────────────────────
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
        blob = account.get("mfa_secret_encrypted")
        if blob is not None:
            secret = mfa.decrypt_secret(self._workspace_root, blob)
            if mfa.verify_totp(secret, code):
                return True
        hashed = account.get("backup_codes_hashed")
        if hashed:
            ok, updated = mfa.consume_backup_code(hashed, code)
            if ok:
                self._store.set_account_mfa(account["principal_id"], True, blob, updated)
                return True
        return False
