"""What an installed plugin is allowed to actually contribute (BUG-221).

Installing a plugin used to validate its manifest, check its supply chain,
resolve its signature and write a record — and then nothing happened. The
blocking question was never packaging; it was *what a plugin's code is allowed to
be*. Every other extension surface answers it: a skill is instructions and runs
nothing, a connector is a brokered tool behind a capability gate, a hook is argv
resolved inside the workspace under a bounded timeout.

This module answers it the same way, by refusing to invent an answer. A plugin
does not get an execution surface of its own. It contributes **through a surface
that already governs the thing it contributes**, and the first of those is hooks:

* A hook already has an execution model, a timeout, an audit trail and a scope.
* ``plugin`` sits below ``managed``, ``user``, ``project`` and ``local`` in
  :data:`~raiker.hooks.contracts.HOOK_SCOPES`, so a plugin rule can make an
  action stricter and can never override a deny the owner or their organisation
  set — the property that makes this safe is structural, not a check.
* The owner's global hooks off switch reaches it, because it is a hook.

Three refusals, all fail-closed and all named:

1. **No declared permission, no contribution.** A manifest must ask for
   ``event:hook``. That permission is not in ``SAFE_READ_ONLY``, so a plugin
   asking for it lands on ``pending_approval`` and the owner reads it in the
   permission diff *before* installing — which is the point of asking.
2. **A malformed contribution is refused at plan time,** not written and
   discovered later by a hooks file that silently loads nothing.
3. **The contribution is a file the owner can read and delete.** Revoking the
   plugin removes it, so "what does this plugin do" never depends on trusting the
   manifest that described it.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from raiker.hooks.contracts import HookConfigError
from raiker.hooks.registry import PLUGIN_HOOKS_DIR, PLUGIN_HOOKS_FILE, HooksRegistry

#: The permission a manifest must declare before any hook rule of its is written.
HOOK_CONTRIBUTION_PERMISSION = "event:hook"

#: A plugin id becomes a directory name, so it is held to a directory-safe shape
#: rather than sanitised into one. Sanitising invites two ids collapsing onto the
#: same folder; refusing does not.
_SAFE_PLUGIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class PluginContributionError(ValueError):
    """A contribution that cannot be accepted, with the reason as the message."""


def _hooks_block(manifest: dict[str, Any]) -> dict[str, Any] | None:
    """``contributes.hooks`` as a full hooks config, or ``None`` if absent.

    A manifest may write the event map directly (``{"PreToolUse": [...]}``) or a
    whole config (``{"schema_version": "1.0", "hooks": {...}}``). Both are
    normalised to the second form here, so exactly one shape reaches the parser
    and the written file is always a hooks config the registry can load without
    knowing a plugin produced it.
    """
    contributes = manifest.get("contributes")
    if not isinstance(contributes, dict):
        return None
    hooks = contributes.get("hooks")
    if not isinstance(hooks, dict):
        return None
    if isinstance(hooks.get("hooks"), dict):
        return {"schema_version": str(hooks.get("schema_version", "1.0")), "hooks": hooks["hooks"]}
    return {"schema_version": "1.0", "hooks": hooks}


def contribution_summary(manifest: dict[str, Any], permissions: list[str]) -> dict[str, Any]:
    """What this manifest contributes, and why it would be refused if it would.

    Returns a plain dict rather than raising, because this is what the owner reads
    on the plan *before* deciding. A refusal is information at that point, not an
    error: ``{"hooks": 0, "refused": ["..."]}`` is the honest rendering of a
    plugin that asked for something it may not have.
    """
    hooks = _hooks_block(manifest)
    if hooks is None:
        return {"hooks": 0, "events": [], "refused": []}
    refused: list[str] = []
    if HOOK_CONTRIBUTION_PERMISSION not in permissions:
        refused.append(f"hooks_contribution_requires_permission:{HOOK_CONTRIBUTION_PERMISSION}")
    events: list[str] = []
    count = 0
    try:
        rules = HooksRegistry.from_config(hooks, scope="plugin").rules
        events = sorted({rule.event for rule in rules})
        count = len(rules)
    except HookConfigError as exc:
        refused.append(f"invalid_hooks_contribution:{exc}")
    if refused:
        return {"hooks": 0, "events": [], "refused": refused}
    return {"hooks": count, "events": events, "refused": []}


def plugin_hooks_path(workspace_root: str | Path, plugin_id: str) -> Path:
    """Where this plugin's contributed rules live, refusing an unsafe id."""
    if not _SAFE_PLUGIN_ID.match(plugin_id or ""):
        raise PluginContributionError(f"unsafe_plugin_id:{plugin_id}")
    return Path(workspace_root) / PLUGIN_HOOKS_DIR / plugin_id / PLUGIN_HOOKS_FILE


