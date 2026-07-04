from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult, not_implemented

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore

_MAX_MANIFEST_BYTES = 1_000_000


class PluginInstallExecutor:
    """Governed local plugin manifest install.

    This executor records a validated manifest in the install registry only. It
    does not fetch packages, unpack archives, import plugin code, or enable
    plugin execution.
    """

    capability = "plugin_install"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.plugins.policy import plan_plugin_registration
        from raiker.plugins.registry import record_plugin_install

        manifest_arg = action.arguments.get("manifest_path")
        if not isinstance(manifest_arg, str) or not manifest_arg.strip():
            return self._failed(action.action_id, "missing_argument:manifest_path")

        try:
            manifest_path = self._resolve_workspace_path(manifest_arg)
        except ValueError as exc:
            return self._failed(action.action_id, str(exc))

        if not manifest_path.is_file():
            return self._failed(action.action_id, "manifest_not_found")

        try:
            if manifest_path.stat().st_size > _MAX_MANIFEST_BYTES:
                return self._failed(action.action_id, "manifest_too_large")
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return self._failed(action.action_id, "manifest_json_invalid")
        except OSError:
            return self._failed(action.action_id, "manifest_read_failed")

        if not isinstance(raw_manifest, dict):
            return self._failed(action.action_id, "manifest_not_object")

        plan = plan_plugin_registration(raw_manifest)
        if plan.status != "planned":
            return ExecutionResult(
                ok=False,
                capability=self.capability,
                action_id=action.action_id,
                reason_code=f"plugin_install_plan_not_approved:{plan.status}",
                summary="Plugin manifest did not satisfy safe install policy.",
                artifacts={
                    "plugin_id": plan.plugin_id,
                    "status": plan.status,
                    "reason_count": len(plan.reasons),
                    "execution_enabled": False,
                },
            )

        if plan.plugin_id is None:
            return self._failed(action.action_id, "manifest_missing_plugin_id")

        supply_chain = raw_manifest.get("supply_chain")
        supply_chain_dict = supply_chain if isinstance(supply_chain, dict) else {}
        checksum = supply_chain_dict.get("checksum")
        signature = supply_chain_dict.get("signature")
        source_url = supply_chain_dict.get("source_url")
        commit_sha = supply_chain_dict.get("commit_sha")

        record = record_plugin_install(
            self._store,
            plugin_id=plan.plugin_id,
            version=str(raw_manifest["version"]),
            trust_level=plan.trust_level,
            permissions_json=json.dumps(plan.permissions, sort_keys=True),
            checksum=checksum if isinstance(checksum, str) else None,
            signature=signature if isinstance(signature, str) else None,
            source_url=source_url if isinstance(source_url, str) else None,
            commit_sha=commit_sha if isinstance(commit_sha, str) else None,
            status="installed",
            installed_by=principal.principal_id,
        )

        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Plugin manifest validated and install record created; execution remains disabled.",
            artifacts={
                "record_id": record.record_id,
                "plugin_id": plan.plugin_id,
                "version": record.version,
                "trust_level": plan.trust_level,
                "permission_count": len(plan.permissions),
                "execution_enabled": False,
            },
        )

    def _resolve_workspace_path(self, manifest_path: str) -> Path:
        candidate = Path(manifest_path)
        resolved = (
            candidate if candidate.is_absolute() else self._workspace_root / candidate
        ).resolve(strict=False)
        try:
            resolved.relative_to(self._workspace_root)
        except ValueError as exc:
            raise ValueError("outside_workspace:manifest_path") from exc
        return resolved

    def _failed(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Plugin manifest install failed closed.",
            artifacts={},
        )


class PluginExecutionCapExecutor:
    """Plugin code execution. Requires sandbox isolation + revocation before it
    can run untrusted plugin code; fails closed until then."""

    capability = "plugin_execution_cap"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return not_implemented(self.capability, action.action_id)
