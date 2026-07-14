from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PluginExecutionRecord, ToolAction
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, run_command

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore

_MAX_MANIFEST_BYTES = 1_000_000
_BROKERED_PLUGIN_TOOLS = frozenset({"read_file", "list_directory", "glob", "grep"})

# Plugin code runtime (Phase 4 slice 14): bounded subprocess execution of an
# installed plugin's declared entrypoint. Only interpreters on this allowlist may
# be launched, only for a plugin the owner has explicitly allowlisted, and only
# on a script that resolves inside the workspace root.
_PLUGIN_RUNTIME_INTERPRETERS = frozenset({"python3", "python", "node"})
_PLUGIN_RUNTIME_TIMEOUT = 30.0
_PLUGIN_RUNTIME_MAX_TIMEOUT = 120.0
_PLUGIN_RUNTIME_MAX_ARGS = 32
_PLUGIN_RUNTIME_MAX_OUTPUT_BYTES = 200_000

# Sandboxed (network-isolated) plugin code runtime (Phase 4 slice 16): run the
# plugin entrypoint inside an owner-allowlisted container with no network, a
# read-only rootfs, dropped capabilities, and only the single entrypoint file
# bind-mounted read-only.
_PLUGIN_SANDBOX_TIMEOUT = 60.0
_PLUGIN_SANDBOX_MAX_TIMEOUT = 300.0
_PLUGIN_SANDBOX_MOUNT_DIR = "/plugin"

CommandRunner = Callable[..., dict[str, Any]]


def plugin_runtime_image() -> str:
    """Owner-selected container image for sandboxed plugin runtime.

    Read from ``RAIKER_PLUGIN_RUNTIME_IMAGE``. Empty by default (fail closed) and
    must also appear in ``container_image_allowlist()`` — the same owner image
    allowlist the container executor uses — before any sandboxed plugin run.
    """
    return os.environ.get("RAIKER_PLUGIN_RUNTIME_IMAGE", "").strip()


