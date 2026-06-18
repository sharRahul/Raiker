from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from raiker.tools.filesystem import resolve_workspace_path

_ALLOWED = {"status", "diff", "log"}


def run_git(workspace_root: str | Path, subcommand: str, args: list[str] | None = None, *, max_bytes: int = 200_000) -> dict[str, Any]:
    if subcommand not in _ALLOWED:
        return {"status": "denied", "error": {"type": "git_subcommand_denied", "subcommand": subcommand}}
    root = resolve_workspace_path(workspace_root, ".")
    command = ["git", "-C", str(root), subcommand, *(args or [])]
    proc = subprocess.run(command, check=False, capture_output=True, text=True, timeout=10)
    output = (proc.stdout + proc.stderr)[:max_bytes]
    return {"status": "success" if proc.returncode == 0 else "failed", "returncode": proc.returncode, "output": output, "truncated": len(proc.stdout + proc.stderr) > max_bytes}
