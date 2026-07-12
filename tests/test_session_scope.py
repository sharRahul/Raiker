from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from raiker.api.auth import AuthMiddleware
from raiker.api.sessions import ApiSessionStore
from raiker.storage.sqlite import SQLiteStore


def _principal(store: SQLiteStore, pid: str) -> None:
    store.insert_principal(pid, "human", pid, max_runtime_mode="multi_user_local_runtime")


def _req(token: str) -> SimpleNamespace:
    return SimpleNamespace(headers={"Authorization": f"Bearer {token}"})


def test_mfa_pending_rejected_on_control_route(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    _principal(store, "p1")
    sessions = ApiSessionStore(tmp_path)
    token, _ = sessions.create_session("p1", scope="mfa_pending")
    mw = AuthMiddleware(tmp_path)
    with pytest.raises(HTTPException) as exc:
        mw.authenticate(_req(token), required_scope="control")
    assert exc.value.status_code == 403


def test_control_session_accepted(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    _principal(store, "p1")
    sessions = ApiSessionStore(tmp_path)
    token, _ = sessions.create_session("p1", scope="control")
    mw = AuthMiddleware(tmp_path)
    session, principal = mw.authenticate(_req(token), required_scope="control")
    assert principal.principal_id == "p1"
    assert session.scope == "control"


def test_revoke_others_keeps_current(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    _principal(store, "p1")
    sessions = ApiSessionStore(tmp_path)
    tok_a, sess_a = sessions.create_session("p1", scope="control")
    tok_b, _ = sessions.create_session("p1", scope="control")
    revoked = sessions.revoke_others_for_principal("p1", keep_session_id=sess_a.session_id)
    assert revoked == 1
    assert sessions.get_by_token(tok_a).revoked is False
    assert sessions.get_by_token(tok_b).revoked is True


def test_absolute_expiry_enforced(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    _principal(store, "p1")
    sessions = ApiSessionStore(tmp_path)
    # Long sliding window, but an already-past absolute cap.
    token, _ = sessions.create_session(
        "p1", scope="control", expires_in_seconds=86400, absolute_expires_in_seconds=-1
    )
    mw = AuthMiddleware(tmp_path)
    with pytest.raises(HTTPException) as exc:
        mw.authenticate(_req(token), required_scope="control")
    assert exc.value.status_code == 401


def test_touch_updates_last_seen(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    _principal(store, "p1")
    sessions = ApiSessionStore(tmp_path)
    _tok, sess = sessions.create_session("p1", scope="control")
    when = datetime.now(UTC).isoformat(timespec="seconds")
    sessions.touch(sess.session_id, when)
    rows = {r["session_id"]: r for r in sessions.list_sessions()}
    assert rows[sess.session_id]["last_seen_at"] == when
    _ = timedelta  # silence unused import guard
