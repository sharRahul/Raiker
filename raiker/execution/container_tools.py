from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from raiker.execution.profiles import ExecutionProfile, validate_execution_profile
from raiker.execution.tool_bridge import CONTAINER_SAFE_TOOLS
from raiker.runtime.executors.containers import (
    CommandRunner,
    ContainerRunRequest,
    build_container_command,
    container_image_allowlist,
)
from raiker.runtime.executors.sandbox import SandboxError, run_command
from raiker.storage.internal_paths import internal_io_path

_ACTION_ID = re.compile(r"[A-Za-z0-9_-]{1,160}\Z")


def container_action_workspace(workspace_root: str | Path, action_id: str) -> Path:
    if not _ACTION_ID.fullmatch(action_id):
        raise ValueError("container_action_id_invalid")
    root = Path(workspace_root).resolve()
    action_root = internal_io_path(root / ".raiker" / "container-workspaces")
    output = (action_root / action_id).resolve()
    if action_root.resolve() not in output.parents:
        raise ValueError("container_output_outside_action_root")
    return output


class ContainerToolExecutor:
    def __init__(
        self,
        workspace_root: str | Path,
        profile: ExecutionProfile,
        *,
        runner: CommandRunner | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.profile = profile
        self.runner = runner or run_command

    def _preflight(self, tool_name: str) -> str | None:
        reason = validate_execution_profile(self.profile)
        if reason:
            return reason
        if tool_name not in CONTAINER_SAFE_TOOLS or tool_name not in self.profile.tools:
            return "container_profile_tool_unsupported"
        if self.profile.image not in container_image_allowlist():
            return f"container_image_not_allowed:{self.profile.profile_id}"
        return None

    def execute(
        self, tool_name: str, arguments: dict[str, Any], action_id: str
    ) -> dict[str, Any]:
        reason = self._preflight(tool_name)
        if reason:
            return {"status": "failed", "error": {"type": reason}}
        output = container_action_workspace(self.workspace_root, action_id)
        output.mkdir(parents=True, exist_ok=False)
        assert self.profile.runtime is not None
        assert self.profile.image is not None
        payload = json.dumps(
            {
                "version": 1,
                "tool_name": tool_name,
                "arguments": arguments,
                "repository": "/repository",
                "output": "/workspace-output",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        request = ContainerRunRequest(
            runtime=self.profile.runtime,
            image=self.profile.image,
            command=("python", "-m", "raiker.execution.tool_bridge"),
            repository=self.workspace_root,
            output_dir=output,
            timeout=60,
            stdin_text=payload,
        )
        result: dict[str, Any]
        cleanup_failed = False
        try:
            raw = self.runner(
                build_container_command(request),
                timeout=request.timeout,
                max_output_bytes=request.max_output_bytes,
                allowlist=frozenset({request.runtime}),
                cwd=self.workspace_root,
                stdin_text=request.stdin_text,
            )
            if int(raw.get("returncode", 1)) != 0 and not str(raw.get("stdout", "")).strip():
                result = {
                    "status": "failed",
                    "error": {"type": f"container_exit_code:{raw.get('returncode', 1)}"},
                }
            elif bool(raw.get("truncated")):
                result = {
                    "status": "failed",
                    "error": {"type": "container_bridge_response_invalid"},
                }
            else:
                try:
                    parsed = json.loads(str(raw.get("stdout", "")))
                except json.JSONDecodeError:
                    parsed = None
                result = (
                    parsed
                    if isinstance(parsed, dict) and parsed.get("status") in {"success", "failed", "denied"}
                    else {
                        "status": "failed",
                        "error": {"type": "container_bridge_response_invalid"},
                    }
                )
        except SandboxError as exc:
            code = str(exc)
            if code.startswith("command_not_found"):
                code = f"container_runtime_unavailable:{self.profile.runtime}"
            result = {"status": "failed", "error": {"type": code}}
        finally:
            try:
                shutil.rmtree(output)
            except OSError:
                cleanup_failed = True
        if cleanup_failed:
            findings = result.setdefault("findings", [])
            if isinstance(findings, list):
                findings.append({"type": "container_workspace_cleanup_failed"})
        return result
