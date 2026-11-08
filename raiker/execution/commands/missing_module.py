"""Why a sandboxed check could not import a module the owner has installed.

BD-5, 2026-11-08: the sandbox ran the system Python, which could not see the
owner's per-user site-packages (``%APPDATA%\\Python`` on Windows,
``~/.local/lib/pythonX.Y`` elsewhere), so ``python -m pytest`` failed with
*No module named pytest* although pytest was installed for the owner. That is
by design: the sandbox never reads the owner's home. What was wrong is that
the failure gave no reason the owner could act on.

This reads the failure, never the owner's files beyond a name lookup: it looks
for the missing top-level module in the owner's own per-user site folders and,
when it is there, says so and names the two fixes. Nothing is mounted, copied
or widened; the boundary is unchanged.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path

_MISSING = re.compile(r"No module named ['\"]?(?P<name>[A-Za-z_][A-Za-z0-9_.]*)['\"]?")


def missing_module(output: str) -> str | None:
    """The top-level module a Python failure could not import, or ``None``."""
    match = _MISSING.search(output)
    return match.group("name").split(".")[0] if match else None


def user_site_folders(home: Path | None = None) -> list[Path]:
    """The owner's per-user ``site-packages`` folders, every Python version."""
    home = home or Path.home()
    roots: list[Path] = []
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        roots = [folder / "site-packages" for folder in sorted((base / "Python").glob("Python3*"))]
    else:
        roots = sorted((home / ".local" / "lib").glob("python3*/site-packages"))
        roots += sorted((home / "Library" / "Python").glob("3*/lib/python/site-packages"))
    return [root for root in roots if root.is_dir()]


def _installed_in(name: str, folders: Iterable[Path]) -> bool:
    for folder in folders:
        if (folder / name).is_dir() or (folder / f"{name}.py").is_file():
            return True
        if any(folder.glob(f"{name}-*.dist-info")):
            return True
    return False


def missing_module_note(output: str, folders: Iterable[Path] | None = None) -> str | None:
    """A sentence for the owner when the sandbox lacks a module they installed for themselves."""
    name = missing_module(output)
    if name is None:
        return None
    if not _installed_in(name, user_site_folders() if folders is None else folders):
        return None
    return (
        f"The sandbox could not import {name}: it is installed for your account only, and "
        "the sandbox never reads your home folder. Install it for all users (or in the "
        "project's own environment), or run checks with a backend that has it."
    )
