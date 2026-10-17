"""DIST-08 — the connector vault key in the OS key store, and the fallback policy."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from raiker.app.uninstall import apply_uninstall, plan_uninstall
from raiker.auth import os_keystore
from raiker.auth.vault_key_file import (
    clear_vault_key,
    ensure_vault_key,
    read_vault_key,
    vault_key_path,
    vault_status,
    write_vault_key,
)

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the keyring path is macOS/Linux")


class FakeKeyring:
    priority = 10

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], str] = {}
        self.refuse = False

    def set_password(self, service: str, account: str, value: str) -> None:
        if self.refuse:
            raise RuntimeError("locked")
        self.items[(service, account)] = value

    def get_password(self, service: str, account: str) -> str | None:
        if self.refuse:
            raise RuntimeError("locked")
        return self.items.get((service, account))

    def delete_password(self, service: str, account: str) -> None:
        self.items.pop((service, account), None)


@pytest.fixture
def keyring(monkeypatch: pytest.MonkeyPatch) -> FakeKeyring:
    fake = FakeKeyring()
    monkeypatch.setenv(os_keystore.KEYSTORE_ENV, "auto")
    monkeypatch.setattr(os_keystore, "_keyring", lambda: fake)
    return fake


def test_protection_is_off_in_a_source_checkout_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(os_keystore.KEYSTORE_ENV, raising=False)
    assert os_keystore.enabled() is False
    key = ensure_vault_key(tmp_path)
    assert vault_key_path(tmp_path).read_text(encoding="ascii").strip() == key
    assert os_keystore.status().backend == "file"


def test_a_new_key_lives_in_the_keystore_and_the_file_holds_a_reference(
    keyring: FakeKeyring, tmp_path: Path
) -> None:
    key = ensure_vault_key(tmp_path)
    on_disk = vault_key_path(tmp_path).read_text(encoding="ascii")
    assert os_keystore.is_protected(on_disk)
    assert key not in on_disk
    assert list(keyring.items.values()) == [key]
    assert read_vault_key(tmp_path) == key
    assert vault_status(tmp_path) == "configured_valid"


def test_a_plain_key_is_moved_into_the_keystore_on_first_read(
    keyring: FakeKeyring, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(os_keystore.KEYSTORE_ENV, "off")
    key = ensure_vault_key(tmp_path)
    monkeypatch.setenv(os_keystore.KEYSTORE_ENV, "auto")
    assert read_vault_key(tmp_path) == key
    assert os_keystore.is_protected(vault_key_path(tmp_path).read_text(encoding="ascii"))
    assert read_vault_key(tmp_path) == key


def test_a_refusing_keystore_keeps_the_private_file(keyring: FakeKeyring, tmp_path: Path) -> None:
    keyring.refuse = True
    key = ensure_vault_key(tmp_path)
    assert vault_key_path(tmp_path).read_text(encoding="ascii").strip() == key


def test_an_unreadable_protected_key_fails_closed_and_is_never_replaced(
    keyring: FakeKeyring, tmp_path: Path
) -> None:
    ensure_vault_key(tmp_path)
    reference = vault_key_path(tmp_path).read_text(encoding="ascii")
    keyring.refuse = True
    with pytest.raises(os_keystore.KeystoreUnavailableError):
        read_vault_key(tmp_path)
    with pytest.raises(os_keystore.KeystoreUnavailableError):
        ensure_vault_key(tmp_path)
    assert vault_status(tmp_path) == "invalid"
    # Nothing regenerated a key over the reference.
    assert vault_key_path(tmp_path).read_text(encoding="ascii") == reference


def test_replacing_and_clearing_remove_the_stored_item(keyring: FakeKeyring, tmp_path: Path) -> None:
    from cryptography.fernet import Fernet

    ensure_vault_key(tmp_path)
    write_vault_key(tmp_path, Fernet.generate_key().decode())
    assert len(keyring.items) == 1
    clear_vault_key(tmp_path)
    assert keyring.items == {}
    assert not vault_key_path(tmp_path).exists()


def test_erasing_an_instance_on_uninstall_removes_its_keystore_item(
    keyring: FakeKeyring, tmp_path: Path
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    ensure_vault_key(workspace)
    assert keyring.items
    plan = plan_uninstall(workspace, disposition="erase", home=tmp_path, detect_source=False)
    apply_uninstall(plan, workspace, home=tmp_path)
    assert keyring.items == {}
