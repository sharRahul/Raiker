from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
class PluginRegistrationPlan:
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "status": self.status,
            "reasons": list(self.reasons),
            "permissions": list(self.permissions),
            "trust_level": self.trust_level,
            "execution_enabled": self.execution_enabled,
            "entrypoints": self.entrypoints,
            "events": self.events,
            "contributions": dict(self.contributions),
            "signature": self.signature.to_dict() if self.signature is not None else None,
        }


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
