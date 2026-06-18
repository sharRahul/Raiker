from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_FIELDS = {"name", "version", "permissions"}
ALLOWED_PERMISSION_PREFIXES = ("tool:", "event:", "ui:", "memory:", "network:", "filesystem:")


@dataclass(frozen=True)
class PluginManifestValidation:
    plugin_id: str | None
    valid: bool
    errors: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    execution_enabled: bool = False


def _permission_to_string(permission: Any) -> str | None:
    if isinstance(permission, str):
        return permission
    if isinstance(permission, dict):
        tool = permission.get("tool")
        if isinstance(tool, str) and tool.strip():
            return f"tool:{tool}"
        kind = permission.get("kind")
        name = permission.get("name")
        if isinstance(kind, str) and isinstance(name, str) and kind.strip() and name.strip():
            return f"{kind}:{name}"
    return None


def validate_plugin_manifest(manifest: dict[str, Any]) -> PluginManifestValidation:
    """Validate a plugin manifest without loading or executing plugin code."""
    errors: list[str] = []
    id_field = "plugin_id" if "plugin_id" in manifest else "id"
    required = set(REQUIRED_FIELDS) | {id_field}
    missing = sorted(required - set(manifest))
    if missing:
        errors.append(f"missing_fields:{','.join(missing)}")

    plugin_id = manifest.get(id_field)
    if plugin_id is not None and (not isinstance(plugin_id, str) or not plugin_id.strip()):
        errors.append("invalid_id")

    version = manifest.get("version")
    if version is not None and (not isinstance(version, str) or not version.strip()):
        errors.append("invalid_version")

    permissions_value = manifest.get("permissions", [])
    permissions: list[str] = []
    if not isinstance(permissions_value, list):
        errors.append("invalid_permissions")
    else:
        parsed = [_permission_to_string(item) for item in permissions_value]
        if not all(parsed):
            errors.append("invalid_permissions")
        else:
            permissions = [item for item in parsed if item is not None]
            invalid = [item for item in permissions if not item.startswith(ALLOWED_PERMISSION_PREFIXES)]
            if invalid:
                errors.append(f"unsupported_permissions:{','.join(sorted(invalid))}")

    return PluginManifestValidation(
        plugin_id=plugin_id if isinstance(plugin_id, str) else None,
        valid=not errors,
        errors=errors,
        permissions=permissions,
        execution_enabled=False,
    )
