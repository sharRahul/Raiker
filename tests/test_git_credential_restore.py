"""ADD-27 GH-16 — authority the owner took back does not come back with a restore.

A backup is a snapshot of the database, and the vault's encrypted GitHub token
and the grant rows are in it. Removing the token, or withdrawing a grant, after
the backup was taken used to be undone by restoring it. Both are now journalled
beside the database, outside every backup, and replayed after a restore.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.runtime.git_credential import GitCredentialBroker, GitCredentialError
from raiker.storage.backup import create_backup, restore_in_place
from raiker.storage.sqlite import SQLiteStore

TOKEN = "ghp_restoreCanary0123456789abcdefghijkl"
OWNER = "principal_owner"


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


def test_a_token_removed_after_a_backup_stays_removed(ws: Path) -> None:
    store = SQLiteStore(ws)
    broker = GitCredentialBroker(store, OWNER)
    broker.store_token(TOKEN)
    broker.grant("session", session_id="sess_a")
    record = create_backup(store.connect(), ws)

    broker.forget_token()
    restore_in_place(ws, record.backup_id)

    restored = GitCredentialBroker(SQLiteStore(ws), OWNER)
    assert restored.token_configured() is False
    assert restored.live_grant() is None


def test_a_grant_withdrawn_after_a_backup_stays_withdrawn(ws: Path) -> None:
    store = SQLiteStore(ws)
    broker = GitCredentialBroker(store, OWNER)
    broker.store_token(TOKEN)
    broker.grant("session", session_id="sess_a")
    record = create_backup(store.connect(), ws)

    broker.revoke()
    restore_in_place(ws, record.backup_id)

    restored = GitCredentialBroker(SQLiteStore(ws), OWNER)
    # The token was not removed, so it comes back; the decision to lend it does not.
    assert restored.token_configured() is True
    assert restored.live_grant() is None
    with pytest.raises(GitCredentialError) as caught, restored.lend(session_id="sess_a"):
        pass
    assert caught.value.reason == "git_grant_required"


def test_a_grant_made_after_the_withdrawal_survives_the_replay(ws: Path) -> None:
    """Replay revokes what was withdrawn, not every later decision."""
    store = SQLiteStore(ws)
    broker = GitCredentialBroker(store, OWNER)
    broker.store_token(TOKEN)
    record = create_backup(store.connect(), ws)
    broker.revoke()
    restore_in_place(ws, record.backup_id)
    restored = GitCredentialBroker(SQLiteStore(ws), OWNER)
    restored.grant("once")
    assert restored.live_grant() is not None
