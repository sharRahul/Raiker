"""Keeping the connector vault key in the operating system's own key store.

DIST-08 (docs/adr/ADR-0003-desktop-distribution.md, "Secrets"). The connector
vault key encrypts every provider API key and OAuth token Raiker holds. Until
now it lived only in ``.raiker/vault.key`` at mode 0600 — protected by file
permissions, and readable by anything that runs as the owner or copies the
profile. A desktop installation can do better with what each platform already
provides:

==========  ===============================================================
Windows     DPAPI (``CryptProtectData``, user scope): the key file holds a
            blob only this Windows account on this machine can decrypt.
macOS       The login Keychain, through ``keyring``: the key file holds a
            reference, the key itself is a Keychain item.
Linux       The Secret Service (GNOME Keyring, KWallet), through ``keyring``;
            the key file holds a reference.
==========  ===============================================================

**Fallback policy, stated rather than implied.** When no usable store exists —
a headless Linux host with no Secret Service, a locked or refusing keyring, a
source checkout where protection is off — the key stays in the 0600 file
exactly as before, and the system check says so. An existing *protected* key
is never silently downgraded: if its store cannot be read, reading fails with
``vault_keystore_unavailable`` and nothing is regenerated, because a new key
would orphan every credential encrypted under the old one.

**Why the vault key and not the app key.** The app key derives the encrypted
database key and is the custody root for backups (``raiker/storage/backup.py``).
Making it depend on a keyring that a desktop reset can wipe would turn that
reset into the loss of every conversation and memory. Losing the vault key
loses only provider credentials, which the owner can enter again. The app key
stays a 0600 file; wrapping it is recorded as later work in the ADR.

Protection is on by default only in a packaged desktop build (``sys.frozen``)
and can be set explicitly with ``RAIKER_KEYSTORE=auto|off``.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

KEYSTORE_ENV = "RAIKER_KEYSTORE"
SERVICE = "org.raiker.desktop"
MARKER = "raiker-keystore:v1:"

Backend = Literal["dpapi", "keyring", "file"]


class KeystoreUnavailableError(RuntimeError):
    """A protected key exists but its store cannot be read right now."""

    def __init__(self) -> None:
        super().__init__("vault_keystore_unavailable")


@dataclass(frozen=True)
class KeystoreStatus:
    """What protects the vault key on this machine, said for the system check."""

    enabled: bool
    backend: Backend
    detail: str


def enabled() -> bool:
    value = os.environ.get(KEYSTORE_ENV, "").strip().lower()
    if value in {"off", "0", "false", "no"}:
        return False
    if value in {"auto", "on", "1", "true", "yes"}:
        return True
    return bool(getattr(sys, "frozen", False))


def is_protected(text: str) -> bool:
    return text.startswith(MARKER)


def _account(workspace_root: Path) -> str:
    """A stable per-workspace item name that does not reveal the path."""
    digest = hashlib.sha256(str(workspace_root.resolve()).encode("utf-8")).hexdigest()[:24]
    return f"vault-key:{digest}"


# ── Windows: DPAPI ──────────────────────────────────────────────────────


def _dpapi(data: bytes, *, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    buffer = ctypes.create_string_buffer(data, len(data))
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    result = Blob()
    # CRYPTPROTECT_UI_FORBIDDEN: never show a prompt from a background host.
    flags = 0x1
    call = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = call(ctypes.byref(source), None, None, None, None, flags, ctypes.byref(result))
    if not ok:
        raise OSError("dpapi_failed")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


# ── macOS and Linux: keyring ───────────────────────────────────────────


def _keyring():  # type: ignore[no-untyped-def]
    """The platform keyring, or ``None`` when there is no usable one."""
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return None
    try:
        backend = keyring.get_keyring()
    except Exception:  # noqa: BLE001 - a broken keyring config is "no keyring"
        return None
    if isinstance(backend, fail.Keyring) or getattr(backend, "priority", 0) <= 0:
        return None
    return backend


def status() -> KeystoreStatus:
    if not enabled():
        return KeystoreStatus(False, "file", "OS key store protection is off for this installation")
    if sys.platform == "win32":
        return KeystoreStatus(True, "dpapi", "Windows Data Protection (DPAPI), this user account")
    backend = _keyring()
    if backend is None:
        return KeystoreStatus(
            True, "file", "No OS key store is available, so the key is kept in a private (0600) file"
        )
    name = type(backend).__module__.rsplit(".", 1)[-1]
    label = {"macOS": "macOS Keychain", "SecretService": "Secret Service keyring",
             "kwallet": "KWallet"}.get(name, name)
    return KeystoreStatus(True, "keyring", label)


def protect(workspace_root: Path, key: str) -> str | None:
    """The text to store in the key file instead of *key*, or ``None`` to keep it plain.

    The value is read back before the reference is returned: a store that
    accepts a write and loses it must not be trusted with the only copy.
    """
    if not enabled():
        return None
    if sys.platform == "win32":
        try:
            blob = _dpapi(key.encode("ascii"), protect=True)
            if _dpapi(blob, protect=False).decode("ascii") != key:
                return None
        except OSError:
            return None
        return f"{MARKER}dpapi:{base64.b64encode(blob).decode('ascii')}"
    backend = _keyring()
    if backend is None:
        return None
    account = _account(workspace_root)
    try:
        backend.set_password(SERVICE, account, key)
        if backend.get_password(SERVICE, account) != key:
            return None
    except Exception:  # noqa: BLE001 - any refusal means "keep the file"
        return None
    return f"{MARKER}keyring:{account}"


def unprotect(text: str) -> str:
    """The key a protected reference stands for. Raises when it cannot be read."""
    body = text[len(MARKER):]
    kind, _, value = body.partition(":")
    try:
        if kind == "dpapi" and sys.platform == "win32":
            return _dpapi(base64.b64decode(value), protect=False).decode("ascii")
        if kind == "keyring":
            backend = _keyring()
            if backend is not None:
                found = backend.get_password(SERVICE, value)
                if found:
                    return str(found)
    except Exception as exc:  # noqa: BLE001 - reported as one stable reason
        raise KeystoreUnavailableError() from exc
    raise KeystoreUnavailableError()


def forget(text: str) -> None:
    """Remove the stored item a reference names. Best effort; a file is removed anyway."""
    body = text[len(MARKER):]
    kind, _, value = body.partition(":")
    if kind != "keyring":
        return
    backend = _keyring()
    if backend is None:
        return
    # Nothing left to delete is fine.
    with contextlib.suppress(Exception):
        backend.delete_password(SERVICE, value)


def forget_workspace(workspace_root: Path) -> None:
    """Remove this workspace's keyring item, for uninstall with data removal."""
    forget(f"{MARKER}keyring:{_account(workspace_root)}")
