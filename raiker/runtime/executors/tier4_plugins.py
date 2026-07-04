from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PluginExecutionRecord, ToolAction
from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore

_MAX_MANIFEST_BYTES = 1_000_000
_BROKERED_PLUGIN_TOOLS = frozenset({"read_file", "list_directory", "glob", "grep"})


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
    """Brokered read-only plugin tool invocation.

    This is not arbitrary plugin code execution: it only lets an installed
    plugin invoke a safe read-only broker tool that was present in its validated
    install permissions. No plugin files are imported, no subprocesses are
    launched, and no network or writes are allowed here.
    """

    capability = "plugin_execution_cap"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.policy.config import StaticPolicyConfig
        from raiker.policy.engine import PolicyEngine
        from raiker.tools.broker import ToolBroker

        plugin_id = action.arguments.get("plugin_id")
        tool_name = action.arguments.get("tool_name")
        tool_args = action.arguments.get("tool_args", {})
        entrypoint = action.arguments.get("entrypoint")
        if not isinstance(plugin_id, str) or not plugin_id.strip():
            return self._record_and_fail(
                action, principal, "", "", "missing_argument:plugin_id", tool_args={}
            )
        if not isinstance(tool_name, str) or not tool_name.strip():
            return self._record_and_fail(
                action, principal, plugin_id, "", "missing_argument:tool_name", tool_args={}
            )
        if not isinstance(tool_args, dict):
            return self._record_and_fail(
                action, principal, plugin_id, tool_name, "invalid_argument:tool_args", tool_args={}
            )

        install = self._latest_install(plugin_id)
        if install is None:
            return self._record_and_fail(
                action, principal, plugin_id, tool_name, "plugin_not_installed", tool_args=tool_args
            )

        permissions = self._permissions(install)
        if tool_name not in _BROKERED_PLUGIN_TOOLS:
            return self._record_and_fail(
                action,
                principal,
                plugin_id,
                tool_name,
                f"plugin_tool_not_brokered:{tool_name}",
                tool_args=tool_args,
                install=install,
            )
        if f"tool:{tool_name}" not in permissions:
            return self._record_and_fail(
                action,
                principal,
                plugin_id,
                tool_name,
                f"plugin_permission_not_granted:tool:{tool_name}",
                tool_args=tool_args,
                install=install,
            )

        tool_action = ToolAction(
            action_id=new_id("tool_"),
            tool_name=tool_name,
            arguments=dict(tool_args),
            risk_level="medium",
            requires_approval=False,
            proposed_by=principal.principal_id,
        )
        broker = ToolBroker(
            workspace_root=self._workspace_root,
            policy_engine=PolicyEngine(StaticPolicyConfig(self._workspace_root), store=self._store),
            store=self._store,
            writer=None,
        )
        tool_result, decision = broker.execute(
            tool_action,
            session_id=action.session_id or "plugin_execution",
            turn_id=action.turn_id,
        )
        execution_status = (
            "succeeded"
            if tool_result.status == "success"
            else ("denied" if decision.decision != "allow" or tool_result.status == "denied" else "failed")
        )
        record = self._record_execution(
            principal=principal,
            plugin_id=plugin_id,
            tool_name=tool_name,
            status=execution_status,
            install=install,
            entrypoint=entrypoint if isinstance(entrypoint, str) else f"tool:{tool_name}",
        )
        if tool_result.status != "success":
            reason = (
                "plugin_tool_policy_denied"
                if decision.decision != "allow" or tool_result.status == "denied"
                else "plugin_tool_failed"
            )
            return ExecutionResult(
                ok=False,
                capability=self.capability,
                action_id=action.action_id,
                reason_code=reason,
                summary="Plugin brokered tool invocation failed closed.",
                artifacts={
                    "execution_id": record.execution_id,
                    "plugin_id": plugin_id,
                    "tool_name": tool_name,
                    "tool_status": tool_result.status,
                    "policy_decision": decision.decision,
                },
            )

        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Installed plugin invoked a brokered read-only tool; output is not included in runtime artifacts.",
            artifacts={
                "execution_id": record.execution_id,
                "plugin_id": plugin_id,
                "tool_name": tool_name,
                "tool_status": tool_result.status,
                "policy_decision": decision.decision,
                "output_redacted": True,
            },
        )

    def _latest_install(self, plugin_id: str) -> dict[str, object] | None:
        for record in self._store.list_plugin_install_records(status="installed"):
            if record.get("plugin_id") == plugin_id:
                return record
        return None

    def _permissions(self, install: dict[str, object]) -> set[str]:
        raw = install.get("permissions_json")
        if not isinstance(raw, str):
            return set()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return set()
        if not isinstance(parsed, list):
            return set()
        return {value for value in parsed if isinstance(value, str)}

    def _record_and_fail(
        self,
        action: GovernedAction,
        principal: Principal,
        plugin_id: str,
        tool_name: str,
        reason_code: str,
        *,
        tool_args: dict[str, object],
        install: dict[str, object] | None = None,
    ) -> ExecutionResult:
        record = self._record_execution(
            principal=principal,
            plugin_id=plugin_id or "unknown",
            tool_name=tool_name or "unknown",
            status="denied",
            install=install,
            entrypoint=f"tool:{tool_name}" if tool_name else "unknown",
        )
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=reason_code,
            summary="Plugin brokered tool invocation failed closed.",
            artifacts={
                "execution_id": record.execution_id,
                "plugin_id": plugin_id or None,
                "tool_name": tool_name or None,
                "argument_count": len(tool_args),
            },
        )

    def _record_execution(
        self,
        *,
        principal: Principal,
        plugin_id: str,
        tool_name: str,
        status: str,
        install: dict[str, object] | None,
        entrypoint: str,
    ) -> PluginExecutionRecord:
        now = utc_now()
        record = PluginExecutionRecord(
            execution_id=new_id("plgex_"),
            plugin_id=plugin_id,
            version=str(install.get("version", "")) if install else "",
            trust_level=str(install.get("trust_level", "untrusted")) if install else "untrusted",
            permissions_json=str(install.get("permissions_json", "[]")) if install else "[]",
            entrypoint=entrypoint or f"tool:{tool_name}",
            status=status,
            started_at=now,
            completed_at=now,
            created_by=principal.principal_id,
        )
        self._store.insert_plugin_execution_record(record)
        return record