def plugin_image_registry_allowlist() -> frozenset[str]:
    """Owner allowlist of registries permitted for sandbox image pulls."""
    raw = os.environ.get("RAIKER_PLUGIN_IMAGE_REGISTRY_ALLOWLIST", "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _image_registry(image: str) -> str:
    """Return the registry implied by an exact Docker image reference."""
    first = image.split("/", 1)[0]
    return first if "." in first or ":" in first or first == "localhost" else "docker.io"


def plugin_runtime_allowlist() -> frozenset[str]:
    """Owner allowlist of plugin ids permitted to run code (``plugin_runtime_cap``).

    Read from ``RAIKER_PLUGIN_RUNTIME_ALLOWLIST`` (comma-separated plugin ids).
    Defaults to **empty**, so no installed plugin can run code until the owner
    explicitly names it — fail closed even when the gate is on. This owner grant
    is the trust anchor for arbitrary plugin code execution: the install slice
    only ever records safe read-only permissions, so runtime authorization comes
    from the owner naming the plugin here, not from the manifest.
    """
    raw = os.environ.get("RAIKER_PLUGIN_RUNTIME_ALLOWLIST", "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def plugin_runtime_scopes() -> dict[str, str]:
    """Per-plugin workspace subpath scopes (``plugin_runtime_cap``, slice 15).

    Read from ``RAIKER_PLUGIN_RUNTIME_SCOPES`` as comma-separated
    ``<plugin_id>:<subpath>`` entries (e.g. ``local.runner:plugins/runner``).
    When a plugin has an entry, its entrypoint must resolve inside
    ``<workspace>/<subpath>`` — a tighter jail than the whole workspace — so the
    owner grant is not all-or-nothing. A plugin without an entry keeps the
    slice-14 behavior (entrypoint anywhere inside the workspace root). Malformed
    entries are ignored; an empty subpath is treated as "no scope".
    """
    raw = os.environ.get("RAIKER_PLUGIN_RUNTIME_SCOPES", "")
    scopes: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        plugin_id, _, subpath = entry.partition(":")
        plugin_id = plugin_id.strip()
        subpath = subpath.strip()
        if plugin_id and subpath:
            scopes[plugin_id] = subpath
    return scopes


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
            reason = (
                "plugin_revoked"
                if self._latest_record_status(plugin_id) == "revoked"
                else "plugin_not_installed"
            )
            return self._record_and_fail(
                action, principal, plugin_id, tool_name, reason, tool_args=tool_args
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

    def _latest_record_status(self, plugin_id: str) -> str | None:
        for record in self._store.list_plugin_install_records():
            if record.get("plugin_id") == plugin_id:
                status = record.get("status")
                return status if isinstance(status, str) else None
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


class PluginRevocationExecutor:
    """Governed revocation of an installed plugin.

    This is the fail-closed off-switch for the plugin install/execution slices.
    It flips the latest install record's status from ``installed`` to
    ``revoked`` so the plugin can no longer broker read-only tools through
    ``plugin_execution_cap``. It never deletes records, edits permissions,
    imports plugin code, runs scripts, opens the network, or writes files.
    """

    capability = "plugin_revocation_cap"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        plugin_id = action.arguments.get("plugin_id")
        reason = action.arguments.get("reason")
        if not isinstance(plugin_id, str) or not plugin_id.strip():
            return self._failed(action.action_id, "missing_argument:plugin_id")

        latest = self._latest_record(plugin_id)
        if latest is None:
            return self._failed(action.action_id, "plugin_not_installed")
        if latest.get("status") == "revoked":
            return self._failed(action.action_id, "plugin_already_revoked")
        if latest.get("status") != "installed":
            return self._failed(action.action_id, "plugin_not_installed")

        record_id = latest.get("record_id")
        if not isinstance(record_id, str) or not self._store.revoke_plugin_install_record(record_id):
            return self._failed(action.action_id, "plugin_revocation_failed")

        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Installed plugin revoked; brokered read-only execution is now denied for it.",
            artifacts={
                "record_id": record_id,
                "plugin_id": plugin_id,
                "previous_status": "installed",
                "new_status": "revoked",
                "reason_provided": isinstance(reason, str) and bool(reason.strip()),
                "execution_enabled": False,
            },
        )

    def _latest_record(self, plugin_id: str) -> dict[str, object] | None:
        for record in self._store.list_plugin_install_records():
            if record.get("plugin_id") == plugin_id:
                return record
        return None

    def _failed(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Plugin revocation failed closed.",
            artifacts={},
        )


class PluginRuntimeExecutor:
    """Governed execution of an installed plugin's declared entrypoint.

    This is the first slice that runs *arbitrary plugin code*, and it is bounded
    on every axis:

    - The plugin must have an ``installed`` (non-revoked) record from the
      governed ``plugin_install`` path.
    - The owner must have named the plugin in ``RAIKER_PLUGIN_RUNTIME_ALLOWLIST``
      (empty = fail closed). This owner grant — not the manifest — is what
      authorizes code execution.
    - Only interpreters on ``_PLUGIN_RUNTIME_INTERPRETERS`` may be launched, and
      only on an entrypoint that resolves inside the workspace root.
    - Execution is a bounded subprocess (timeout, output caps, workspace cwd) via
      the shared sandbox — the same isolation posture as ``shell_execution`` /
      ``process_execution``. It does **not** import plugin modules in-process,
      grant a network-namespace jail, or return stdout/stderr content: runtime
      artifacts are metadata only.

    Every attempt records a ``plugin_execution_records`` row.
    """

    capability = "plugin_runtime_cap"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        *,
        runner: CommandRunner | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        # Injectable so the execute path is testable without launching a process.
        self._runner: CommandRunner = runner or run_command

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        plugin_id = action.arguments.get("plugin_id")
        entrypoint = action.arguments.get("entrypoint")
        interpreter = action.arguments.get("interpreter", "python3")
        raw_args = action.arguments.get("args", [])

        if not isinstance(plugin_id, str) or not plugin_id.strip():
            return self._record_and_fail(action, principal, "", "missing_argument:plugin_id")
        if not isinstance(entrypoint, str) or not entrypoint.strip():
            return self._record_and_fail(action, principal, plugin_id, "missing_argument:entrypoint")
        if not isinstance(interpreter, str) or interpreter not in _PLUGIN_RUNTIME_INTERPRETERS:
            return self._record_and_fail(
                action, principal, plugin_id, f"interpreter_not_allowed:{interpreter}"
            )
        if not isinstance(raw_args, list) or any(not isinstance(part, str) for part in raw_args):
            return self._record_and_fail(action, principal, plugin_id, "invalid_argument:args")
        if len(raw_args) > _PLUGIN_RUNTIME_MAX_ARGS:
            return self._record_and_fail(action, principal, plugin_id, "too_many_args")

        install = self._latest_install(plugin_id)
        if install is None:
            reason = (
                "plugin_revoked"
                if self._latest_record_status(plugin_id) == "revoked"
                else "plugin_not_installed"
            )
            return self._record_and_fail(action, principal, plugin_id, reason)

        if plugin_id not in plugin_runtime_allowlist():
            return self._record_and_fail(
                action, principal, plugin_id, "plugin_runtime_not_allowlisted", install=install
            )

        try:
            script_path = self._resolve_workspace_path(entrypoint)
        except ValueError as exc:
            return self._record_and_fail(action, principal, plugin_id, str(exc), install=install)
        if not script_path.is_file():
            return self._record_and_fail(
                action, principal, plugin_id, "entrypoint_not_found", install=install
            )

        scope_error = self._check_plugin_scope(plugin_id, script_path)
        if scope_error is not None:
            return self._record_and_fail(
                action, principal, plugin_id, scope_error, install=install,
                entrypoint=str(script_path),
            )

        timeout = min(float(action.arguments.get("timeout", _PLUGIN_RUNTIME_TIMEOUT)), _PLUGIN_RUNTIME_MAX_TIMEOUT)
        command = [interpreter, str(script_path), *[str(part) for part in raw_args]]
        try:
            result = self._runner(
                command,
                timeout=timeout,
                max_output_bytes=_PLUGIN_RUNTIME_MAX_OUTPUT_BYTES,
                allowlist=_PLUGIN_RUNTIME_INTERPRETERS,
                cwd=self._workspace_root,
            )
        except SandboxError as exc:
            return self._record_and_fail(
                action, principal, plugin_id, f"plugin_runtime_sandbox:{exc}", install=install,
                entrypoint=str(script_path),
            )

        returncode = int(result.get("returncode", 1))
        status = "succeeded" if returncode == 0 else "failed"
        record = self._record_execution(
            principal=principal, plugin_id=plugin_id, status=status, install=install,
            entrypoint=str(script_path),
        )
        return ExecutionResult(
            ok=returncode == 0,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=None if returncode == 0 else f"plugin_runtime_exit:{returncode}",
            summary="Installed plugin entrypoint executed in a bounded subprocess; output is not included in runtime artifacts.",
            artifacts={
                "execution_id": record.execution_id,
                "plugin_id": plugin_id,
                "interpreter": interpreter,
                "returncode": returncode,
                "stdout_bytes": result.get("stdout_bytes", 0),
                "stderr_bytes": result.get("stderr_bytes", 0),
                "truncated": result.get("truncated", False),
                "output_redacted": True,
            },
        )

    def _resolve_workspace_path(self, entrypoint: str) -> Path:
        candidate = Path(entrypoint)
        resolved = (
            candidate if candidate.is_absolute() else self._workspace_root / candidate
        ).resolve(strict=False)
        try:
            resolved.relative_to(self._workspace_root)
        except ValueError as exc:
            raise ValueError("outside_workspace:entrypoint") from exc
        return resolved

    def _check_plugin_scope(self, plugin_id: str, script_path: Path) -> str | None:
        """Enforce an optional per-plugin workspace subpath jail (slice 15).

        Returns a fail-closed reason code, or ``None`` when the plugin has no
        configured scope (slice-14 workspace-root behavior) or the entrypoint is
        inside its scope. A configured subpath that escapes the workspace fails
        closed with ``plugin_scope_invalid``.
        """
        subpath = plugin_runtime_scopes().get(plugin_id)
        if not subpath:
            return None
        scope_root = (self._workspace_root / subpath).resolve(strict=False)
        try:
            scope_root.relative_to(self._workspace_root)
        except ValueError:
            return "plugin_scope_invalid"
        try:
            script_path.relative_to(scope_root)
        except ValueError:
            return "entrypoint_outside_plugin_scope"
        return None

    def _latest_install(self, plugin_id: str) -> dict[str, object] | None:
        for record in self._store.list_plugin_install_records(status="installed"):
            if record.get("plugin_id") == plugin_id:
                return record
        return None

    def _latest_record_status(self, plugin_id: str) -> str | None:
        for record in self._store.list_plugin_install_records():
            if record.get("plugin_id") == plugin_id:
                status = record.get("status")
                return status if isinstance(status, str) else None
        return None

    def _record_and_fail(
        self,
        action: GovernedAction,
        principal: Principal,
        plugin_id: str,
        reason_code: str,
        *,
        install: dict[str, object] | None = None,
        entrypoint: str = "",
    ) -> ExecutionResult:
        record = self._record_execution(
            principal=principal,
            plugin_id=plugin_id or "unknown",
            status="denied",
            install=install,
            entrypoint=entrypoint or "denied",
        )
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=reason_code,
            summary="Plugin code runtime failed closed.",
            artifacts={
                "execution_id": record.execution_id,
                "plugin_id": plugin_id or None,
            },
        )

    def _record_execution(
        self,
        *,
        principal: Principal,
        plugin_id: str,
        status: str,
        install: dict[str, object] | None,
        entrypoint: str,
    ) -> PluginExecutionRecord:
        now = utc_now()
        record = PluginExecutionRecord(
            execution_id=new_id("plgrt_"),
            plugin_id=plugin_id,
            version=str(install.get("version", "")) if install else "",
            trust_level=str(install.get("trust_level", "untrusted")) if install else "untrusted",
            permissions_json=str(install.get("permissions_json", "[]")) if install else "[]",
            entrypoint=entrypoint,
            status=status,
            started_at=now,
            completed_at=now,
            created_by=principal.principal_id,
        )
        self._store.insert_plugin_execution_record(record)
        return record


class PluginSandboxedRuntimeExecutor:
    """Network-isolated plugin code runtime (Phase 4 slice 16).

    Runs an installed, owner-allowlisted plugin's entrypoint **inside a
    container** with no network, a read-only rootfs, dropped capabilities, and
    only the single entrypoint file bind-mounted read-only at ``/plugin``. This
    is the stronger-isolation counterpart to ``plugin_runtime_cap`` (which runs a
    bare subprocess with the host's ambient network). It reuses the owner plugin
    allowlist (``RAIKER_PLUGIN_RUNTIME_ALLOWLIST``) and per-plugin scopes, and
    additionally requires an owner-allowlisted container image
    (``RAIKER_PLUGIN_RUNTIME_IMAGE`` in ``container_image_allowlist()``).

    It never mounts the workspace, opens the network, imports plugin modules
    in-process, or returns stdout/stderr content; artifacts are metadata only.
    """

    capability = "plugin_sandboxed_runtime_cap"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        *,
        runner: CommandRunner | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        self._runner: CommandRunner = runner or run_command

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.runtime.executors.containers import container_image_allowlist

        plugin_id = action.arguments.get("plugin_id")
        entrypoint = action.arguments.get("entrypoint")
        interpreter = action.arguments.get("interpreter", "python3")
        raw_args = action.arguments.get("args", [])

        if not isinstance(plugin_id, str) or not plugin_id.strip():
            return self._record_and_fail(action, principal, "", "missing_argument:plugin_id")
        if not isinstance(entrypoint, str) or not entrypoint.strip():
            return self._record_and_fail(action, principal, plugin_id, "missing_argument:entrypoint")
        if not isinstance(interpreter, str) or interpreter not in _PLUGIN_RUNTIME_INTERPRETERS:
            return self._record_and_fail(
                action, principal, plugin_id, f"interpreter_not_allowed:{interpreter}"
            )
        if not isinstance(raw_args, list) or any(not isinstance(part, str) for part in raw_args):
            return self._record_and_fail(action, principal, plugin_id, "invalid_argument:args")
        if len(raw_args) > _PLUGIN_RUNTIME_MAX_ARGS:
            return self._record_and_fail(action, principal, plugin_id, "too_many_args")

        install = self._latest_install(plugin_id)
        if install is None:
            reason = (
                "plugin_revoked"
                if self._latest_record_status(plugin_id) == "revoked"
                else "plugin_not_installed"
            )
            return self._record_and_fail(action, principal, plugin_id, reason)

        if plugin_id not in plugin_runtime_allowlist():
            return self._record_and_fail(
                action, principal, plugin_id, "plugin_runtime_not_allowlisted", install=install
            )

        image = plugin_runtime_image()
        if not image:
            return self._record_and_fail(
                action, principal, plugin_id, "plugin_runtime_image_unset", install=install
            )
        if image not in container_image_allowlist():
            return self._record_and_fail(
                action, principal, plugin_id, "image_not_allowed", install=install
            )

        try:
            script_path = self._resolve_workspace_path(entrypoint)
        except ValueError as exc:
            return self._record_and_fail(action, principal, plugin_id, str(exc), install=install)
        if not script_path.is_file():
            return self._record_and_fail(
                action, principal, plugin_id, "entrypoint_not_found", install=install
            )

        scope_error = self._check_plugin_scope(plugin_id, script_path)
        if scope_error is not None:
            return self._record_and_fail(
                action, principal, plugin_id, scope_error, install=install,
                entrypoint=str(script_path),
            )

        timeout = min(
            float(action.arguments.get("timeout", _PLUGIN_SANDBOX_TIMEOUT)),
            _PLUGIN_SANDBOX_MAX_TIMEOUT,
        )
        mount_target = f"{_PLUGIN_SANDBOX_MOUNT_DIR}/{script_path.name}"
        docker_command = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1",
            "--pids-limit", "256",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "-v", f"{script_path}:{mount_target}:ro",
            "-w", _PLUGIN_SANDBOX_MOUNT_DIR,
            image,
            interpreter, mount_target, *[str(part) for part in raw_args],
        ]
        try:
            result = self._runner(
                docker_command,
                timeout=timeout,
                max_output_bytes=_PLUGIN_RUNTIME_MAX_OUTPUT_BYTES,
                allowlist=frozenset({"docker"}),
                cwd=self._workspace_root,
            )
        except SandboxError as exc:
            code = str(exc)
            if code.startswith("command_not_found"):
                code = "docker_unavailable"
            return self._record_and_fail(
                action, principal, plugin_id, f"plugin_sandbox:{code}", install=install,
                entrypoint=str(script_path),
            )

        returncode = int(result.get("returncode", 1))
        status = "succeeded" if returncode == 0 else "failed"
        record = self._record_execution(
            principal=principal, plugin_id=plugin_id, status=status, install=install,
            entrypoint=str(script_path),
        )
        return ExecutionResult(
            ok=returncode == 0,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=None if returncode == 0 else f"plugin_sandbox_exit:{returncode}",
            summary="Installed plugin entrypoint executed in a no-network container; output is not included in runtime artifacts.",
            artifacts={
                "execution_id": record.execution_id,
                "plugin_id": plugin_id,
                "image": image,
                "interpreter": interpreter,
                "network_isolated": True,
                "returncode": returncode,
                "stdout_bytes": result.get("stdout_bytes", 0),
                "stderr_bytes": result.get("stderr_bytes", 0),
                "truncated": result.get("truncated", False),
                "output_redacted": True,
            },
        )

    def _resolve_workspace_path(self, entrypoint: str) -> Path:
        candidate = Path(entrypoint)
        resolved = (
            candidate if candidate.is_absolute() else self._workspace_root / candidate
        ).resolve(strict=False)
        try:
            resolved.relative_to(self._workspace_root)
        except ValueError as exc:
            raise ValueError("outside_workspace:entrypoint") from exc
        return resolved

    def _check_plugin_scope(self, plugin_id: str, script_path: Path) -> str | None:
        subpath = plugin_runtime_scopes().get(plugin_id)
        if not subpath:
            return None
        scope_root = (self._workspace_root / subpath).resolve(strict=False)
        try:
            scope_root.relative_to(self._workspace_root)
        except ValueError:
            return "plugin_scope_invalid"
        try:
            script_path.relative_to(scope_root)
        except ValueError:
            return "entrypoint_outside_plugin_scope"
        return None

    def _latest_install(self, plugin_id: str) -> dict[str, object] | None:
        for record in self._store.list_plugin_install_records(status="installed"):
            if record.get("plugin_id") == plugin_id:
                return record
        return None

    def _latest_record_status(self, plugin_id: str) -> str | None:
        for record in self._store.list_plugin_install_records():
            if record.get("plugin_id") == plugin_id:
                status = record.get("status")
                return status if isinstance(status, str) else None
        return None

    def _record_and_fail(
        self,
        action: GovernedAction,
        principal: Principal,
        plugin_id: str,
        reason_code: str,
        *,
        install: dict[str, object] | None = None,
        entrypoint: str = "",
    ) -> ExecutionResult:
        record = self._record_execution(
            principal=principal,
            plugin_id=plugin_id or "unknown",
            status="denied",
            install=install,
            entrypoint=entrypoint or "denied",
        )
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=reason_code,
            summary="Sandboxed plugin code runtime failed closed.",
            artifacts={
                "execution_id": record.execution_id,
                "plugin_id": plugin_id or None,
            },
        )

    def _record_execution(
        self,
        *,
        principal: Principal,
        plugin_id: str,
        status: str,
        install: dict[str, object] | None,
        entrypoint: str,
    ) -> PluginExecutionRecord:
        now = utc_now()
        record = PluginExecutionRecord(
            execution_id=new_id("plgrt_"),
            plugin_id=plugin_id,
            version=str(install.get("version", "")) if install else "",
            trust_level=str(install.get("trust_level", "untrusted")) if install else "untrusted",
            permissions_json=str(install.get("permissions_json", "[]")) if install else "[]",
            entrypoint=entrypoint,
            status=status,
            started_at=now,
            completed_at=now,
            created_by=principal.principal_id,
        )
        self._store.insert_plugin_execution_record(record)
        return record