def install_contributions(
    workspace_root: str | Path,
    manifest: dict[str, Any],
    *,
    plugin_id: str,
    permissions: list[str],
) -> dict[str, Any]:
    """Write this plugin's contributed hook rules, or refuse and write nothing.

    Idempotent: re-installing the same plugin replaces its file rather than
    accumulating a second one, because a plugin has exactly one contribution and
    a stale copy of an older version's rules would still be loaded.
    """
    summary = contribution_summary(manifest, permissions)
    if summary["refused"] or summary["hooks"] == 0:
        # Refused *or* empty — either way nothing is written, and a previous
        # version's rules do not survive an upgrade that dropped them.
        remove_contributions(workspace_root, plugin_id)
        return summary
    hooks = _hooks_block(manifest)
    assert hooks is not None  # summary["hooks"] > 0 implies a parsed block
    path = plugin_hooks_path(workspace_root, plugin_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(hooks, indent=2, sort_keys=True), encoding="utf-8")
    return {**summary, "path": str(path)}


def remove_contributions(workspace_root: str | Path, plugin_id: str) -> bool:
    """Remove everything this plugin contributed. Revocation's teeth.

    An install record flipped to ``revoked`` stops the brokered execution path,
    but a hooks file on disk is read by :meth:`HooksRegistry.load`, which has no
    store and no business gaining one. So revocation deletes the contribution
    rather than annotating it: the rules are gone at the next load, and there is
    no state in which the page says revoked and the runtime still runs the rule.
    """
    try:
        directory = plugin_hooks_path(workspace_root, plugin_id).parent
    except PluginContributionError:
        return False
    if not directory.is_dir():
        return False
    shutil.rmtree(directory, ignore_errors=True)
    return not directory.exists()


def installed_contributions(workspace_root: str | Path) -> dict[str, dict[str, Any]]:
    """What each plugin contributes *right now*, read from disk, keyed by id.

    Read from the files rather than from the install records on purpose: the
    files are what the runtime loads, so this cannot report a contribution the
    runtime does not have, or miss one it does.
    """
    root = Path(workspace_root) / PLUGIN_HOOKS_DIR
    found: dict[str, dict[str, Any]] = {}
    try:
        directories = sorted(entry for entry in root.iterdir() if entry.is_dir())
    except OSError:
        return found
    for directory in directories:
        path = directory / PLUGIN_HOOKS_FILE
        if not path.is_file():
            continue
        try:
            rules = HooksRegistry.from_config(
                json.loads(path.read_text(encoding="utf-8")), scope="plugin"
            ).rules
        except (OSError, ValueError, HookConfigError):
            found[directory.name] = {"hooks": 0, "events": [], "error": "unreadable"}
            continue
        found[directory.name] = {
            "hooks": len(rules),
            "events": sorted({rule.event for rule in rules}),
            "error": None,
        }
    return found


__all__ = [
    "HOOK_CONTRIBUTION_PERMISSION",
    "PluginContributionError",
    "contribution_summary",
    "install_contributions",
    "installed_contributions",
    "plugin_hooks_path",
    "remove_contributions",
]
