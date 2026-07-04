from __future__ import annotations

import os
from typing import Any

PLUGIN_DEPENDENCY_ALLOWLIST_ENV = "RAIKER_PLUGIN_DEPENDENCY_ALLOWLIST"

# Any of these in a version string means it is not an exact pin. Ranges,
# wildcards, and "latest" resolution are all rejected fail-closed: an install
# must name the exact dependency version it was reviewed against.
_RANGE_TOKENS = (">", "<", "=", "~", "^", "*", "x", "X", " ", ",", "||", "|", "!")
_UNPINNED_KEYWORDS = {"latest", "any", "current", "stable", ""}


def plugin_dependency_allowlist() -> frozenset[str]:
    """Owner-controlled allowlist of plugin IDs that may be declared as deps.

    Read from ``RAIKER_PLUGIN_DEPENDENCY_ALLOWLIST`` (comma-separated plugin
    IDs). Defaults to **empty** so a manifest that declares any dependency
    fails closed until the owner explicitly allowlists each dependency plugin
    ID — even when the ``plugin_install`` capability gate is on. A manifest with
    no dependencies is always fine.
    """
    raw = os.environ.get(PLUGIN_DEPENDENCY_ALLOWLIST_ENV, "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _resolve_dependency(entry: Any) -> tuple[str, str] | None:
    """Return ``(dep_id, version)`` for a dependency entry, or None if unparseable.

    Accepts object form ``{"plugin_id"|"id": str, "version": str}`` and string
    form ``"dep.id==1.2.3"`` / ``"dep.id@1.2.3"``. The version part may be an
    empty string here (that is caught as ``dependency_unpinned`` by the caller);
    only a structurally unusable entry returns None.
    """
    if isinstance(entry, dict):
        dep_id = entry.get("plugin_id") or entry.get("id")
        version = entry.get("version")
        if not isinstance(dep_id, str) or not dep_id.strip():
            return None
        return dep_id.strip(), version.strip() if isinstance(version, str) else ""
    if isinstance(entry, str) and entry.strip():
        text = entry.strip()
        for sep in ("==", "@"):
            if sep in text:
                dep_id, _, version = text.partition(sep)
                if dep_id.strip():
                    return dep_id.strip(), version.strip()
                return None
        # A bare plugin id with no version is structurally valid but unpinned.
        return text, ""
    return None


def _is_exact_pin(version: str) -> bool:
    if version.lower() in _UNPINNED_KEYWORDS:
        return False
    return not any(token in version for token in _RANGE_TOKENS)


def validate_plugin_dependencies(
    manifest: dict[str, Any], *, allowlist: frozenset[str]
) -> list[str]:
    """Fail-closed static validation of a manifest's declared dependencies.

    Returns a list of reason codes (empty = accepted). This never downloads,
    resolves transitively, or installs anything — it only inspects the declared
    ``dependencies`` array:

    - every dependency must resolve to an exact ``(plugin_id, version)`` pin
      (ranges / wildcards / "latest" are rejected as ``dependency_unpinned``);
    - every dependency plugin id must be on the owner allowlist
      (``dependency_not_allowlisted`` otherwise);
    - a missing/empty ``dependencies`` array is always accepted.
    """
    declared = manifest.get("dependencies", [])
    if declared in (None, []):
        return []
    if not isinstance(declared, list):
        return ["invalid_dependencies"]

    reasons: list[str] = []
    for entry in declared:
        resolved = _resolve_dependency(entry)
        if resolved is None:
            reasons.append("invalid_dependency_entry")
            continue
        dep_id, version = resolved
        if not _is_exact_pin(version):
            reasons.append(f"dependency_unpinned:{dep_id}")
            continue
        if dep_id not in allowlist:
            reasons.append(f"dependency_not_allowlisted:{dep_id}")
    return reasons
