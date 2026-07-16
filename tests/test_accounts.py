from __future__ import annotations

import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pyotp
import pytest

import raiker.auth.passwords as passwords
from raiker.api.sessions import ApiSessionStore
from raiker.auth.accounts import (
    GENERIC_AUTH_ERROR,
    LOCKOUT_THRESHOLD,
    AccountService,
    AuthError,
)
from raiker.cli.principal_resolver import (
    ADMIN_ROLE_ID,
    APPROVER_ROLE_ID,
    OWNER_ROLE_ID,
    RUNTIME_GATE_MANAGER_ROLE_ID,
)
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import User, UserRoleAssignment
from raiker.control.dashboard import DashboardService
from raiker.control.service import RuntimeControlService
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.models.policy_state import provider_runtime_policy_from_gates
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID, ModelSessionState
from raiker.runtime.retrieval import RetrievalAugmentor
from raiker.storage.sqlite import SQLiteStore

_LEGACY_ACCOUNT_ROLE_MIGRATION_ID = "RAIKER-2021-legacy-account-bootstrap-roles"
_ACCOUNT_BOOTSTRAP_ROLES = (ADMIN_ROLE_ID, APPROVER_ROLE_ID, RUNTIME_GATE_MANAGER_ROLE_ID)


def _svc(tmp_path) -> AccountService:  # type: ignore[no-untyped-def]
    return AccountService(tmp_path)


def _seed_legacy_account(svc: AccountService, username: str, password: str) -> str:
    """Create a pre-single-instance account fixture without using registration."""
    now = utc_now()
    user_id = f"user_legacy_{secrets.token_hex(8)}"
    principal_id = f"principal_{user_id}"
    svc._store.insert_user(User(user_id, username, None, True, now, now))
    svc._store.insert_principal(
        principal_id=principal_id,
        principal_type="human",
        display_name=username,
        delegated_by_user_id=user_id,
        role_ids=_ACCOUNT_BOOTSTRAP_ROLES,
        max_runtime_mode="multi_user_local_runtime",
        is_active=True,
    )
    for role_id in _ACCOUNT_BOOTSTRAP_ROLES:
        svc._store.insert_user_role_assignment(
            UserRoleAssignment(new_id("ura_"), user_id, role_id, now, "legacy_fixture")
        )
    encoded, algo = passwords.hash_password(password)
    svc._store.upsert_account(principal_id, username, encoded, algo, now, now)
    return principal_id


def _remove_account_bootstrap_roles(svc: AccountService, principal_id: str) -> str:
    principal = svc._store.get_principal(principal_id)
    assert principal is not None
    user_id = principal["delegated_by_user_id"]
    assert user_id is not None
    with svc._store.connect() as connection:
        connection.execute(
            "UPDATE principals SET role_ids = ? WHERE principal_id = ?",
            (json.dumps([]), principal_id),
        )
        connection.execute(
            "DELETE FROM user_role_assignments WHERE user_id = ? AND role_id IN (?, ?, ?)",
            (user_id, *_ACCOUNT_BOOTSTRAP_ROLES),
        )
    return user_id


def _role_assignment_count(svc: AccountService, user_id: str, role_id: str) -> int:
    with svc._store.connect() as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM user_role_assignments WHERE user_id = ? AND role_id = ?",
                (user_id, role_id),
            ).fetchone()[0]
        )


def _rerun_legacy_account_role_migration(svc: AccountService) -> None:
    with svc._store.connect() as connection:
        connection.execute(
            "DELETE FROM migrations WHERE migration_id = ?", (_LEGACY_ACCOUNT_ROLE_MIGRATION_ID,)
        )
    SQLiteStore(svc._workspace_root)


