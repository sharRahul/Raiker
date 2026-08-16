from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from raiker.contracts.ids import utc_now
from raiker.contracts.models import RemoteExecutionProfile
from raiker.execution.commands import CommandRequest
from raiker.execution.commands.backends import (
    BackendRegistry,
    CommandBackendError,
    LocalStrictBackend,
    NativeSandboxBackend,
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
    # BUG-197 — the run names its backend while it is still in flight, not only
    # once a receipt exists. `run` is read straight back out of the store, so
    # this is the column the run list reads.
    assert run.backend == "container"
    service.shutdown()


def test_a_run_in_flight_already_names_the_backend_its_receipt_will_name(
    tmp_path: Path,
) -> None:
    """BUG-197 — the browsable row and the immutable receipt must not disagree.

    Every ``command_runs`` row carried ``backend = ''`` while `evidence.backend`
    on the receipt was correct, so the record that proves what ran a command and
    the list the owner reads said different things about the same run.
    """
    store = SQLiteStore(tmp_path)
    _container(store)
    store.select_execution_environment("owner_a", "container_a")
    backend = Mock()
    handle = Mock()
    handle.poll.return_value = None
    backend.start.return_value = handle
    service = CommandService(
        tmp_path,
        profile_probe=lambda profile: ProfileProbe(profile, True, None, utc_now()),
        backend_factory=lambda profile: backend,
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

    listed = service.store.list_runs("owner_a", session_id="sess_a")
    assert [item.backend for item in listed] == ["container"]
    assert run.backend == listed[0].backend
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


def _installed_runner(tmp_path: Path, *, digest: str | None = None) -> Path:
    """A stand-in runner with a digest manifest beside it."""
    directory = tmp_path / "native"
    directory.mkdir(parents=True, exist_ok=True)
    name = "raiker-command-runner.exe" if sys.platform == "win32" else "raiker-command-runner"
    binary = directory / name
    binary.write_bytes(b"not a real runner")
    (directory / "digest.json").write_text(
        json.dumps(
            {
                "binary": name,
                "sha256": digest or hashlib.sha256(binary.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    return directory


def _probe_reply(**overrides: str) -> Any:
    measured = {
        "relay": "enforced",
        "workspace_write": "enforced",
        "escape_write": "enforced",
        "masked_read": "enforced",
        "egress": "enforced",
        "descendant_reaped": "enforced",
    }
    measured.update(overrides)
    payload = {
        "platform": "windows",
        "boundary": "appcontainer",
        "available": all(value == "enforced" for value in measured.values()),
        "reason": None,
        "observations": measured,
        "connect_destination": "192.168.0.1:9",
    }
    return lambda argv: subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")


def test_native_sandbox_reports_missing_and_tampered_runners_separately(tmp_path: Path) -> None:
    absent = NativeSandboxDriver(tmp_path, helper_root=tmp_path / "native")
    assert absent.probe().reason_code == "native_sandbox_artifact_missing"

    directory = _installed_runner(tmp_path, digest="0" * 64)
    tampered = NativeSandboxDriver(tmp_path, helper_root=directory)
    assert tampered.probe().reason_code == "native_sandbox_runner_digest_mismatch"


def test_native_sandbox_capabilities_come_from_measurements_not_configuration(
    tmp_path: Path,
) -> None:
    directory = _installed_runner(tmp_path)
    driver = NativeSandboxDriver(tmp_path, helper_root=directory, run_probe=_probe_reply())
    proof = driver.probe()
    assert proof.available is True
    assert proof.boundary == "appcontainer"
    assert proof.features.process_tree_stop is True
    # Everything unmeasured stays off, however the profile is configured.
    assert proof.features.pty is False
    assert proof.features.background is False
    assert proof.features.filtered_network is False


@pytest.mark.parametrize("verdict", ("unenforced", "indeterminate"))
def test_an_unproven_egress_observation_never_yields_an_available_sandbox(
    tmp_path: Path, verdict: str
) -> None:
    """An indeterminate observation is not proof.

    A host with no route refuses to connect exactly like a boundary does. If a
    failed control arm counted as enforcement, an air-gapped machine would
    report a sandbox it does not have.
    """
    directory = _installed_runner(tmp_path)
    driver = NativeSandboxDriver(
        tmp_path, helper_root=directory, run_probe=_probe_reply(egress=verdict)
    )
    proof = driver.probe()
    assert proof.available is False
    assert proof.reason_code == "native_sandbox_not_enforced"


def test_a_descendant_that_survived_turns_process_tree_stop_off(tmp_path: Path) -> None:
    directory = _installed_runner(tmp_path)
    driver = NativeSandboxDriver(
        tmp_path, helper_root=directory, run_probe=_probe_reply(descendant_reaped="unenforced")
    )
    assert driver.probe().features.process_tree_stop is False


def test_the_launch_policy_masks_raiker_state_and_denies_the_network(tmp_path: Path) -> None:
    driver = NativeSandboxDriver(tmp_path, helper_root=tmp_path / "native")
    document = driver.policy_document(request(tmp_path))
    assert document["network"] == "none"
    assert ".raiker" in document["deny_paths"]
    assert ".git" in document["readonly_paths"]
    assert document["pty"] is False
    assert document["deadline_seconds"] > 0


def test_the_container_profile_name_is_per_run_not_per_workspace(tmp_path: Path) -> None:
    """A predictable container name is a hole, not a convenience.

    The container SID is a pure function of its name, so a name anything else
    can guess lets a local process enter a container the workspace already
    trusts.
    """
    one = NativeSandboxDriver.profile_name(request(tmp_path, run_id="cmd_one"))
    another = NativeSandboxDriver.profile_name(request(tmp_path, run_id="cmd_two"))
    assert one != another
    assert one.startswith("raiker.cmd.")
    # Stable for the same run, so a reap can name the profile it created.
    assert one == NativeSandboxDriver.profile_name(request(tmp_path, run_id="cmd_one"))


@pytest.mark.parametrize(
    ("field", "reason"),
    (
        ("background", "selected_environment_background_unsupported"),
        ("interactive", "selected_environment_pty_unsupported"),
    ),
)
def test_the_native_backend_refuses_unbuilt_capabilities_by_name(
    tmp_path: Path, field: str, reason: str
) -> None:
    directory = _installed_runner(tmp_path)
    driver = NativeSandboxDriver(tmp_path, helper_root=directory, run_probe=_probe_reply())
    backend = NativeSandboxBackend(driver=driver, proof=driver.probe())
    asked = request(tmp_path, **{field: True})
    with pytest.raises(CommandBackendError) as raised:
        backend.start(asked)
    assert raised.value.reason_code == reason


def test_an_unavailable_boundary_refuses_rather_than_running_on_the_host(
    tmp_path: Path,
) -> None:
    directory = _installed_runner(tmp_path)
    driver = NativeSandboxDriver(
        tmp_path, helper_root=directory, run_probe=_probe_reply(egress="unenforced")
    )
    backend = NativeSandboxBackend(driver=driver, proof=driver.probe())
    with pytest.raises(CommandBackendError) as raised:
        backend.start(request(tmp_path))
    assert raised.value.reason_code == "native_sandbox_not_enforced"


def test_the_receipt_separates_this_run_from_the_host_measurement(tmp_path: Path) -> None:
    """Two claims, kept apart.

    "This command ran in an AppContainer with no network capability" is about
    this run. "This host was measured to deny egress at 14:02" is about the
    host, taken earlier by another process. Blending them would let a receipt
    borrow a measurement it did not make.
    """
    directory = _installed_runner(tmp_path)
    driver = NativeSandboxDriver(tmp_path, helper_root=directory, run_probe=_probe_reply())
    backend = NativeSandboxBackend(driver=driver, proof=driver.probe())
    evidence = backend.isolation_evidence(request(tmp_path))
    assert evidence["boundary_constructed"]["network_capability"] is False
    assert evidence["boundary_constructed"]["profile_name"].startswith("raiker.cmd.")
    assert evidence["probe_observations"]["egress"] == "enforced"
    assert evidence["probe_checked_at"]


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
