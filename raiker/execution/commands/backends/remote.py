"""Foreground-only remote transports for the governed command lifecycle."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from raiker.execution.commands.backends.base import CommandBackendError
from raiker.execution.commands.known_hosts import write_profile_known_hosts
from raiker.execution.commands.models import CommandFeatures, CommandRequest
from raiker.execution.commands.remote_envelope import (
    RemoteCommandEnvelope,
    encode_remote_envelope,
)
from raiker.execution.commands.remote_supervisor import (
    SUPERVISOR_VERSION,
    supervisor_artifact_digest,
)
from raiker.execution.commands.runner import CommandSink, StreamingCommandRunner
from raiker.execution.profiles import ExecutionProfile
from raiker.runtime.command_policy import sandbox_environment
from raiker.storage.sqlite import SQLiteStore

REMOTE_SUPERVISOR_PATH = "/usr/local/bin/raiker-command-supervisor"
_HOST = re.compile(r"[A-Za-z0-9.-]{1,253}")
_USER = re.compile(r"[A-Za-z0-9._-]{1,64}")
_SANDBOX = re.compile(r"[A-Za-z0-9._-]{1,128}")

REMOTE_FEATURES = CommandFeatures(
    shell=False,
    pty=False,
    background=False,
    input=False,
    process_tree_stop=False,
    network_escalation=False,
    filtered_network=False,
    persistent_environment=False,
    persistent=False,
    restart_recovery=False,
    recoverable=False,
    concurrent_runs=False,
    credential_delivery=False,
    credential_delta_quarantine=False,
)


def probe_remote_profile(
    profile: ExecutionProfile, workspace_root: Path
) -> tuple[bool, str | None, dict[str, str]]:
    """Run only the fixed read-only supervisor probe and verify its identity."""
    try:
        if profile.kind == "ssh":
            backend = SshCommandBackend(profile, workspace_root)
            argv, environment, _secrets = backend.transport()
        elif profile.kind == "daytona":
            backend = DaytonaCommandBackend(profile, workspace_root, SQLiteStore(workspace_root))
            argv, environment, _api_key = backend.transport(15)
        else:
            return False, "remote_profile_kind_invalid", {}
        argv = [*argv, "--probe"]
        completed = subprocess.run(  # noqa: S603 - fixed validated transport + literal probe
            argv,
            cwd=workspace_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except CommandBackendError as exc:
        return False, exc.reason_code, {}
    except (OSError, subprocess.TimeoutExpired):
        return False, f"{profile.kind}_command_supervisor_unavailable", {}
    if completed.returncode != 0:
        return False, f"{profile.kind}_command_supervisor_unavailable", {}
    try:
        value = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError):
        return False, "remote_command_supervisor_probe_invalid", {}
    expected = {
        "protocol": "raiker-command-v1",
        "version": SUPERVISOR_VERSION,
        "artifact_digest": supervisor_artifact_digest(),
    }
    observed = {key: str(value.get(key, "")) for key in expected}
    if observed != expected or value.get("available") is not True:
        return False, "remote_command_supervisor_identity_mismatch", observed
    return True, None, observed


def _checked_request(request: CommandRequest) -> None:
    if request.shell:
        raise CommandBackendError("remote_shell_source_denied")
    if request.background:
        raise CommandBackendError("selected_environment_background_unsupported")
    if request.interactive:
        raise CommandBackendError("selected_environment_pty_unsupported")
    if request.network_policy_id:
        raise CommandBackendError("selected_environment_network_unsupported")
    if request.credential_bindings:
        raise CommandBackendError("selected_environment_credential_unsupported")


def _send_frame(handle: Any, frame: bytes) -> None:
    send = getattr(handle, "write_frame", None)
    if callable(send):
        send(frame)
        return
    process = getattr(handle, "process", None)
    write = getattr(process, "write", None)
    if not callable(write):
        raise CommandBackendError("remote_transport_stdin_unavailable")
    write(frame)


class SshCommandBackend:
    features = REMOTE_FEATURES

    def __init__(
        self,
        profile: ExecutionProfile,
        workspace_root: Path,
        *,
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.profile = profile
        self.workspace_root = workspace_root.resolve()
        self.config: Mapping[str, Any] = profile.config
        self._runner = runner

    def transport(self) -> tuple[list[str], dict[str, str], tuple[str, ...]]:
        host = str(self.config.get("host", "")).strip()
        user = str(self.config.get("user", "")).strip()
        port = int(self.config.get("port", 22))
        identity_env = str(self.config.get("credential_env", "")).strip()
        identity = os.environ.get(identity_env, "").strip() if identity_env else ""
        public_key = str(self.config.get("host_public_key", "")).strip()
        fingerprint = str(self.config.get("host_key_sha256", "")).strip()
        if (
            shutil.which("ssh") is None
            or not _HOST.fullmatch(host)
            or not _USER.fullmatch(user)
            or not 1 <= port <= 65535
            or not identity
            or not Path(identity).is_file()
        ):
            raise CommandBackendError("ssh_profile_not_ready")
        try:
            known_hosts = write_profile_known_hosts(
                self.workspace_root,
                owner_principal_id=str(self.config.get("owner_principal_id", "")),
                profile_id=self.profile.profile_id,
                host=host,
                port=port,
                public_key=public_key,
                expected_fingerprint=fingerprint,
            )
        except (OSError, ValueError):
            raise CommandBackendError("ssh_host_key_pin_invalid") from None
        argv = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-o",
            "GlobalKnownHostsFile=" + ("NUL" if os.name == "nt" else "/dev/null"),
            "-o",
            "ConnectTimeout=10",
            "-p",
            str(port),
            "-i",
            identity,
            "--",
            f"{user}@{host}",
            REMOTE_SUPERVISOR_PATH,
        ]
        return argv, sandbox_environment(workspace_root=self.workspace_root), (identity,)

    def start(self, request: CommandRequest, sink: CommandSink) -> Any:
        _checked_request(request)
        argv, environment, secrets = self.transport()
        runner = self._runner or StreamingCommandRunner(
            registered_secrets=secrets
        ).start
        handle = runner(
            request,
            argv,
            self.workspace_root,
            environment,
            sink,
            pty=False,
        )
        _send_frame(
            handle,
            encode_remote_envelope(
                RemoteCommandEnvelope(
                    request.run_id,
                    request.argv_template,
                    request.cwd,
                    request.timeout_seconds,
                    request.max_output_bytes,
                )
            ),
        )
        return handle

    def isolation_evidence(self, request: CommandRequest) -> dict[str, Any]:
        del request
        return {
            "boundary_constructed": {
                "transport": "ssh",
                "host_key_checking": "profile_pin",
                "remote_supervisor": REMOTE_SUPERVISOR_PATH,
            }
        }


class DaytonaCommandBackend:
    features = REMOTE_FEATURES

    def __init__(
        self,
        profile: ExecutionProfile,
        workspace_root: Path,
        store: SQLiteStore,
        *,
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.profile = profile
        self.workspace_root = workspace_root.resolve()
        self.store = store
        self.config: Mapping[str, Any] = profile.config
        self._runner = runner

    def transport(self, timeout_seconds: float) -> tuple[list[str], dict[str, str], str]:
        sandbox_id = str(self.config.get("sandbox_id", "")).strip()
        key_env = str(self.config.get("api_key_env", "")).strip()
        api_key = os.environ.get(key_env, "").strip() if key_env else ""
        if shutil.which("daytona") is None or not _SANDBOX.fullmatch(sandbox_id) or not api_key:
            raise CommandBackendError("daytona_profile_not_ready")
        environment = sandbox_environment(workspace_root=self.workspace_root)
        environment["DAYTONA_API_KEY"] = api_key
        return (
            [
                "daytona",
                "exec",
                sandbox_id,
                "--timeout",
                str(int(timeout_seconds) + 15),
                "--",
                REMOTE_SUPERVISOR_PATH,
            ],
            environment,
            api_key,
        )

    def start(self, request: CommandRequest, sink: CommandSink) -> Any:
        _checked_request(request)
        try:
            max_cost = float(self.config.get("max_cost", 0))
            estimated = float(self.config.get("estimated_cost_per_run", 0))
        except (TypeError, ValueError):
            raise CommandBackendError("daytona_budget_invalid") from None
        if max_cost <= 0 or estimated < 0 or not self.store.reserve_cloud_execution_cost(
            owner_principal_id=request.owner_principal_id,
            profile_id=self.profile.profile_id,
            action_id=request.action_id,
            estimated_cost=estimated,
            max_cost=max_cost,
        ):
            raise CommandBackendError("cloud_execution_budget_exceeded")
        argv, environment, api_key = self.transport(request.timeout_seconds)
        runner = self._runner or StreamingCommandRunner(
            registered_secrets=(api_key,)
        ).start
        handle = runner(
            request,
            argv,
            self.workspace_root,
            environment,
            sink,
            pty=False,
        )
        _send_frame(
            handle,
            encode_remote_envelope(
                RemoteCommandEnvelope(
                    request.run_id,
                    request.argv_template,
                    request.cwd,
                    request.timeout_seconds,
                    request.max_output_bytes,
                )
            ),
        )
        return handle

    def isolation_evidence(self, request: CommandRequest) -> dict[str, Any]:
        del request
        return {
            "boundary_constructed": {
                "transport": "daytona",
                "remote_supervisor": REMOTE_SUPERVISOR_PATH,
            }
        }
