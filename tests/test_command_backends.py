from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from raiker.contracts.ids import utc_now
from raiker.contracts.models import RemoteExecutionProfile
from raiker.execution.commands import CommandRequest
from raiker.execution.commands.backends import (
    BackendRegistry,
    CommandBackendError,
    LocalStrictBackend,
    NativeSandboxDriver,
    UnavailableBackend,
)
from raiker.execution.commands.service import CommandService
from raiker.execution.profiles import (
    ExecutionProfile,
    ProfileProbe,
    resolve_command_environment,
)
from raiker.storage.sqlite import SQLiteStore


def test_command_service_imports_without_executor_package_cycle() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from raiker.execution.commands.service import CommandService; "
            "assert CommandService.__name__ == 'CommandService'",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def request(workspace_root: Path, **overrides: object) -> CommandRequest:
    values: dict[str, object] = {
        "run_id": "cmd_backend",
        "owner_principal_id": "owner_a",
        "acting_principal_id": "agent_a",
        "session_id": "sess_a",
        "turn_id": "turn_a",
        "action_id": "act_a",
        "repository_id": None,
        "workspace_root": workspace_root,
        "cwd": ".",
        "executable_template": "",
        "argv_template": ("git", "status"),
        "safe_display": "git status",
        "credential_bindings": (),
        "shell": False,
        "interactive": False,
        "background": False,
        "timeout_seconds": 30.0,
        "max_output_bytes": 100_000,
        "environment_profile_id": "local_native",
        "network_policy_id": None,
    }
    values.update(overrides)
    return CommandRequest(**values)  # type: ignore[arg-type]


def _container(store: SQLiteStore, profile_id: str = "container_a") -> None:
    now = utc_now()
    store.insert_remote_execution_profile(
        RemoteExecutionProfile(
            profile_id,
            "container",
            "Container A",
            '{"image":"raiker-tools:test","repository_access":"read_only",'
            '"runtime":"docker","tools":["shell"]}',
            True,
            "owner_a",
            now,
            now,
        )
    )


