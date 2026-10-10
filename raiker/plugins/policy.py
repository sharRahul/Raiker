from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from raiker.contracts.views import View
from raiker.plugins.contributions import contribution_summary
from raiker.plugins.dependencies import (
    plugin_dependency_allowlist,
    validate_plugin_dependencies,
)
from raiker.plugins.manifest import PluginManifestValidation, validate_plugin_manifest
from raiker.plugins.verify import (
    SignatureVerification,
    signature_verification,
    validate_supply_chain,
)

SAFE_READ_ONLY = {
    "tool:read_file",
    "tool:list_directory",
    "tool:glob",
    "tool:grep",
    "event:read",
    "ui:panel",
    "memory:read",
}
RISKY_APPROVAL_PREFIXES = (
    "tool:shell",
    "tool:write_file",
    "tool:edit_file",
    "tool:apply_patch",
    "network:",
    "filesystem:write",
)
DENIED_PREFIXES = ("subprocess:", "import:", "eval:", "exec:", "path:", "../", "/")
KNOWN_TRUST_LEVELS = {"untrusted", "local_dev", "project", "managed", "bundled"}


@dataclass(frozen=True)
class PluginRegistrationPlan(View):
    plugin_id: str | None
    status: str
    reasons: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    trust_level: str = "untrusted"
    execution_enabled: bool = False
    entrypoints: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    # BUG-221 — what this plugin would actually provide once installed, and the
    # named reason when it would provide nothing. `execution_enabled` stays False
    # because a plugin still runs no code of its own; a contribution arrives
    # through a surface that already governs it, which is a different claim.
    contributions: dict[str, Any] = field(default_factory=dict)
    # BUG-79 — what the manifest's signature actually proved. Carried on the plan
    # so the permission diff the owner reads states it alongside the permissions,
    # rather than leaving `verified` and `present only` looking identical.
    signature: SignatureVerification | None = None


@dataclass(frozen=True)
class PluginPermissionDiff(View):
    """What installing a manifest changes about a plugin already installed (DEC-15 step 10).

    ``previous_version`` is ``None`` for a first install, where every permission
    is new by definition and the plan itself is the review. For an update,
    ``added`` is the authority the new version asks for that the installed one
    did not have: when it is not empty the update grows the plugin's authority,
    and the install executor refuses it unless the owner accepted exactly the
    permission set they were shown.
    """

    previous_version: str | None
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    @property
    def authority_grows(self) -> bool:
        return self.previous_version is not None and bool(self.added)


def installed_plugin_permissions(store: Any, plugin_id: str) -> tuple[str, list[str]] | None:
    """The installed version of ``plugin_id`` and its permissions, or ``None``."""
    import json

    for record in store.list_plugin_install_records(status="installed"):
        if record.get("plugin_id") != plugin_id:
            continue
        try:
            permissions = json.loads(str(record.get("permissions_json") or "[]"))
        except ValueError:
            permissions = []
        clean = [p for p in permissions if isinstance(p, str)] if isinstance(permissions, list) else []
        return str(record.get("version") or ""), clean
    return None


def plugin_permission_diff(store: Any, plugin_id: str, permissions: list[str]) -> PluginPermissionDiff:
    installed = installed_plugin_permissions(store, plugin_id)
    if installed is None:
        return PluginPermissionDiff(previous_version=None)
    version, before = installed
    return PluginPermissionDiff(
        previous_version=version,
        added=sorted(set(permissions) - set(before)),
        removed=sorted(set(before) - set(permissions)),
    )


def plan_plugin_registration(manifest: dict[str, Any]) -> PluginRegistrationPlan:
    validation: PluginManifestValidation = validate_plugin_manifest(manifest)
    trust_level_value = manifest.get("trust_level", "untrusted")
    trust_level = trust_level_value if isinstance(trust_level_value, str) else "invalid"
    reasons = list(validation.errors)
    if trust_level not in KNOWN_TRUST_LEVELS:
        reasons.append(f"unknown_trust_level:{trust_level}")
    permissions = validation.permissions
    supply_chain_reasons = validate_supply_chain(manifest)
    reasons.extend(supply_chain_reasons)
    signature = signature_verification(manifest)
    dependency_reasons = validate_plugin_dependencies(
        manifest, allowlist=plugin_dependency_allowlist()
    )
    reasons.extend(dependency_reasons)
    for permission in permissions:
        if permission.startswith(DENIED_PREFIXES) or any(
            token in permission for token in ("..", "$(", "`;", "__import__")
        ):
            reasons.append(f"unsafe_permission:{permission}")
    status = "planned"
    if reasons:
        status = "denied"
    elif any(permission.startswith(RISKY_APPROVAL_PREFIXES) for permission in permissions):
        status = "pending_approval"
        reasons.append("risky_permissions_require_explicit_policy")
    elif all(permission in SAFE_READ_ONLY for permission in permissions):
        status = "planned"
    else:
        status = "pending_approval"
        reasons.append("unknown_permission_requires_policy")
    event_type = (
        "phase3.plugin.registration.denied"
        if status == "denied"
        else "phase3.plugin.registration.planned"
    )
    contributions = contribution_summary(manifest, permissions)
    return PluginRegistrationPlan(
        plugin_id=validation.plugin_id,
        status=status,
        reasons=reasons,
        permissions=permissions,
        trust_level=trust_level,
        execution_enabled=False,
        entrypoints=manifest.get("entrypoints", {})
        if isinstance(manifest.get("entrypoints", {}), dict)
        else {},
        events=[
            {
                "event_type": "phase3.plugin.manifest.validated",
                "payload": {"plugin_id": validation.plugin_id, "valid": validation.valid},
            },
            {
                "event_type": event_type,
                "payload": {
                    "plugin_id": validation.plugin_id,
                    "status": status,
                    "execution_enabled": False,
                    "signature_level": signature.level,
                    "signature_reason": signature.reason,
                    "contributed_hooks": contributions.get("hooks", 0),
                    "contributions_refused": contributions.get("refused", []),
                },
            },
        ],
        signature=signature,
        contributions=contributions,
    )
