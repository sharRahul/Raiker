from __future__ import annotations

from raiker.storage.sqlite import SQLiteStore


def test_lock_screen_tables_and_columns(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    with store.connect() as c:
        c.execute(
            "SELECT username, password_hash, hash_algo, failed_attempts, locked_until, "
            "mfa_enrolled, mfa_secret_encrypted, backup_codes_hashed, created_at, updated_at "
            "FROM account_credentials"
        )
        c.execute("SELECT principal_id, settings_json, updated_at FROM user_settings")
        c.execute(
            "SELECT contact_id, principal_id, name, method, value, created_at FROM trusted_contacts"
        )
        session_cols = {r["name"] for r in c.execute("PRAGMA table_info(api_sessions)")}
        assert {"scope", "absolute_expires_at", "last_seen_at", "device_label"} <= session_cols
        task_cols = {r["name"] for r in c.execute("PRAGMA table_info(tasks)")}
        assert {"priority", "scheduled_at", "recurrence", "reminder_at"} <= task_cols


def test_account_credentials_username_unique(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import sqlite3

    store = SQLiteStore(tmp_path)
    with store.connect() as c:
        c.execute(
            "INSERT INTO account_credentials "
            "(principal_id, username, password_hash, hash_algo, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", "alice", "h", "argon2id", "t", "t"),
        )
    try:
        with store.connect() as c:
            c.execute(
                "INSERT INTO account_credentials "
                "(principal_id, username, password_hash, hash_algo, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("p2", "alice", "h", "argon2id", "t", "t"),
            )
        raise AssertionError("expected UNIQUE violation on username")
    except sqlite3.IntegrityError:
        pass
