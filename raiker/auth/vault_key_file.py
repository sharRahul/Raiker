"""Persistence for the user-managed connector vault master key.

The vault key encrypts connector credentials (API keys, OAuth tokens). It is set
through the web app behind elevated re-auth and stored in a 0600 key-file. The
environment variable ``RAIKER_CONNECTOR_VAULT_KEY`` always overrides the file, so
existing deployments that inject the key via the environment are unaffected.

Unlike the internal app key, this key is a user secret: it may be absent, in which
case connector processes fail closed (enforced in ``connector_ecosystem``).
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

from raiker.auth.secure_io import atomic_write_private

VAULT_KEY_ENV = "RAIKER_CONNECTOR_VAULT_KEY"
_KEY_DIRNAME = ".raiker"
_KEY_FILENAME = "vault.key"


def vault_key_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root).resolve() / _KEY_DIRNAME / _KEY_FILENAME


def _is_valid_fernet(value: str) -> bool:
    try:
        Fernet(value.encode("ascii"))
    except (ValueError, TypeError):
        return False
    return True


def read_vault_key(workspace_root: str | Path) -> str | None:
    path = vault_key_path(workspace_root)
    if not path.exists():
        return None
    value = path.read_text(encoding="ascii").strip()
    return value or None


def write_vault_key(workspace_root: str | Path, key: str) -> None:
    key = key.strip()
    if not _is_valid_fernet(key):
        raise ValueError("connector_vault_key_invalid")
    path = vault_key_path(workspace_root)
    # Replace atomically at mode 0o600 — the key never touches disk world-readable.
    atomic_write_private(path, key.encode("ascii"), exclusive=False)


def clear_vault_key(workspace_root: str | Path) -> None:
    path = vault_key_path(workspace_root)
    if path.exists():
        path.unlink()


def ensure_vault_key(workspace_root: str | Path) -> str:
    """Return this workspace's vault key, generating one if there is none.

    The vault key is a locally generated encryption key, not a passphrase the
    owner chooses or needs to remember. Blocking a credential save until they
    visit Settings and press "Generate key" produced `connector_vault_key_unset`
    for no security gain — the generated key is the same either way. Provision
    it on first use instead, at 0600, and leave Settings owning rotation and
    removal.

    An existing key (file or environment) is never replaced: silently rotating a
    key would orphan every credential already encrypted under it.
    """
    existing = effective_vault_key(workspace_root)
    if existing:
        return existing
    generated = Fernet.generate_key().decode("ascii")
    write_vault_key(workspace_root, generated)
    return generated


def load_vault_key_into_env(workspace_root: str | Path) -> None:
    """Populate the env var from the key-file when the env is unset and valid."""
    if os.environ.get(VAULT_KEY_ENV, "").strip():
        return
    value = read_vault_key(workspace_root)
    if value and _is_valid_fernet(value):
        os.environ[VAULT_KEY_ENV] = value


def effective_vault_key(workspace_root: str | Path) -> str | None:
    """Return this workspace's own key, falling back to an injected process key.

    The workspace file deliberately wins so several isolated Raiker instances
    can share one server process without sharing connector credentials.
    """
    return read_vault_key(workspace_root) or os.environ.get(VAULT_KEY_ENV, "").strip() or None


def vault_status(workspace_root: str | Path) -> str:
    """Return 'configured_valid' | 'missing' | 'invalid'.

    Reflects the effective key: the environment variable wins, then the file.
    """
    value = effective_vault_key(workspace_root)
    if value is None:
        return "missing"
    return "configured_valid" if _is_valid_fernet(value) else "invalid"