class PluginSandboxImagePullExecutor:
    """Pull one owner-allowlisted sandbox image without running it."""

    capability = "plugin_sandbox_image_pull_cap"

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        runner: CommandRunner | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._runner: CommandRunner = runner or run_command

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.runtime.executors.containers import container_image_allowlist

        raw_image = action.arguments.get("image")
        if not isinstance(raw_image, str) or not raw_image.strip():
            return self._failed(action, "missing_argument:image")
        image = raw_image.strip()
        if image not in container_image_allowlist():
            return self._failed(action, "image_not_allowed")
        registry = _image_registry(image)
        if registry not in plugin_image_registry_allowlist():
            return self._failed(action, "image_registry_not_allowed")
        try:
            result = self._runner(
                ["docker", "pull", image],
                timeout=_PLUGIN_SANDBOX_MAX_TIMEOUT,
                max_output_bytes=_PLUGIN_RUNTIME_MAX_OUTPUT_BYTES,
                allowlist=frozenset({"docker"}),
                cwd=self._workspace_root,
            )
        except SandboxError as exc:
            code = "docker_unavailable" if str(exc).startswith("command_not_found") else str(exc)
            return self._failed(action, code)
        returncode = int(result.get("returncode", 1))
        return ExecutionResult(
            ok=returncode == 0,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=None if returncode == 0 else f"plugin_image_pull_exit:{returncode}",
            summary="Owner-allowlisted sandbox image pulled; output is not included in runtime artifacts.",
            artifacts={
                "image": image,
                "registry": registry,
                "returncode": returncode,
                "stdout_bytes": result.get("stdout_bytes", 0),
                "stderr_bytes": result.get("stderr_bytes", 0),
                "truncated": result.get("truncated", False),
                "output_redacted": True,
            },
        )

    def _failed(self, action: GovernedAction, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=reason_code,
            summary="Sandbox image pull failed closed.",
        )
