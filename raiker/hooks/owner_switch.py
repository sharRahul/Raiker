"""The owner's off switch for every hook (BUG-222).

Hooks load from three files, and one of them — ``config/hooks.json`` — travels
with a repository. Cloning a project can therefore bring rules that run commands
on the owner's machine: bounded, argv-only and resolved inside the workspace, but
still theirs to refuse. Editing someone else's checked-in file is not a refusal,
so the switch is an **owner setting**, deliberately kept out of all three config
files so that a file a project ships cannot re-enable itself.

Off by default. Hooks that are configured run, which is what configuring them
meant; the switch exists to be reachable, not to be the posture.

This lives in the runtime layer rather than beside the settings route because the
gateway consumes it, and the gateway must not import the HTTP layer to answer a
question about its own behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raiker.storage.sqlite import SQLiteStore


def _settings(workspace: str | Path, principal_id: str) -> dict[str, Any]:
    row = SQLiteStore(workspace).get_user_settings(principal_id)
    if row is None:
        return {}
    try:
        parsed = json.loads(row["settings_json"])
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def hooks_disabled(workspace: str | Path, principal_id: str) -> bool:
    """True when this owner has turned every hook off."""
    hooks = _settings(workspace, principal_id).get("hooks")
    return isinstance(hooks, dict) and hooks.get("disabled") is True
