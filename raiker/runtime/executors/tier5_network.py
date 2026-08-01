from __future__ import annotations

import json
import os
import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, run_command
from raiker.storage.sqlite import SQLiteStore

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction

CommandRunner = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ProviderSpendSnapshot:
    """A provider-reported cumulative USD total, or an explicit unavailable state."""

    cumulative_cost: float | None
    reference: str = ""
    reason: str = ""


ProviderSpendReader = Callable[[dict[str, Any], str], ProviderSpendSnapshot]


def unavailable_daytona_spend(_config: dict[str, Any], _api_key: str) -> ProviderSpendSnapshot:
    # Daytona's documented organization usage API reports quota consumption,
    # not billed cost. Do not present that resource count as money. Deployments
    # can inject a billing adapter; until then the estimate stays reserved.
    return ProviderSpendSnapshot(None, reason="daytona_spend_api_unavailable")


class _NetworkExecutorBase:
    """Configured-profile executor with env-only credentials and bounded output."""

    capability = ""

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        *,
        runner: CommandRunner | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        self._runner = runner or run_command

    def _profile(
        self, action: GovernedAction, principal: Principal, expected_type: str
    ) -> tuple[dict[str, Any], dict[str, Any]] | ExecutionResult:
        profile_id = str(action.arguments.get("profile_id", "")) or self._store.selected_execution_environment(
            principal.principal_id
        )
        row = self._store.load_remote_execution_profile(
            profile_id, owner_principal_id=principal.principal_id
        )
        if row is None or not row["enabled"] or row["profile_type"] != expected_type:
            return ExecutionResult(
                False,
                self.capability,
                action.action_id,
                "execution_profile_unavailable",
                "Execution denied: the selected owner profile is unavailable.",
            )
        try:
            config = json.loads(row["config_json"])
        except (TypeError, ValueError):
            return ExecutionResult(
                False,
                self.capability,
                action.action_id,
                "invalid_execution_profile",
                "Execution denied: profile configuration is invalid.",
            )
        return row, config

    def _result(
        self, action: GovernedAction, profile_id: str, result: dict[str, Any], label: str
    ) -> ExecutionResult:
        code = int(result.get("returncode", 1))
        return ExecutionResult(
            code == 0,
            self.capability,
            action.action_id,
            None if code == 0 else f"exit_code:{code}",
            f"{label} exited {code}.",
            {
                "execution_profile_id": profile_id,
                "returncode": code,
                "stdout_bytes": result.get("stdout_bytes", 0),
                "stderr_bytes": result.get("stderr_bytes", 0),
                "truncated": result.get("truncated", False),
            },
        )


class RemoteExecutionExecutor(_NetworkExecutorBase):
    """Bounded OpenSSH executor for an owner-configured host profile."""

    capability = "remote_execution_cap"

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        loaded = self._profile(action, principal, "ssh")
        if isinstance(loaded, ExecutionResult):
            return loaded
        row, config = loaded
        host = str(config.get("host", ""))
        user = str(config.get("user", ""))
        credential_env = str(config.get("credential_env", ""))
        identity = os.environ.get(credential_env, "").strip() if credential_env else ""
        command = action.arguments.get("command", [])
        if isinstance(command, str):
            try:
                command = shlex.split(command, posix=True)
            except ValueError:
                command = []
        if (
            not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", user)
            or not identity
            or not Path(identity).is_file()
            or not isinstance(command, list)
            or not command
        ):
            return ExecutionResult(
                False,
                self.capability,
                action.action_id,
                "ssh_profile_not_ready",
                "SSH execution denied: profile, credential reference, or command is incomplete.",
            )
        timeout = min(max(float(action.arguments.get("timeout", 60)), 1), 300)
        ssh_command = [
            "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=10", "-i", identity, "--", f"{user}@{host}",
            *[str(part) for part in command],
        ]
        try:
            result = self._runner(
                ssh_command,
                timeout=timeout,
                max_output_bytes=200_000,
                allowlist=frozenset({"ssh"}),
                cwd=self._workspace_root,
            )
        except SandboxError as exc:
            return ExecutionResult(
                False, self.capability, action.action_id, str(exc), "SSH execution failed closed."
            )
        return self._result(action, str(row["profile_id"]), result, "SSH command")


