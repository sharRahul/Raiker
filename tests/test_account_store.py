from __future__ import annotations

from raiker.storage.sqlite import SQLiteStore


def _store(tmp_path) -> SQLiteStore:  # type: ignore[no-untyped-def]
    return SQLiteStore(tmp_path)


def test_account_upsert_get_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _store(tmp_path)
    store.upsert_account("p1", "alice", "hash1", "argon2id", "t0", "t0")
    by_name = store.get_account_by_username("alice")
    assert by_name is not None
    assert by_name["principal_id"] == "p1"
    assert by_name["password_hash"] == "hash1"
    assert by_name["hash_algo"] == "argon2id"
    assert by_name["failed_attempts"] == 0
    account = store.get_account("p1")
    assert account is not None
    assert account["username"] == "alice"
    assert store.get_account_by_username("nobody") is None


def test_account_failed_and_lock(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _store(tmp_path)
    store.upsert_account("p1", "alice", "h", "argon2id", "t0", "t0")
    store.set_account_failed("p1", 3, None)
    account = store.get_account("p1")
    assert account is not None
    assert account["failed_attempts"] == 3
    store.set_account_failed("p1", 5, "2999-01-01T00:00:00+00:00")
    acct = store.get_account("p1")
    assert acct is not None
    assert acct["failed_attempts"] == 5
    assert acct["locked_until"] == "2999-01-01T00:00:00+00:00"


def test_account_mfa_and_password(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _store(tmp_path)
    store.upsert_account("p1", "alice", "h", "argon2id", "t0", "t0")
    store.set_account_mfa("p1", True, b"secretblob", '["a","b"]')
    acct = store.get_account("p1")
    assert acct is not None
    assert acct["mfa_enrolled"] == 1
    assert bytes(acct["mfa_secret_encrypted"]) == b"secretblob"
    assert acct["backup_codes_hashed"] == '["a","b"]'
    store.set_account_password("p1", "hash2", "scrypt", "t1")
    acct = store.get_account("p1")
    assert acct is not None
    assert acct["password_hash"] == "hash2"
    assert acct["hash_algo"] == "scrypt"
    assert acct["updated_at"] == "t1"


def test_account_delete(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _store(tmp_path)
    store.upsert_account("p1", "alice", "h", "argon2id", "t0", "t0")
    store.delete_account("p1")
    assert store.get_account("p1") is None


def test_user_settings_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _store(tmp_path)
    assert store.get_user_settings("p1") is None
    store.put_user_settings("p1", '{"theme":"dark"}', "t0")
    settings = store.get_user_settings("p1")
    assert settings is not None
    assert settings["settings_json"] == '{"theme":"dark"}'
    store.put_user_settings("p1", '{"theme":"light"}', "t1")
    settings = store.get_user_settings("p1")
    assert settings is not None
    assert settings["settings_json"] == '{"theme":"light"}'
