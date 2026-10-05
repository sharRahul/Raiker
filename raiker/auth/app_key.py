"""Internal application key.

Distinct from the user-managed connector vault key. This key encrypts Raiker's
own at-rest secrets (currently TOTP MFA seeds) so those features never depend on
whether a connector vault has been configured. It is auto-generated on first use,
never entered through the UI, and its absence does not trigger connector
fail-closed behavior.

DEC-24 step 6 — "first use" is a fact about the workspace, not about the key
file. The same key derives the encrypted store's key, so a key file that has
gone missing while ``raiker.db`` is still there is not a first use: a new key
would open nothing, and written into the old key's place it would make the
owner's restore of the original harder rather than easier. That case refuses
with ``store_key_missing`` and writes nothing.
"""

from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet

from raiker.auth.secure_io import atomic_write_private
from raiker.storage.internal_paths import internal_io_path
from raiker.storage.store_errors import AppKeyMissingError

_KEY_DIRNAME = ".raiker"
_KEY_FILENAME = "app.key"


def app_key_path(workspace_root: str | Path) -> Path:
    return internal_io_path(
        Path(workspace_root).resolve() / _KEY_DIRNAME / _KEY_FILENAME
    )


def _store_exists(workspace_root: str | Path) -> bool:
    """True when the encrypted store this key unlocks already holds data.

    A zero-byte file is what an interrupted first open leaves behind, and holds
    nothing a new key could fail to open.
    """
    db = internal_io_path(Path(workspace_root).resolve() / _KEY_DIRNAME / "raiker.db")
    try:
        return db.stat().st_size > 0
    except OSError:
        return False


def ensure_app_key(workspace_root: str | Path) -> bytes:
    """Return the app key, generating a 0600 key-file on first call.

    Raises :class:`AppKeyMissingError` instead of generating one when the
    workspace's encrypted store already exists without it.
    """
    path = app_key_path(workspace_root)
    if path.exists():
        return path.read_bytes().strip()
    if _store_exists(workspace_root):
        raise AppKeyMissingError()
    key = Fernet.generate_key()
    # O_EXCL: never follow/overwrite an existing file or symlink (defeats a
    # symlink-swap race); if a concurrent caller won, adopt its key.
    if not atomic_write_private(path, key, exclusive=True):
        return path.read_bytes().strip()
    return key


def app_fernet(workspace_root: str | Path) -> Fernet:
    return Fernet(ensure_app_key(workspace_root))