class CloudExecutionExecutor(_NetworkExecutorBase):
    """Bounded Daytona CLI executor for an existing owner sandbox."""

    capability = "cloud_execution_cap"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        *,
        runner: CommandRunner | None = None,
        spend_reader: ProviderSpendReader | None = None,
    ) -> None:
        super().__init__(workspace_root, store, runner=runner)
        self._spend_reader = spend_reader or unavailable_daytona_spend

    def _spend(self, config: dict[str, Any], api_key: str) -> ProviderSpendSnapshot:
        try:
            snapshot = self._spend_reader(config, api_key)
            if snapshot.cumulative_cost is not None and snapshot.cumulative_cost < 0:
                return ProviderSpendSnapshot(None, reason="invalid_provider_spend")
            return snapshot
        except Exception:
            return ProviderSpendSnapshot(None, reason="provider_spend_read_failed")

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        loaded = self._profile(action, principal, "cloud")
        if isinstance(loaded, ExecutionResult):
            return loaded
        row, config = loaded
        sandbox_id = str(config.get("sandbox_id", "")).strip()
        key_env = str(config.get("api_key_env", ""))
        api_key = os.environ.get(key_env, "").strip() if key_env else ""
        command = action.arguments.get("command", [])
        if isinstance(command, str):
            try:
                command = shlex.split(command, posix=True)
            except ValueError:
                command = []
        estimated_cost = max(float(action.arguments.get("estimated_cost", 0)), 0)
        max_cost = max(float(config.get("max_cost", 0)), 0)
        if (
            not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", sandbox_id)
            or not api_key
            or not isinstance(command, list)
            or not command
        ):
            return ExecutionResult(
                False,
                self.capability,
                action.action_id,
                "daytona_profile_not_ready",
                "Daytona execution denied: sandbox, API-key reference, or command is incomplete.",
            )
        before = self._spend(config, api_key)
        if before.cumulative_cost is not None:
            self._store.record_cloud_execution_cost(
                owner_principal_id=principal.principal_id,
                profile_id=str(row["profile_id"]),
                action_id=action.action_id,
                event_type="provider_snapshot",
                amount=before.cumulative_cost,
                provider_reference=before.reference or None,
            )
        if not self._store.reserve_cloud_execution_cost(
            owner_principal_id=principal.principal_id,
            profile_id=str(row["profile_id"]),
            action_id=action.action_id,
            estimated_cost=estimated_cost,
            max_cost=max_cost,
        ):
            return ExecutionResult(
                False,
                self.capability,
                action.action_id,
                "cloud_execution_budget_exceeded",
                "Daytona execution denied: cumulative actual and reserved spend would exceed the owner budget.",
            )
        timeout = min(max(float(action.arguments.get("timeout", 60)), 1), 300)
        daytona_command = [
            "daytona", "exec", sandbox_id, "--timeout", str(int(timeout)), "--",
            *[str(part) for part in command],
        ]
        try:
            result = self._runner(
                daytona_command,
                timeout=timeout + 15,
                max_output_bytes=200_000,
                allowlist=frozenset({"daytona"}),
                cwd=self._workspace_root,
                env={"DAYTONA_API_KEY": api_key},
            )
        except SandboxError as exc:
            self._store.record_cloud_execution_cost(
                owner_principal_id=principal.principal_id,
                profile_id=str(row["profile_id"]),
                action_id=action.action_id,
                event_type="released",
                amount=estimated_cost,
                reason="execution_did_not_start",
            )
            return ExecutionResult(
                False,
                self.capability,
                action.action_id,
                str(exc),
                "Daytona execution failed closed.",
            )
        after = self._spend(config, api_key)
        if after.cumulative_cost is not None:
            self._store.record_cloud_execution_cost(
                owner_principal_id=principal.principal_id,
                profile_id=str(row["profile_id"]),
                action_id=action.action_id,
                event_type="provider_snapshot",
                amount=after.cumulative_cost,
                provider_reference=after.reference or None,
            )
        if before.cumulative_cost is not None and after.cumulative_cost is not None:
            self._store.record_cloud_execution_cost(
                owner_principal_id=principal.principal_id,
                profile_id=str(row["profile_id"]),
                action_id=action.action_id,
                event_type="reconciled",
                amount=max(after.cumulative_cost - before.cumulative_cost, 0),
                provider_reference=after.reference or None,
            )
        else:
            self._store.record_cloud_execution_cost(
                owner_principal_id=principal.principal_id,
                profile_id=str(row["profile_id"]),
                action_id=action.action_id,
                event_type="provider_unavailable",
                amount=estimated_cost,
                reason=after.reason or before.reason or "provider_spend_unavailable",
            )
        return self._result(action, str(row["profile_id"]), result, "Daytona command")
