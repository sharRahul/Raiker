from __future__ import annotations

import pytest

from raiker.auth.accounts import GENERIC_AUTH_ERROR, AccountService, AuthError


def _svc(tmp_path) -> AccountService:  # type: ignore[no-untyped-def]
    return AccountService(tmp_path)


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
    import pyotp

    svc.activate_mfa(pid, pyotp.TOTP(secret).now())
    result = svc.login("alice", "right-pass")
    assert result.stage == "mfa_required"
    assert result.ticket and result.token is None
    verified = svc.verify_mfa(result.ticket, pyotp.TOTP(secret).now())
    assert verified.stage == "session"
    assert verified.token


def test_change_password_revokes_others(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from raiker.api.sessions import ApiSessionStore

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


def test_accounts_are_isolated_principals(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    pid_a = svc.register("alice", "pa")
    pid_b = svc.register("bob", "pb")
    assert pid_a != pid_b


def test_duplicate_username_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = _svc(tmp_path)
    svc.register("alice", "pa")
    with pytest.raises(AuthError):
        svc.register("alice", "pb")
