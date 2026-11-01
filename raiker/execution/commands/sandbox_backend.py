"""Which boundary sandboxed commands use on Windows: the account, or WSL2.

Windows has two command boundaries. The restricted account (the default) runs
Windows toolchains. WSL2 runs Linux toolchains under the same Bubblewrap and
seccomp boundary Linux uses, inside Raiker's own distribution. The owner picks
one in Settings › Runtime; every later command reads it at launch.

Only *commands* follow the choice. Command hooks, MCP servers and plugin code
run Windows interpreters, so they stay on the restricted account whichever is
chosen. On other platforms the setting is stored but has no effect.
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


def load_windows_backend(workspace_root: str | Path) -> WindowsBackend:
    """The owner's choice; the account when unset or unreadable."""
    try:
        value = json.loads(_settings_path(workspace_root).read_text(encoding="utf-8"))
        choice = value.get("windows_backend")
    except (OSError, ValueError, AttributeError):
        return DEFAULT_WINDOWS_BACKEND
    return choice if choice in WINDOWS_BACKENDS else DEFAULT_WINDOWS_BACKEND


def save_windows_backend(workspace_root: str | Path, choice: str) -> WindowsBackend:
    if choice not in WINDOWS_BACKENDS:
        raise ValueError("command_sandbox_backend_invalid")
    path = _settings_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(".tmp")
    staged.write_text(json.dumps({"windows_backend": choice}), encoding="utf-8")
    os.replace(staged, path)
    return choice  # type: ignore[return-value]
