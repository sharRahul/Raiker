from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from raiker.auth import vault_key_file as vkf

ENV = "RAIKER_CONNECTOR_VAULT_KEY"


def test_write_read_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    key = Fernet.generate_key().decode("ascii")
    vkf.write_vault_key(tmp_path, key)
    assert vkf.read_vault_key(tmp_path) == key


def test_write_rejects_invalid_key(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError):
        vkf.write_vault_key(tmp_path, "not-a-fernet-key")


def test_status_states(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv(ENV, raising=False)
    assert vkf.vault_status(tmp_path) == "missing"
    vkf.write_vault_key(tmp_path, Fernet.generate_key().decode("ascii"))
    assert vkf.vault_status(tmp_path) == "configured_valid"
    vkf.vault_key_path(tmp_path).write_text("garbage", encoding="ascii")
    assert vkf.vault_status(tmp_path) == "invalid"


def test_load_into_env_only_when_unset(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv(ENV, raising=False)
    key = Fernet.generate_key().decode("ascii")
    vkf.write_vault_key(tmp_path, key)
    vkf.load_vault_key_into_env(tmp_path)
    import os

    assert os.environ.get(ENV) == key


def test_env_wins_over_file(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env_key = Fernet.generate_key().decode("ascii")
    file_key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv(ENV, env_key)
    vkf.write_vault_key(tmp_path, file_key)
    vkf.load_vault_key_into_env(tmp_path)
    import os

    assert os.environ.get(ENV) == env_key


def test_clear(tmp_path) -> None:  # type: ignore[no-untyped-def]
    vkf.write_vault_key(tmp_path, Fernet.generate_key().decode("ascii"))
    vkf.clear_vault_key(tmp_path)
    assert vkf.read_vault_key(tmp_path) is None
