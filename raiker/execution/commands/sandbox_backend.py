"""Which boundary sandboxed commands use on Windows: the account, or WSL2.

Windows has two command boundaries. The restricted account (the default) runs
Windows toolchains. WSL2 runs Linux toolchains under the same Bubblewrap and
seccomp boundary Linux uses, inside Raiker's own distribution. The owner picks
one in Settings › Runtime; every later command reads it at launch.

Commands *and* programs follow the choice. With WSL2 chosen, command hooks,
MCP servers and plugin code run the distribution's own interpreter (`python3`,
`node`, installed by its setup) inside the same boundary; with the account
chosen they run Windows interpreters there. (Until 2026-11-25 programs stayed
on the account whatever was chosen, and the account is off until its isolation
gaps close, so a Windows owner had an enforced boundary no program could use.)
On other platforms the setting is stored but has no effect.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from raiker.storage.internal_paths import internal_io_path

WindowsBackend = Literal["account", "wsl"]
WINDOWS_BACKENDS: tuple[WindowsBackend, ...] = ("account", "wsl")
DEFAULT_WINDOWS_BACKEND: WindowsBackend = "account"


def _settings_path(workspace_root: str | Path) -> Path:
    return internal_io_path(Path(workspace_root) / ".raiker" / "command-sandbox.json")


def stored_windows_backend(workspace_root: str | Path) -> WindowsBackend | None:
    """The owner's explicit choice, or None when they have not made one."""
    try:
        value = json.loads(_settings_path(workspace_root).read_text(encoding="utf-8"))
        choice = value.get("windows_backend")
    except (OSError, ValueError, AttributeError):
        return None
    return choice if choice in WINDOWS_BACKENDS else None


def load_windows_backend(workspace_root: str | Path) -> WindowsBackend:
    """The owner's choice; when unset, WSL2 if it is set up, else the account.

    The restricted account refuses to run anything until its isolation gaps
    close, so an owner who set WSL2 up (or whose machine already had it) but
    never opened the setting had every command refused. An unset choice now
    follows what is actually usable; an explicit one is always kept.
    """
    stored = stored_windows_backend(workspace_root)
    if stored is not None:
        return stored
    return "wsl" if _wsl_configured(workspace_root) else DEFAULT_WINDOWS_BACKEND


def _wsl_configured(workspace_root: str | Path) -> bool:
    if os.name != "nt":
        return False
    try:
        from raiker.execution.commands.backends.native import NativeSandboxDriver

        return NativeSandboxDriver(Path(workspace_root)).wsl_base() is not None
    except Exception:  # noqa: BLE001 — an unreadable status keeps the default
        return False


def save_windows_backend(workspace_root: str | Path, choice: str) -> WindowsBackend:
    if choice not in WINDOWS_BACKENDS:
        raise ValueError("command_sandbox_backend_invalid")
    path = _settings_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(".tmp")
    staged.write_text(json.dumps({"windows_backend": choice}), encoding="utf-8")
    os.replace(staged, path)
    return choice  # type: ignore[return-value]