def test_register_and_login_no_mfa(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    pid = svc.register("alice", "correct horse battery")
    assert pid
    result = svc.login("alice", "correct horse battery")
    assert result.stage == "session"
    assert result.token
    assert result.principal_id == pid


def test_wrong_password_generic_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    svc.register("alice", "right-pass")
    with pytest.raises(AuthError) as exc:
        svc.login("alice", "wrong-pass")
    assert str(exc.value) == GENERIC_AUTH_ERROR


def test_unknown_user_same_generic_error(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    with pytest.raises(AuthError) as exc:
        svc.login("ghost", "whatever")
    assert str(exc.value) == GENERIC_AUTH_ERROR


def test_lockout_after_five(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    svc.register("alice", "right-pass")
    for _ in range(5):
        with pytest.raises(AuthError):
            svc.login("alice", "bad")
    # even with the correct password, the account is now locked
    with pytest.raises(AuthError):
        svc.login("alice", "right-pass")


def test_mfa_gate(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    pid = svc.register("alice", "right-pass")
    secret, _uri, _codes = svc.begin_enroll_mfa(pid)
    svc.activate_mfa(pid, pyotp.TOTP(secret).now())
    result = svc.login("alice", "right-pass")
    assert result.stage == "mfa_required"
    assert result.ticket and result.token is None
    verified = svc.verify_mfa(result.ticket, pyotp.TOTP(secret).now())
    assert verified.stage == "session"
    assert verified.token


def test_mfa_ticket_is_claimed_once_under_concurrent_verification(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    principal_id = svc.register("alice", "right-pass")
    secret, _uri, _codes = svc.begin_enroll_mfa(principal_id)
    svc.activate_mfa(principal_id, pyotp.TOTP(secret).now())
    ticket = svc.login("alice", "right-pass").ticket
    assert ticket is not None
    barrier = Barrier(2)

    def verify() -> str:
        barrier.wait()
        try:
            svc.verify_mfa(ticket, pyotp.TOTP(secret).now())
            return "success"
        except AuthError:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: verify(), range(2)))
    assert sorted(results) == ["denied", "success"]


def test_mfa_backup_code_is_consumed_once_across_concurrent_tickets(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    principal_id = svc.register("alice", "right-pass")
    secret, _uri, codes = svc.begin_enroll_mfa(principal_id)
    svc.activate_mfa(principal_id, pyotp.TOTP(secret).now())
    first_ticket = svc.login("alice", "right-pass").ticket
    second_ticket = svc.login("alice", "right-pass").ticket
    assert first_ticket is not None and second_ticket is not None
    barrier = Barrier(2)

    def verify(ticket: str) -> str:
        barrier.wait()
        try:
            svc.verify_mfa(ticket, codes[0])
            return "success"
        except AuthError:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(verify, (first_ticket, second_ticket)))
    assert sorted(results) == ["denied", "success"]


def test_backup_code_is_consumed_once_across_concurrent_elevations(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A single-use backup code must survive `grant_elevated` racing itself.

    `verify_mfa` claims its code inside a transaction, but `_check_mfa` — the
    path `grant_elevated` and `verify_mfa_code` use — reads the code list,
    consumes, and writes with no transaction at all. Concurrent callers all read
    the same list and the last write wins, so every racer is granted elevation
    from one code, and a code consumed by one thread is restored by another's
    stale write and can be replayed.
    """
    svc = _svc(tmp_path)
    principal_id = svc.register("alice", "right-pass")
    secret, _uri, codes = svc.begin_enroll_mfa(principal_id)
    svc.activate_mfa(principal_id, pyotp.TOTP(secret).now())
    workers = 8
    barrier = Barrier(workers)

    def elevate() -> str:
        barrier.wait()
        try:
            svc.grant_elevated(principal_id, mfa_code=codes[0])
            return "success"
        except AuthError:
            return "denied"

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(lambda _item: elevate(), range(workers)))
    assert results.count("success") == 1, f"single-use code granted {results.count('success')} elevations"
    # The consumed code must stay consumed — a stale write must not restore it.
    with pytest.raises(AuthError):
        svc.grant_elevated(principal_id, mfa_code=codes[0])


def test_change_password_revokes_others(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    pid = svc.register("alice", "old-pass")
    sessions = ApiSessionStore(tmp_path)
    stale_tok, _ = sessions.create_session(pid, scope="control")
    svc.change_password(pid, "old-pass", "new-pass")
    stale_session = sessions.get_by_token(stale_tok)
    assert stale_session is not None and stale_session.revoked is True
    # old password no longer works
    with pytest.raises(AuthError):
        svc.login("alice", "old-pass")
    assert svc.login("alice", "new-pass").stage == "session"


def test_inactive_account_cannot_grant_elevated_session(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    principal_id = svc.register("inactive", "inactive-pass")
    svc._store.deactivate_principal(principal_id)

    with pytest.raises(AuthError):
        svc.grant_elevated(principal_id, password="inactive-pass")

    with svc._store.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM api_sessions WHERE principal_id = ? AND scope = 'elevated'",
            (principal_id,),
        ).fetchone()[0]
    assert count == 0


def test_second_account_registration_is_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    svc.register("alice", "pa")
    with pytest.raises(AuthError):
        svc.register("bob", "pb")


def test_bootstrap_backfills_all_account_roles_only_for_active_credential_backed_legacy_humans(
    tmp_path: Path,
) -> None:
    svc = _svc(tmp_path)
    svc.register("owner", "owner-pass")
    legacy_principal_id = _seed_legacy_account(svc, "legacy", "legacy-pass")
    inactive_principal_id = _seed_legacy_account(svc, "inactive", "inactive-pass")
    svc._store.insert_principal(
        principal_id="principal_ai",
        principal_type="ai_agent",
        display_name="AI",
        role_ids=(),
    )
    svc._store.insert_principal(
        principal_id="principal_non_account",
        principal_type="human",
        display_name="Non-account human",
        role_ids=(),
    )
    legacy_user_id = _remove_account_bootstrap_roles(svc, legacy_principal_id)
    _remove_account_bootstrap_roles(svc, inactive_principal_id)
    svc._store.deactivate_principal(inactive_principal_id)
    with svc._store.connect() as connection:
        connection.execute("DROP INDEX IF EXISTS idx_user_role_assignments_user_role")
        for role_id in _ACCOUNT_BOOTSTRAP_ROLES:
            for suffix in ("one", "two"):
                connection.execute(
                    "INSERT INTO user_role_assignments "
                    "(assignment_id, user_id, role_id, granted_at, granted_by) VALUES (?, ?, ?, ?, ?)",
                    (f"ura_duplicate_{role_id}_{suffix}", legacy_user_id, role_id, utc_now(), "legacy"),
                )

    _rerun_legacy_account_role_migration(svc)

    legacy_principal = svc._store.get_principal(legacy_principal_id)
    inactive_account_principal = svc._store.get_principal(inactive_principal_id)
    ai_principal = svc._store.get_principal("principal_ai")
    non_account_principal = svc._store.get_principal("principal_non_account")
    assert legacy_principal is not None
    assert inactive_account_principal is not None
    assert ai_principal is not None
    assert non_account_principal is not None
    for role_id in _ACCOUNT_BOOTSTRAP_ROLES:
        assert legacy_principal["role_ids"].count(role_id) == 1
        assert _role_assignment_count(svc, legacy_user_id, role_id) == 1
        assert role_id not in inactive_account_principal["role_ids"]
        assert role_id not in ai_principal["role_ids"]
        assert role_id not in non_account_principal["role_ids"]


def test_bootstrap_does_not_backfill_an_active_account_with_an_inactive_user(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    svc.register("owner", "owner-pass")
    principal_id = _seed_legacy_account(svc, "inactive-user", "inactive-user-pass")
    user_id = _remove_account_bootstrap_roles(svc, principal_id)
    with svc._store.connect() as connection:
        connection.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
        connection.execute(
            "DELETE FROM migrations WHERE migration_id = ?", (_LEGACY_ACCOUNT_ROLE_MIGRATION_ID,)
        )

    SQLiteStore(tmp_path)

    principal = svc._store.get_principal(principal_id)
    assert principal is not None
    assert principal["is_active"] is True
    for role_id in _ACCOUNT_BOOTSTRAP_ROLES:
        assert role_id not in principal["role_ids"]
        assert _role_assignment_count(svc, user_id, role_id) == 0


def test_legacy_role_backfill_is_idempotent_across_concurrent_and_sequential_bootstrap(
    tmp_path: Path,
) -> None:
    svc = _svc(tmp_path)
    svc.register("owner", "owner-pass")
    legacy_principal_id = _seed_legacy_account(svc, "legacy", "legacy-pass")
    legacy_user_id = _remove_account_bootstrap_roles(svc, legacy_principal_id)
    with svc._store.connect() as connection:
        connection.execute(
            "DELETE FROM migrations WHERE migration_id = ?", (_LEGACY_ACCOUNT_ROLE_MIGRATION_ID,)
        )

    barrier = Barrier(4)

    def bootstrap() -> None:
        barrier.wait()
        SQLiteStore(tmp_path)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(bootstrap) for _ in range(4)]
        for future in futures:
            future.result()
    SQLiteStore(tmp_path)

    principal = svc._store.get_principal(legacy_principal_id)
    assert principal is not None
    with svc._store.connect() as connection:
        marker_count = connection.execute(
            "SELECT COUNT(*) FROM migrations WHERE migration_id = ?",
            (_LEGACY_ACCOUNT_ROLE_MIGRATION_ID,),
        ).fetchone()[0]
    assert marker_count == 1
    for role_id in _ACCOUNT_BOOTSTRAP_ROLES:
        assert principal["role_ids"].count(role_id) == 1
        assert _role_assignment_count(svc, legacy_user_id, role_id) == 1


@pytest.mark.skipif(not passwords.ARGON2_AVAILABLE, reason="mixed hash algorithms require Argon2")
@pytest.mark.parametrize(
    ("stored_algo", "expected_algorithms"),
    (("scrypt", ("scrypt", "argon2id")), ("argon2id", ("argon2id", "scrypt"))),
)
def test_failed_login_verifies_stored_hash_and_only_other_dummy_algorithms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stored_algo: str,
    expected_algorithms: tuple[str, str],
) -> None:
    svc = _svc(tmp_path)
    principal_id = svc.register("account", "account-pass")
    svc._store.set_account_password(principal_id, "stored-hash", stored_algo, utc_now())
    verify_calls: list[str] = []

    def verify_password(_password: str, _encoded: str, algo: str) -> bool:
        verify_calls.append(algo)
        return False

    monkeypatch.setattr("raiker.auth.accounts.passwords.verify_password", verify_password)
    monkeypatch.setattr(
        "raiker.auth.accounts.passwords._DUMMY_HASHES",
        {"scrypt": "scrypt-dummy", "argon2id": "argon2id-dummy"},
    )

    with pytest.raises(AuthError):
        svc.login("account", "wrong-pass")

    assert tuple(verify_calls) == expected_algorithms
    with svc._store.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM api_sessions WHERE principal_id = ?", (principal_id,)
        ).fetchone()[0]
    assert count == 0


@pytest.mark.skipif(not passwords.ARGON2_AVAILABLE, reason="mixed hash algorithms require Argon2")
def test_failed_login_uses_scrypt_fallback_for_malformed_metadata_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path)
    principal_id = svc.register("account", "account-pass")
    svc._store.set_account_password(
        principal_id, "scrypt$legacy-encoded-hash", "unknown", utc_now()
    )
    verify_calls: list[str] = []

    def verify_password(_password: str, encoded: str, algo: str) -> bool:
        verify_calls.append("scrypt" if encoded.startswith("scrypt$") else algo)
        return False

    monkeypatch.setattr("raiker.auth.accounts.passwords.verify_password", verify_password)
    monkeypatch.setattr(
        "raiker.auth.accounts.passwords._DUMMY_HASHES",
        {"scrypt": "scrypt-dummy", "argon2id": "argon2id-dummy"},
    )

    with pytest.raises(AuthError):
        svc.login("account", "wrong-pass")

    assert verify_calls == ["scrypt", "argon2id"]
    with svc._store.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM api_sessions WHERE principal_id = ?", (principal_id,)
        ).fetchone()[0]
    assert count == 0


def test_account_service_prepares_dummy_hashes_outside_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[None] = []

    def prepare_dummy_hashes() -> None:
        calls.append(None)

    monkeypatch.setattr("raiker.auth.accounts.passwords.prepare_dummy_hashes", prepare_dummy_hashes)

    _svc(tmp_path)

    assert calls == [None]


def test_intentional_role_removal_after_migration_is_not_repaired_by_login(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    svc.register("owner", "owner-pass")
    legacy_principal_id = _seed_legacy_account(svc, "legacy", "legacy-pass")
    _remove_account_bootstrap_roles(svc, legacy_principal_id)

    result = svc.login("legacy", "legacy-pass")

    assert result.stage == "session"
    principal = svc._store.get_principal(legacy_principal_id)
    assert principal is not None
    for role_id in _ACCOUNT_BOOTSTRAP_ROLES:
        assert role_id not in principal["role_ids"]


def test_inactive_account_principal_cannot_login_or_complete_mfa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path)
    svc.register("owner", "owner-pass")
    principal_id = _seed_legacy_account(svc, "inactive", "inactive-pass")
    svc._store.set_account_mfa(principal_id, True, None, None)
    ticket, _ = svc._sessions.create_session(principal_id, scope="mfa_pending")
    svc._store.deactivate_principal(principal_id)
    monkeypatch.setattr(svc, "_check_mfa", lambda _account, _code: True)

    with pytest.raises(AuthError):
        svc.login("inactive", "inactive-pass")
    with pytest.raises(AuthError):
        svc.verify_mfa(ticket, "valid-code")


def test_inactive_account_cannot_receive_mfa_pending_session(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    principal_id = svc.register("inactive", "inactive-pass")
    svc._store.set_account_mfa(principal_id, True, None, None)
    svc._store.deactivate_principal(principal_id)

    with pytest.raises(AuthError):
        svc.login("inactive", "inactive-pass")

    with svc._store.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM api_sessions WHERE principal_id = ?", (principal_id,)
        ).fetchone()[0]
    assert count == 0


def test_inactive_account_login_verifies_password_without_issuing_a_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _svc(tmp_path)
    principal_id = svc.register("inactive", "inactive-pass")
    svc._store.deactivate_principal(principal_id)
    verify_calls: list[tuple[str, str, str]] = []

    def verify_password(password: str, password_hash: str, hash_algo: str) -> bool:
        verify_calls.append((password, password_hash, hash_algo))
        return True

    monkeypatch.setattr("raiker.auth.accounts.passwords.verify_password", verify_password)

    with pytest.raises(AuthError) as exc:
        svc.login("inactive", "inactive-pass")

    assert str(exc.value) == GENERIC_AUTH_ERROR
    account = svc._store.get_account(principal_id)
    assert account is not None
    expected_algorithms = [account["hash_algo"]]
    if passwords.ARGON2_AVAILABLE:
        expected_algorithms.append("scrypt")
    assert [hash_algo for _password, _password_hash, hash_algo in verify_calls] == expected_algorithms
    with svc._store.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM api_sessions WHERE principal_id = ?", (principal_id,)
        ).fetchone()[0]
    assert count == 0


def test_duplicate_username_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    svc.register("alice", "pa")
    with pytest.raises(AuthError):
        svc.register("alice", "pb")


def test_instance_rejects_a_second_account(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    svc.register("alice", "pa")

    with pytest.raises(AuthError, match="separate Raiker instance"):
        svc.register("bob", "pb")


def test_password_recovery_requires_a_ticket_and_mfa_then_revokes_all_sessions(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    principal_id = svc.register("alice", "old-password")
    secret, _uri, _codes = svc.begin_enroll_mfa(principal_id)
    svc.activate_mfa(principal_id, pyotp.TOTP(secret).now())
    stale_token, _ = ApiSessionStore(tmp_path).create_session(principal_id, scope="control")

    ticket = svc.begin_password_recovery("alice")
    assert ticket
    svc.complete_password_recovery(ticket, pyotp.TOTP(secret).now(), "new-password")

    stale = ApiSessionStore(tmp_path).get_by_token(stale_token)
    assert stale is not None and stale.revoked
    with pytest.raises(AuthError):
        svc.login("alice", "old-password")
    assert svc.login("alice", "new-password").stage == "mfa_required"


def test_password_recovery_locks_out_after_repeated_wrong_codes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Recovery resets the password, so its code gate needs login's lockout.

    ``login`` locks the account after ``LOCKOUT_THRESHOLD`` failures; recovery
    never did, so one ticket tolerated unlimited guesses against a 6-digit TOTP
    (~333k effective codes, since ``valid_window=1`` keeps three live at once)
    at hundreds of tries per second, and tickets are freely re-mintable. That is
    an account-takeover primitive, not a brute-force nuisance.
    """
    svc = _svc(tmp_path)
    principal_id = svc.register("alice", "old-password")
    secret, _uri, _codes = svc.begin_enroll_mfa(principal_id)
    svc.activate_mfa(principal_id, pyotp.TOTP(secret).now())

    ticket = svc.begin_password_recovery("alice")
    for _ in range(LOCKOUT_THRESHOLD):
        with pytest.raises(AuthError):
            svc.complete_password_recovery(ticket, "000000", "new-password")

    # Locked out: even the correct code must now be refused.
    with pytest.raises(AuthError):
        svc.complete_password_recovery(ticket, pyotp.TOTP(secret).now(), "new-password")
    # A fresh ticket must not reset the lockout either.
    with pytest.raises(AuthError):
        svc.complete_password_recovery(
            svc.begin_password_recovery("alice"), pyotp.TOTP(secret).now(), "new-password"
        )
    # The password was never changed. Checked against the stored hash rather than
    # via login, which is itself locked out by the same counter.
    account = SQLiteStore(tmp_path).get_account(principal_id)
    assert account is not None
    assert passwords.verify_password(
        "old-password", account["password_hash"], account["hash_algo"]
    )


def test_password_recovery_ticket_is_single_use(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    principal_id = svc.register("alice", "old-password")
    secret, _uri, _codes = svc.begin_enroll_mfa(principal_id)
    svc.activate_mfa(principal_id, pyotp.TOTP(secret).now())
    ticket = svc.begin_password_recovery("alice")
    svc.complete_password_recovery(ticket, pyotp.TOTP(secret).now(), "new-password")

    with pytest.raises(AuthError, match="Password recovery failed"):
        svc.complete_password_recovery(ticket, pyotp.TOTP(secret).now(), "another-password")


def test_failed_registration_releases_the_singleton_reservation(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    monkeypatch.setattr(svc._store, "create_initial_account_atomic", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        svc.register("alice", "password")

    assert _svc(tmp_path).register("alice", "password")


def test_purging_sole_account_reopens_initial_registration(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    principal_id = svc.register("alice", "password")
    svc._store.purge_account(principal_id)

    replacement = _svc(tmp_path).register("replacement", "password")
    principal = SQLiteStore(tmp_path).get_principal(replacement)
    assert principal is not None
    assert OWNER_ROLE_ID in principal["role_ids"]


def test_legacy_controls_migrate_only_to_original_account_and_stay_principal_scoped(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    store.save_model_session_state(ModelSessionState(TERMINAL_MODEL_SESSION_ID, "llama-cpp-local"))
    now = utc_now()
    store.upsert_capability_gate_state({
        "capability": "hosted_model_runtime", "state": "enabled_runtime",
        "requested_by": "legacy", "requested_at": now, "activated_by": "legacy",
        "activated_at": now, "reason": "legacy", "created_at": now, "updated_at": now,
    })
    svc = _svc(tmp_path)
    owner = svc.register("owner", "owner-password")
    legacy = _seed_legacy_account(svc, "legacy", "legacy-password")

    assert store.load_principal_model_state(owner) is not None
    assert store.load_principal_model_state(legacy) is None
    assert provider_runtime_policy_from_gates(store, owner).allow_hosted_provider is True
    assert provider_runtime_policy_from_gates(store, legacy).allow_hosted_provider is False

    control = RuntimeControlService(tmp_path)
    assert control.set_capability_decision_mode("medical_runtime", "deny", owner).ok
    assert control.get_capability_decision_mode("medical_runtime", owner).data["decision_mode"] == "deny"
    assert control.get_capability_decision_mode("medical_runtime", legacy).data["decision_mode"] == "ask"


def test_legacy_secondary_does_not_inherit_global_enabled_gate(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    owner = svc.register("owner", "owner-password")
    legacy = _seed_legacy_account(svc, "legacy", "legacy-password")
    now = utc_now()
    svc._store.upsert_capability_gate_state({
        "capability": "file_write_execution", "state": "enabled_runtime",
        "requested_by": owner, "requested_at": now, "activated_by": owner,
        "activated_at": now, "reason": "legacy global", "created_at": now, "updated_at": now,
    })

    gate = RuntimeControlService(tmp_path).get_capability_gate("file_write_execution", legacy)
    assert gate is not None
    assert gate.state == "disabled"
    assert gate.decision_mode == "ask"


def test_retrieval_helper_does_not_inherit_legacy_global_gate(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    svc.register("owner", "owner-password")
    legacy = _seed_legacy_account(svc, "legacy", "legacy-password")
    now = utc_now()
    svc._store.upsert_capability_gate_state({
        "capability": "vector_embedding_runtime", "state": "enabled_runtime",
        "requested_by": "legacy", "requested_at": now, "activated_by": "legacy",
        "activated_at": now, "reason": "legacy global", "created_at": now, "updated_at": now,
    })

    plan = RetrievalAugmentor(tmp_path, svc._store, principal_id=legacy).plan("secret")
    assert plan.decision == "disabled"


def test_turn_and_event_reads_filter_other_account_session_ids(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    now = utc_now()
    store.insert_user(User("user_a", "A", None, True, now, now))
    store.insert_user(User("user_b", "B", None, True, now, now))
    store.create_session("sess_a", str(tmp_path), user_id="user_a")
    store.create_session("sess_b", str(tmp_path), user_id="user_b")
    store.insert_turn("sess_b", "turn_b", "secret")
    EventLogWriter(store).append(
        make_event(
            session_id="sess_b", turn_id="turn_b", event_type="prompt_received",
            actor="test", payload={"secret": "b"},
        )
    )

    dashboard = DashboardService(tmp_path)
    assert dashboard.get_turn("turn_b", user_id="user_a") is None
    assert dashboard.list_events(user_id="user_a") == []
