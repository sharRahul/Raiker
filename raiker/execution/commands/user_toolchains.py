"""Interpreters installed in the owner's home by a toolchain manager.

The sandbox never mounts the owner's home: a home folder holds keys, tokens and
mail. That rule refused every interpreter uv, pyenv, nvm, mise or asdf put
there, so an MCP server written for a uv-managed Python failed its Test with
*its program was not found* (2026-11-19; again on the Windows test PC on
2026-11-25), though the owner could run it in a terminal.

The home stays out of reach. What changes is that one **install** inside a
recognised manager's store can be reached, read-only:

* Only the narrowest folder: the single version folder directly below a known
  store (``~/.local/share/uv/python/cpython-3.12.8-linux-x86_64-gnu``), never
  the store, the manager's own folder or the home.
* Only a folder holding no credential-shaped file anywhere inside it
  (``.npmrc``, ``credentials*``, ``.netrc``, ``*.pem``, ``id_*`` …), and no link
  that leaves it. A global ``npmrc`` with an auth token, for example, keeps that
  Node install refused.
* On Linux the folder is mounted read-only by the boundary (``toolchain_mounts``).
  On Windows and macOS, where the boundary is a separate account that cannot
  read the owner's profile, the install is copied once into Raiker's toolchain
  cache inside the sandbox's own base and run from there: nothing in the
  owner's profile is re-permissioned.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

#: Stores relative to the home folder; each child is one install.
_STORES: tuple[tuple[str, ...], ...] = (
    (".local", "share", "uv", "python"),
    ("AppData", "Roaming", "uv", "python"),
    ("Library", "Application Support", "uv", "python"),
    (".pyenv", "versions"),
    (".pyenv", "pyenv-win", "versions"),
    (".nvm", "versions", "node"),
    ("AppData", "Roaming", "nvm"),
    (".local", "share", "mise", "installs", "python"),
    (".local", "share", "mise", "installs", "node"),
    (".asdf", "installs", "python"),
    (".asdf", "installs", "nodejs"),
    (".volta", "tools", "image", "node"),
)

#: File names that hold, or usually hold, a secret.
_SECRET_NAMES = frozenset(
    {".npmrc", "npmrc", ".netrc", ".pypirc", "pip.conf", "pip.ini", ".git-credentials", ".env"}
)
_SECRET_PREFIXES = ("credentials", "id_rsa", "id_ed25519", "id_ecdsa", "secrets")
_SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".kdbx")

#: An install larger than this is not copied (Windows and macOS).
COPY_LIMIT_BYTES = 1024 * 1024 * 1024


def _home() -> Path:
    return Path.home().resolve()


def install_prefix(interpreter: Path, home: Path | None = None) -> Path | None:
    """The one install folder below a recognised store that holds *interpreter*."""
    base = (home or _home()).resolve()
    target = Path(os.path.abspath(interpreter))
    for store in _STORES:
        root = base.joinpath(*store)
        try:
            relative = target.relative_to(root)
        except ValueError:
            continue
        if len(relative.parts) < 2 or relative.parts[0] in {".", ".."}:
            return None
        return root / relative.parts[0]
    return None


def _walk(prefix: Path) -> Iterator[Path]:
    for directory, folders, files in os.walk(prefix, followlinks=False):
        here = Path(directory)
        for name in (*folders, *files):
            yield here / name


def refusal(prefix: Path) -> str | None:
    """Why *prefix* may not be reached, or ``None`` when it may."""
    if not prefix.is_dir() or prefix.is_symlink():
        return "user_toolchain_not_a_folder"
    resolved = prefix.resolve()
    for path in _walk(prefix):
        name = path.name.lower()
        if name in _SECRET_NAMES or name.startswith(_SECRET_PREFIXES) or name.endswith(_SECRET_SUFFIXES):
            return "user_toolchain_holds_credentials"
        if path.is_symlink():
            try:
                destination = path.resolve()
            except OSError:
                return "user_toolchain_link_unreadable"
            if destination != resolved and resolved not in destination.parents:
                return "user_toolchain_link_leaves_install"
    return None


def reachable_prefix(interpreter: Path, home: Path | None = None) -> Path | None:
    """The install folder of a home interpreter the sandbox may reach, if any."""
    prefix = install_prefix(interpreter, home)
    if prefix is None or refusal(prefix) is not None:
        return None
    return prefix


def needs_copy() -> bool:
    """Whether the boundary is an account that cannot read the owner's home."""
    return not sys.platform.startswith("linux")


def cached_copy(prefix: Path, cache_root: Path) -> Path:
    """*prefix* copied once into *cache_root*, keyed by its path and contents' sizes.

    A changed install (an upgrade in place) gets a new key, so a stale copy is
    never run. The copy is built beside its final name and renamed into place.
    """
    total = 0
    fingerprint = hashlib.sha256(str(prefix).encode("utf-8"))
    for path in sorted(_walk(prefix)):
        if path.is_file() and not path.is_symlink():
            size = path.stat().st_size
            total += size
            fingerprint.update(f"{path.relative_to(prefix).as_posix()}:{size}\n".encode())
    if total > COPY_LIMIT_BYTES:
        raise OSError("user_toolchain_too_large")
    destination = cache_root / f"{prefix.name}-{fingerprint.hexdigest()[:16]}"
    if destination.is_dir():
        return destination
    cache_root.mkdir(parents=True, exist_ok=True)
    staging = cache_root / f".{destination.name}.partial"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(prefix, staging, symlinks=True)
    try:
        staging.rename(destination)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        if not destination.is_dir():
            raise
    return destination
