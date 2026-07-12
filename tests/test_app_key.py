from __future__ import annotations

import os

from raiker.auth.app_key import app_fernet, app_key_path, ensure_app_key


def test_ensure_app_key_creates_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    key = ensure_app_key(tmp_path)
    assert isinstance(key, bytes) and len(key) > 0
    path = app_key_path(tmp_path)
    assert path.exists()
    if os.name == "posix":
        assert (path.stat().st_mode & 0o777) == 0o600


def test_ensure_app_key_is_stable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    first = ensure_app_key(tmp_path)
    second = ensure_app_key(tmp_path)
    assert first == second


def test_app_fernet_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fernet = app_fernet(tmp_path)
    token = fernet.encrypt(b"totp-seed")
    assert fernet.decrypt(token) == b"totp-seed"
