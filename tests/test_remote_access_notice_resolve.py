"""BUG-359 — the *Remote access is suspended* notice leaves the tray once MFA is on again."""

from __future__ import annotations

from pathlib import Path

import pyotp
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.notify.remote_access_notifier import (
    REMOTE_ACCESS_SUSPENDED_KIND,
    notify_remote_access_suspended,
    resolve_remote_access_suspended,
)
from raiker.storage.sqlite import SQLiteStore

USER = "owner"
PASSWORD = "correct horse battery staple 42"


def _unread_suspensions(store: SQLiteStore) -> int:
    owner = store.original_account_principal_id()
    assert owner
    return sum(
        1
        for row in store.list_notifications(owner, unread_only=True)
        if row["kind"] == REMOTE_ACCESS_SUSPENDED_KIND
    )


def test_resolving_marks_only_suspension_notices_read(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    assert client.post("/api/auth/register", json={"username": USER, "password": PASSWORD}).status_code == 200
    store = SQLiteStore(tmp_path)
    owner = store.original_account_principal_id()
    assert owner
    notify_remote_access_suspended(store, reason="mfa_disabled")
    other = store.insert_notification(principal_id=owner, kind="task_failed", title="t", body="b", subject_id="x")
    assert _unread_suspensions(store) == 1
    assert resolve_remote_access_suspended(store) == 1
    assert _unread_suspensions(store) == 0
    unread_ids = {row["notification_id"] for row in store.list_notifications(owner, unread_only=True)}
    assert other in unread_ids


def test_activating_mfa_resolves_the_notice(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/register", json={"username": USER, "password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    store = SQLiteStore(tmp_path)
    notify_remote_access_suspended(store, reason="mfa_disabled")
    assert _unread_suspensions(store) == 1
    secret = client.post("/api/auth/mfa/enroll", headers=headers).json()["secret"]
    response = client.post("/api/auth/mfa/activate", json={"code": pyotp.TOTP(secret).now()}, headers=headers)
    assert response.status_code == 200
    assert _unread_suspensions(store) == 0
