from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, run_command

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction

# Local container execution (Phase 4 slice 3), sandboxed-first: run an
# owner-allowlisted image with no network, dropped capabilities, no host mounts,
# memory/cpu/pid limits, a read-only rootfs, and a timeout. Remote/cloud
# execution stays fail-closed (tier5_network). Only images the owner explicitly
# allowlists can run; an empty allowlist denies everything (fail closed).

CONTAINER_RUN_TIMEOUT = 60.0
_MAX_TIMEOUT = 300.0

CommandRunner = Callable[..., dict[str, Any]]


def container_image_allowlist() -> frozenset[str]:
    raw = os.environ.get("RAIKER_CONTAINER_IMAGE_ALLOWLIST", "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


class ContainerExecutionExecutor:
    """Real executor for ``container_execution_cap`` — bounded local Docker run."""

    capability = "container_execution_cap"

    def __init__(self, workspace_root: str | Path, *, runner: CommandRunner | None = None) -> None:
        self._ws = Path(workspace_root).resolve()
        # Injectable so the execute path is testable without a live daemon.
        self._runner: CommandRunner = runner or run_command

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        image = str(action.arguments.get("image", "")).strip()
        command: list[str] = [str(part) for part in action.arguments.get("command", [])]
        if not image:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:image",
                summary="Container execution denied: no image provided.",
            )
        allowlist = container_image_allowlist()
        if not allowlist or image not in allowlist:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="image_not_allowed",
                summary="Container execution denied: image is not in the owner allowlist.",
            )
        timeout = min(float(action.arguments.get("timeout", CONTAINER_RUN_TIMEOUT)), _MAX_TIMEOUT)
        docker_command = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1",
            "--pids-limit", "256",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            image,
            *command,
        ]
        try:
            result = self._runner(
                docker_command,
                timeout=timeout,
                max_output_bytes=200_000,
                allowlist=frozenset({"docker"}),
                cwd=self._ws,
            )
        except SandboxError as exc:
            code = str(exc)
            if code.startswith("command_not_found"):
                code = "docker_unavailable"
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=code,
                summary="Container execution blocked (sandbox/daemon).",
            )
        returncode = int(result.get("returncode", 1))
        return ExecutionResult(
            ok=returncode == 0,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=None if returncode == 0 else f"exit_code:{returncode}",
            summary=f"Container '{image}' exited {returncode}.",
            # Metadata only — never stdout/stderr content.
            artifacts={
                "image": image,
                "returncode": returncode,
                "stdout_bytes": result.get("stdout_bytes", 0),
                "stderr_bytes": result.get("stderr_bytes", 0),
                "truncated": result.get("truncated", False),
            },
        )
