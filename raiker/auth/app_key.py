"""Internal application key.

Distinct from the user-managed connector vault key. This key encrypts Raiker's
own at-rest secrets (currently TOTP MFA seeds) so those features never depend on
whether a connector vault has been configured. It is auto-generated on first use,
never entered through the UI, and its absence does not trigger connector
fail-closed behavior.
"""

from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet

from raiker.auth.secure_io import atomic_write_private

_KEY_DIRNAME = ".raiker"
_KEY_FILENAME = "app.key"


def app_key_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root).resolve() / _KEY_DIRNAME / _KEY_FILENAME


def ensure_app_key(workspace_root: str | Path) -> bytes:
    """Return the app key, generating a 0600 key-file on first call."""
    path = app_key_path(workspace_root)
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    # O_EXCL: never follow/overwrite an existing file or symlink (defeats a
    # symlink-swap race); if a concurrent caller won, adopt its key.
    if not atomic_write_private(path, key, exclusive=True):
        return path.read_bytes().strip()
    return key


def app_fernet(workspace_root: str | Path) -> Fernet:
    return Fernet(ensure_app_key(workspace_root))