def test_selected_command_environment_is_authoritative(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _container(store)
    store.select_execution_environment("owner_a", "container_a")

    resolution = resolve_command_environment(
        store,
        "owner_a",
        "shell",
        probe=lambda profile: ProfileProbe(profile, True, None, utc_now()),
    )

    assert resolution.profile is not None
    assert resolution.profile.profile_id == "container_a"
    assert resolution.selected_for_commands is True
    assert resolution.available is True


def test_unknown_or_unassigned_selected_environment_fails_without_fallback(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.select_execution_environment("owner_a", "missing")
    missing = resolve_command_environment(store, "owner_a", "shell")
    assert missing.profile is None
    assert missing.reason_code == "selected_environment_unavailable"

    _container(store)
    store.select_execution_environment("owner_a", "container_a")
    unsupported = resolve_command_environment(store, "owner_a", "read_file")
    assert unsupported.profile is None
    assert unsupported.reason_code == "selected_environment_tool_unsupported"


def test_unavailable_selected_sandbox_never_calls_local_runner(tmp_path: Path) -> None:
    local = Mock()
    registry = BackendRegistry(
        {
            "local_native": local,
            "container_a": UnavailableBackend("container_daemon_unreachable"),
        }
    )

    with pytest.raises(CommandBackendError, match="container_daemon_unreachable"):
        registry.start(request(tmp_path, environment_profile_id="container_a"))
    local.start.assert_not_called()


def test_command_service_routes_selected_container_without_local_fallback(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _container(store)
    store.select_execution_environment("owner_a", "container_a")
    selected = Mock()
    handle = Mock()
    handle.poll.return_value = None
    selected.start.return_value = handle
    service = CommandService(
        tmp_path,
        profile_probe=lambda profile: ProfileProbe(profile, True, None, utc_now()),
        backend_factory=lambda profile: selected,
    )

    run = service.start(
        owner_principal_id="owner_a",
        acting_principal_id="agent_a",
        session_id="sess_a",
        turn_id="turn_a",
        action_id="act_a",
        authority_kind="approval",
        authority_id="appr_a",
        command="misleading display",
        argv=["printf", "hello"],
    )

    routed = selected.start.call_args.args[0]
    assert run.profile_id == "container_a"
    assert routed.shell is False
    assert routed.executable_template == ""
    assert routed.argv_template == ("printf", "hello")
    assert routed.safe_display == "printf hello"
    service.shutdown()


def test_local_strict_rejects_shell_background_network_and_credentials(tmp_path: Path) -> None:
    backend = LocalStrictBackend(runner=Mock())
    with pytest.raises(CommandBackendError, match="local_strict_shell_source_denied"):
        backend.start(
            request(
                tmp_path,
                executable_template="echo hi",
                argv_template=(),
                shell=True,
                safe_display="echo hi",
            )
        )
    with pytest.raises(CommandBackendError, match="selected_environment_background_unsupported"):
        backend.start(request(tmp_path, background=True))
    with pytest.raises(CommandBackendError, match="selected_environment_network_unsupported"):
        backend.start(request(tmp_path, network_policy_id="filtered"))


def test_local_strict_runs_validated_argv_with_secret_free_environment(tmp_path: Path) -> None:
    runner = Mock(return_value="handle")
    backend = LocalStrictBackend(runner=runner)
    assert backend.start(request(tmp_path)) == "handle"
    called = runner.call_args
    assert called.args[1] == ["git", "status"]
    assert "OPENAI_API_KEY" not in called.args[3]
    assert backend.features.shell is False
    assert backend.features.concurrent_runs is False
    assert backend.features.credential_delivery is False


@pytest.mark.parametrize(
    ("platform", "marker"),
    (("linux", "bwrap"), ("darwin", "sandbox-exec"), ("win32", "raiker-command-runner.exe")),
)
def test_native_driver_wraps_command_and_denies_network(
    platform: str, marker: str, tmp_path: Path
) -> None:
    driver = NativeSandboxDriver(platform, helper_root=tmp_path)
    command = driver.command(request(tmp_path), ["npm", "test"])
    assert marker in command[0]
    policy = driver.policy(request(tmp_path))
    assert policy.network == "none"
    assert ".raiker" in policy.protected_paths
    assert policy.git_write is False
    assert policy.outside_workspace_write is False


def test_native_readiness_never_claims_missing_helper(tmp_path: Path) -> None:
    driver = NativeSandboxDriver("win32", helper_root=tmp_path)
    proof = driver.probe(tmp_path)
    assert proof.available is False
    assert proof.reason_code == "native_sandbox_artifact_missing"


@pytest.mark.parametrize(
    "profile",
    (
        ExecutionProfile("local_native", "local"),
        ExecutionProfile("ssh_a", "ssh", tools=("shell",)),
        ExecutionProfile("daytona_a", "daytona", tools=("shell",)),
    ),
)
def test_non_container_profiles_never_advertise_credential_delivery(
    profile: ExecutionProfile,
) -> None:
    assert profile.features.credential_delivery is False
    assert profile.features.credential_delta_quarantine is False


def test_feature_contract_refuses_delivery_without_quarantine() -> None:
    with pytest.raises(ValueError, match="credential_delivery_requires_quarantine"):
        ExecutionProfile(
            "bad",
            "container",
            runtime="docker",
            image="raiker-tools:test",
            tools=("shell",),
            credential_delivery=True,
            credential_delta_quarantine=False,
        )


def test_container_profile_advertises_only_the_proven_foreground_shell() -> None:
    features = ExecutionProfile(
        "container_a",
        "container",
        runtime="docker",
        image="raiker-command-sandbox@sha256:" + ("a" * 64),
        tools=("shell",),
        credential_delivery=True,
        credential_delta_quarantine=True,
    ).features

    assert features.shell is True
    assert features.process_tree_stop is True
    assert features.pty is False
    assert features.background is False
    assert features.input is False
    assert features.filtered_network is False
    assert features.persistent is False
    assert features.restart_recovery is False
    assert features.concurrent_runs is False
    assert features.credential_delivery is False
    assert features.credential_delta_quarantine is False
