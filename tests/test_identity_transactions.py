from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import OWNER_ROLE_ID, bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.contracts.models import Role, User
from raiker.storage.sqlite import SQLiteStore


@pytest.mark.parametrize("phase", ("guard", "user", "principal", "credential", "migration"))
def test_initial_account_transaction_rolls_back_every_phase(tmp_path: Path, phase: str) -> None:
    store = SQLiteStore(tmp_path)
    now = utc_now()
    with pytest.raises(RuntimeError, match=f"injected_failure:{phase}"):
        store.create_initial_account_atomic(
            user=User("owner", "Owner", None, True, now, now), principal_id="principal_owner",
            username="owner", password_hash="hash", hash_algo="test", role_ids=(),
            max_runtime_mode="local_single_user_runtime", fail_after=phase,
        )
    assert store.get_principal("principal_owner") is None
    assert store.get_account("principal_owner") is None
    with store.connect() as connection:
        assert connection.execute("SELECT 1 FROM instance_account_guard").fetchone() is None


@pytest.mark.parametrize("phase", ("user", "principal", "credential", "finalize"))
def test_owner_recovery_transaction_rolls_back_every_phase(tmp_path: Path, phase: str) -> None:
    store = SQLiteStore(tmp_path)
    now = utc_now()
    assert store.create_initial_account_atomic(
        user=User("owner", "Owner", None, True, now, now), principal_id="principal_owner",
        username="owner", password_hash="hash", hash_algo="test", role_ids=(),
        max_runtime_mode="local_single_user_runtime",
    )
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO api_sessions (session_id, principal_id, token_hash, created_at) VALUES (?, ?, ?, ?)",
            ("session_owner", "principal_owner", "hash", now),
        )

    with pytest.raises(RuntimeError, match=f"injected_failure:{phase}"):
        store.recover_owner_atomic(
            user=User("replacement", "Replacement", None, True, now, now),
            principal_id="principal_replacement", role_ids=(),
            old_principal_ids=["principal_owner"], credential_owner_id="principal_owner",
            max_runtime_mode="local_single_user_runtime", fail_after=phase,
        )

    assert store.get_principal("principal_replacement") is None
    assert store.get_account("principal_replacement") is None
    owner = store.get_principal("principal_owner")
    assert owner is not None
    assert owner["is_active"] is True
    assert store.get_account("principal_owner") is not None
    with store.connect() as connection:
        guard = connection.execute("SELECT principal_id FROM instance_account_guard").fetchone()
        assert guard["principal_id"] == "principal_owner"
        session = connection.execute("SELECT revoked FROM api_sessions WHERE session_id = ?", ("session_owner",)).fetchone()
        assert session["revoked"] == 0


