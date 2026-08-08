from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, run_command

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction

# Local container execution (Phase 4 slice 3), sandboxed-first: run an
# owner-allowlisted image with no network, dropped capabilities, no host mounts,
# memory/cpu/pid limits, a read-only rootfs, and a timeout. Only images the owner
# explicitly allowlists can run; an empty allowlist denies everything (fail
# closed).

CONTAINER_RUN_TIMEOUT = 60.0
_MAX_TIMEOUT = 300.0

CommandRunner = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ContainerRunRequest:
    runtime: Literal["docker", "podman"]
    image: str
    command: tuple[str, ...]
    repository: Path | None
    output_dir: Path | None
    timeout: float
    stdin_text: str | None = None
    max_output_bytes: int = 200_000


def _action_workspace_root(repository: Path) -> Path:
    return repository.resolve() / ".raiker" / "container-workspaces"


def build_container_command(request: ContainerRunRequest) -> list[str]:
    if request.runtime not in {"docker", "podman"}:
        raise ValueError("container_runtime_invalid")
    if not request.image.strip():
        raise ValueError("container_image_required")
    command = [
        request.runtime,
        "run",
        "--rm",
        "--interactive",
        "--network",
        "none",
        "--memory",
        "512m",
        "--cpus",
        "1",
        "--pids-limit",
        "256",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        *_docker_user_args(),
    ]
    repository = request.repository.resolve() if request.repository is not None else None
    output = request.output_dir.resolve() if request.output_dir is not None else None
    if output is not None and (
        repository is None or _action_workspace_root(repository) not in output.parents
    ):
        raise ValueError("container_output_outside_action_root")
    if repository is not None:
        command.extend(
            ["--mount", f"type=bind,src={repository},dst=/repository,readonly"]
        )
        # The bridge is imported from the read-only repository mount. Disabling
        # bytecode writes keeps that import compatible with the immutable mount
        # and avoids leaving interpreter artifacts in the owner's workspace.
        command.extend(
            ["--workdir", "/repository", "--env", "PYTHONDONTWRITEBYTECODE=1"]
        )
    if output is not None:
        command.extend(["--mount", f"type=bind,src={output},dst=/workspace-output"])
    command.extend([request.image, *request.command])
    return command


def _docker_user_args() -> list[str]:
    """Preserve host ownership on POSIX without calling unavailable Windows APIs."""
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if getuid is None or getgid is None:
        return []
    return ["--user", f"{getuid()}:{getgid()}"]


def command_sandbox_image() -> str:
    """Return the operator-approved image for standing command grants.

    A grant is not permission to fall back to the host.  Operators must choose
    an image already covered by the container image allowlist; an unset or
    mismatched value therefore fails closed.
    """
    return os.environ.get("RAIKER_COMMAND_SANDBOX_IMAGE", "").strip()


def run_isolated_workspace_command(
    command: list[str],
    *,
    workspace_root: str | Path,
    timeout: float,
    max_output_bytes: int = 100_000,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Execute an owner-granted command behind Docker's network namespace."""
    image = command_sandbox_image()
    if not image:
        raise SandboxError("command_sandbox_unconfigured")
    if image not in container_image_allowlist():
        raise SandboxError("command_sandbox_image_not_allowed")
    workspace = Path(workspace_root).resolve()
    docker_command = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "512m",
        "--cpus", "1",
        "--pids-limit", "256",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        *_docker_user_args(),
        "--mount", f"type=bind,src={workspace},dst=/workspace",
        "--workdir", "/workspace",
        image,
        *command,
    ]
    command_runner = runner or run_command
    try:
        return command_runner(
            docker_command,
            timeout=timeout,
            max_output_bytes=max_output_bytes,
            allowlist=frozenset({"docker"}),
            cwd=workspace,
        )
    except SandboxError as exc:
        if str(exc).startswith("command_not_found"):
            raise SandboxError("command_sandbox_runtime_unavailable") from None
        raise


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