def test_recovery_revokes_inactive_credential_owner_sessions(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    now = utc_now()
    store.insert_role(Role(OWNER_ROLE_ID, "owner", "owner", True, now))
    assert store.create_initial_account_atomic(
        user=User("owner", "Owner", None, True, now, now), principal_id="principal_owner",
        username="owner", password_hash="hash", hash_algo="test", role_ids=(OWNER_ROLE_ID,),
        max_runtime_mode="local_single_user_runtime",
    )
    with store.connect() as connection:
        connection.execute("UPDATE principals SET is_active = 0 WHERE principal_id = ?", ("principal_owner",))
        connection.execute(
            "INSERT INTO api_sessions (session_id, principal_id, token_hash, created_at) VALUES (?, ?, ?, ?)",
            ("session_owner", "principal_owner", "hash", now),
        )

    result = bootstrap_owner(
        "replacement", "Replacement", workspace_root=tmp_path, is_recovery=True,
        force_recover=True, confirm_deactivate_old=True, recovery_reason="lost access",
    )

    assert "Owner recovery successful" in result
    with store.connect() as connection:
        session = connection.execute("SELECT revoked FROM api_sessions WHERE session_id = ?", ("session_owner",)).fetchone()
        assert session["revoked"] == 1


def test_brain_sources_are_persisted_per_owner(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.add_brain_source("principal_one", "research")
    store.add_brain_source("principal_two", "private")
    store.remove_brain_source("principal_one", "private")
    assert store.list_brain_sources("principal_one") == ["research"]
    assert store.list_brain_sources("principal_two") == ["private"]


def test_recovery_transfers_owner_scoped_records(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    now = utc_now()
    assert store.create_initial_account_atomic(
        user=User("owner", "Owner", None, True, now, now), principal_id="principal_owner",
        username="owner", password_hash="hash", hash_algo="test", role_ids=(),
        max_runtime_mode="local_single_user_runtime",
    )
    store.add_brain_source("principal_owner", "research")
    store.put_user_settings("principal_owner", "{}", now)
    store.recover_owner_atomic(
        user=User("replacement", "Replacement", None, True, now, now),
        principal_id="principal_replacement", role_ids=(), old_principal_ids=["principal_owner"],
        credential_owner_id="principal_owner", max_runtime_mode="local_single_user_runtime",
    )
    assert store.list_brain_sources("principal_replacement") == ["research"]
    assert store.get_user_settings("principal_replacement") is not None
    assert store.get_principal("principal_owner")["is_active"] is False  # type: ignore[index]


def test_purge_removes_only_target_owner_scoped_records(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    now = utc_now()
    assert store.create_initial_account_atomic(
        user=User("owner", "Owner", None, True, now, now), principal_id="principal_owner",
        username="owner", password_hash="hash", hash_algo="test", role_ids=(),
        max_runtime_mode="local_single_user_runtime",
    )
    store.insert_user(User("other", "Other", None, True, now, now))
    store.insert_principal(
        "principal_other", "human", "Other", delegated_by_user_id="other",
        max_runtime_mode="multi_user_local_runtime",
    )
    store.add_brain_source("principal_owner", "owner-data")
    store.add_brain_source("principal_other", "other-data")
    store.put_user_settings("principal_owner", "{}", now)
    store.put_user_settings("principal_other", "{}", now)

    store.purge_account("principal_owner")

    assert store.list_brain_sources("principal_owner") == []
    assert store.get_user_settings("principal_owner") is None
    assert store.list_brain_sources("principal_other") == ["other-data"]
    assert store.get_user_settings("principal_other") is not None
    assert store.get_principal("principal_owner")["is_active"] is False  # type: ignore[index]


def test_purge_account_removes_an_owner_with_real_session_history(tmp_path: Path) -> None:
    """Purge must survive a workspace that has conversations in it.

    ``purge_account`` sweeps ``sqlite_master`` in table-creation order, which is
    parent-before-child: ``sessions`` is created before ``turns``, and
    ``turns.session_id`` references it. With ``PRAGMA foreign_keys = ON`` the
    parent delete raises ``FOREIGN KEY constraint failed``, so purge fails on any
    account that ever held a conversation. The pre-existing purge tests only seed
    brain sources and settings — neither has a child row — so none of them touch
    the ordering.
    """
    store = SQLiteStore(tmp_path)
    now = utc_now()
    assert store.create_initial_account_atomic(
        user=User("owner", "Owner", None, True, now, now), principal_id="principal_owner",
        username="owner", password_hash="hash", hash_algo="test", role_ids=(),
        max_runtime_mode="local_single_user_runtime",
    )
    store.create_session("sess_owned", str(tmp_path), user_id="owner")
    store.insert_turn("sess_owned", "turn_owned", "hello", status="completed")

    store.insert_user(User("other", "Other", None, True, now, now))
    store.insert_principal(
        "principal_other", "human", "Other", delegated_by_user_id="other",
        max_runtime_mode="multi_user_local_runtime",
    )
    store.create_session("sess_other", str(tmp_path), user_id="other")
    store.insert_turn("sess_other", "turn_other", "keep me", status="completed")

    store.purge_account("principal_owner")

    with store.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = 'owner'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM turns WHERE session_id = 'sess_owned'"
        ).fetchone()[0] == 0
        # The other account keeps its conversation.
        assert connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = 'other'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM turns WHERE session_id = 'sess_other'"
        ).fetchone()[0] == 1


def test_purge_account_removes_an_owner_with_no_delegation_link(tmp_path: Path) -> None:
    """An owner whose principal predates the delegation link must still purge.

    Principals created by older bootstraps carry a NULL ``delegated_by_user_id``
    and are linked to their user only by the ``principal_<user_id>`` naming
    convention — a real, observed shape in existing workspaces. Resolving the
    user from the delegation column alone yields NULL, so every user-keyed and
    session-keyed delete matches nothing and the purge silently no-ops while
    reporting success, leaving the whole account's data behind. Every other
    resolver in the store already falls back to the prefix.
    """
    store = SQLiteStore(tmp_path)
    now = utc_now()
    store.insert_user(User("owner", "Owner", None, True, now, now))
    store.insert_principal(
        "principal_owner", "human", "Owner", delegated_by_user_id=None,
        max_runtime_mode="local_single_user_runtime",
    )
    with store.connect() as connection:
        assert connection.execute(
            "SELECT delegated_by_user_id FROM principals WHERE principal_id = 'principal_owner'"
        ).fetchone()["delegated_by_user_id"] is None
    store.create_session("sess_cli", str(tmp_path), user_id="owner")
    store.insert_turn("sess_cli", "turn_cli", "hello", status="completed")

    store.purge_account("principal_owner")

    with store.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = 'owner'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM turns WHERE session_id = 'sess_cli'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM users WHERE user_id = 'owner'"
        ).fetchone()[0] == 0


def test_purge_account_removes_rows_orphaned_by_its_own_deletes(tmp_path: Path) -> None:
    """Purge must not leave a child row pointing at a parent it deleted.

    The sweep can only match tables that carry an owner/session/project column.
    ``policy_decisions`` and ``approvals`` reference ``tool_actions.action_id``
    and carry none, so deleting the owner's ``tool_actions`` orphans them and the
    transaction fails the foreign-key check at COMMIT. Same shape for
    ``gist_memories`` -> ``eidetic_observations`` and the two
    ``*_relationship*`` tables -> ``approved_memory``.
    """
    store = SQLiteStore(tmp_path)
    now = utc_now()
    assert store.create_initial_account_atomic(
        user=User("owner", "Owner", None, True, now, now), principal_id="principal_owner",
        username="owner", password_hash="hash", hash_algo="test", role_ids=(),
        max_runtime_mode="local_single_user_runtime",
    )
    store.create_session("sess_a", str(tmp_path), user_id="owner")
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO tool_actions (action_id, session_id, tool_name, arguments_json, "
            "risk_level, status, proposed_at) VALUES ('act_1', 'sess_a', 'x', '{}', 'low', 'proposed', ?)",
            (now,),
        )
        connection.execute(
            "INSERT INTO policy_decisions (decision_id, action_id, decision, reasons_json, "
            "policy_version, created_at) VALUES ('dec_1', 'act_1', 'allow', '[]', '1.0', ?)",
            (now,),
        )

    store.purge_account("principal_owner")

    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM tool_actions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM policy_decisions").fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_original_owner_pointer_follows_recovery_to_the_live_owner(tmp_path: Path) -> None:
    """After recovery the pointer must name the *live* owner, not the dead one.

    ``_original_owner_from_connection`` picks the earliest ``rl_owner`` principal
    with no ``is_active`` filter. Recovery deactivates the old owner but leaves
    its role_ids and its earlier created_at, so the pointer keeps resolving to
    the deactivated principal. That pointer is the destination for every
    unattributed-data backfill (run on each ``SQLiteStore.__init__``) and for
    ``write_memory``'s owner fallback, so new data would be filed against a dead
    principal and stay invisible to the recovered owner forever.
    """
    store = SQLiteStore(tmp_path)
    now = utc_now()
    store.insert_role(Role(OWNER_ROLE_ID, "owner", "owner", True, now))
    assert store.create_initial_account_atomic(
        user=User("owner", "Owner", None, True, now, now), principal_id="principal_owner",
        username="owner", password_hash="hash", hash_algo="test", role_ids=(OWNER_ROLE_ID,),
        max_runtime_mode="local_single_user_runtime",
    )
    assert store.original_account_principal_id() == "principal_owner"

    store.recover_owner_atomic(
        user=User("replacement", "Replacement", None, True, now, now),
        principal_id="principal_replacement", role_ids=(OWNER_ROLE_ID,),
        old_principal_ids=["principal_owner"], credential_owner_id="principal_owner",
        max_runtime_mode="local_single_user_runtime",
    )

    old = store.get_principal("principal_owner")
    assert old is not None and old["is_active"] is False
    assert store.original_account_principal_id() == "principal_replacement"


def test_context_data_backfill_files_unowned_rows_to_the_live_owner(tmp_path: Path) -> None:
    """The backfill path must resolve the owner the same way the pointer does.

    ``original_account_principal_id`` was hardened to skip deactivated owners,
    but ``_backfill_owned_context_data`` kept its own copy of the query with no
    ``is_active`` filter. That backfill is what the pointer fix exists to
    protect — it runs on every ``SQLiteStore.__init__`` — so an unowned row
    created after a recovery is filed against the dead owner even though the
    pointer itself now resolves correctly.
    """
    store = SQLiteStore(tmp_path)
    now = utc_now()
    store.insert_role(Role(OWNER_ROLE_ID, "owner", "owner", True, now))
    assert store.create_initial_account_atomic(
        user=User("owner", "Owner", None, True, now, now), principal_id="principal_owner",
        username="owner", password_hash="hash", hash_algo="test", role_ids=(OWNER_ROLE_ID,),
        max_runtime_mode="local_single_user_runtime",
    )
    store.recover_owner_atomic(
        user=User("replacement", "Replacement", None, True, now, now),
        principal_id="principal_replacement", role_ids=(OWNER_ROLE_ID,),
        old_principal_ids=["principal_owner"], credential_owner_id="principal_owner",
        max_runtime_mode="local_single_user_runtime",
    )
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO approved_memory (memory_id, text, scope, sensitivity, source_event_id, "
            "memory_type, created_at, tags_json, source, owner_principal_id) "
            "VALUES ('mem_unowned', 'text', 'default', 'public', 'evt_1', 'fact', ?, '[]', "
            "'test', NULL)",
            (now,),
        )

    SQLiteStore(tmp_path)  # Bootstrap runs the backfills.

    with store.connect() as connection:
        owner = connection.execute(
            "SELECT owner_principal_id FROM approved_memory WHERE memory_id = 'mem_unowned'"
        ).fetchone()["owner_principal_id"]
    assert owner == "principal_replacement", f"filed against {owner}, a deactivated principal"


def test_cli_bootstrapped_owner_can_be_recovered_without_credentials(tmp_path: Path) -> None:
    """A CLI-bootstrapped owner is the documented lost-access path.

    ``bootstrap_owner`` creates its owner with no username/password, so it never
    has an ``account_credentials`` row. Gating recovery on a credential-backed
    owner therefore locks out exactly the owner that recovery exists to replace.
    This is deliberately not hand-seeded with credentials — that is what masked
    the break.
    """
    assert "Owner bootstrap successful." in bootstrap_owner(
        "alice", "Alice", workspace_root=tmp_path
    )
    store = SQLiteStore(tmp_path)
    assert store.get_account("principal_alice") is None, "CLI bootstrap must not create credentials"

    message = bootstrap_owner(
        "bob", "Bob", workspace_root=tmp_path, is_recovery=True, force_recover=True,
        confirm_deactivate_old=True, recovery_reason="alice lost access",
    )

    assert "Owner recovery successful." in message, message
    new_owner = store.get_principal("principal_bob")
    assert new_owner is not None and new_owner["is_active"] is True
    old_owner = store.get_principal("principal_alice")
    assert old_owner is not None and old_owner["is_active"] is False


def test_recovery_on_an_empty_workspace_creates_the_owner(tmp_path: Path) -> None:
    """No owners at all: recovery has nothing to transfer, and must not raise."""
    message = bootstrap_owner(
        "bob", "Bob", workspace_root=tmp_path, is_recovery=True, force_recover=True,
        confirm_deactivate_old=True, recovery_reason="fresh workspace",
    )

    assert "Owner recovery successful." in message, message
    owner = SQLiteStore(tmp_path).get_principal("principal_bob")
    assert owner is not None and owner["is_active"] is True


def test_partially_applied_migration_is_not_recorded_as_applied(tmp_path: Path) -> None:
    """A migration must not be marked applied when its script did not finish.

    ``OWNED_CONTEXT_DATA_SQL`` is three bare ``ALTER TABLE ... ADD COLUMN``
    statements, and ``executescript`` issues an implicit COMMIT — so a crash
    between the first ALTER committing and the bookkeeping INSERT leaves the
    database half-migrated. On restart the first ALTER raises "duplicate column
    name"; swallowing that and recording the migration anyway strands the
    remaining columns forever, and every owner-scoped read against them raises.
    """
    from raiker.storage import migrations
    from raiker.storage.sqlite import SQLiteStore as Store

    SQLiteStore(tmp_path)  # fully migrated workspace
    # Rewind to the exact crash-resume state: the first ALTER committed, the
    # rest never ran, and the bookkeeping INSERT never happened.
    with SQLiteStore(tmp_path).connect() as connection:
        connection.execute(
            "DELETE FROM migrations WHERE migration_id = ?",
            (migrations.OWNED_CONTEXT_DATA_MIGRATION_ID,),
        )
        for table in ("vector_records", "attachments"):
            connection.execute(f"DROP INDEX IF EXISTS idx_{table}_owner")
            connection.execute(f"ALTER TABLE {table} DROP COLUMN owner_principal_id")

    store = Store(tmp_path)  # re-open: the migration re-runs and hits the ALTER

    with store.connect() as connection:
        applied = connection.execute(
            "SELECT 1 FROM migrations WHERE migration_id = ?",
            (migrations.OWNED_CONTEXT_DATA_MIGRATION_ID,),
        ).fetchone() is not None
        columns = {
            table: {
                str(row["name"])
                for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            for table in ("approved_memory", "vector_records", "attachments")
        }
    # Every table must end up with the column, whether the migration re-ran
    # cleanly or was correctly recognised as already applied.
    for table, cols in columns.items():
        assert "owner_principal_id" in cols, f"{table} never got its owner column"
    assert applied
    # And the owner-scoped read that depends on it must work.
    assert store.list_vector_records(owner_principal_id="principal_nobody") == []
