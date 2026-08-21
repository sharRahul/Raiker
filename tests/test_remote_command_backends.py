from __future__ import annotations

import base64
import json
import tomllib
from pathlib import Path
from unittest.mock import Mock

import pytest

from raiker.contracts.ids import utc_now
from raiker.contracts.models import RemoteExecutionProfile
from raiker.execution.commands.backends import CommandBackendError, SshCommandBackend
from raiker.execution.commands.known_hosts import host_key_fingerprint
from raiker.execution.commands.models import CommandRequest
from raiker.execution.commands.remote_envelope import (
    RemoteCommandEnvelope,
    decode_remote_envelope,
    encode_remote_envelope,
)
from raiker.execution.commands.remote_supervisor import probe_document
from raiker.execution.profiles import ExecutionProfile, ProfileProbe, resolve_command_environment
from raiker.storage.sqlite import SQLiteStore


def _request(root: Path, **changes: object) -> CommandRequest:
    values: dict[str, object] = {
        "run_id": "cmd_remote",
        "owner_principal_id": "owner_a",
        "acting_principal_id": "agent_a",
        "session_id": "sess_a",
        "turn_id": "turn_a",
        "action_id": "act_a",
        "repository_id": None,
        "workspace_root": root,
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
        "environment_profile_id": "ssh_a",
        "network_policy_id": None,
    }
    values.update(changes)
    return CommandRequest(**values)  # type: ignore[arg-type]


def _ssh_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ExecutionProfile:
    identity = tmp_path / "identity"
    identity.write_text("test-only", encoding="utf-8")
    monkeypatch.setenv("RAIKER_TEST_SSH_IDENTITY", str(identity))
    blob = base64.b64encode(b"test host key blob").decode()
    public_key = f"ssh-ed25519 {blob}"
    return ExecutionProfile(
        "ssh_a",
        "ssh",
        tools=("shell",),
        config={
            "credential_env": "RAIKER_TEST_SSH_IDENTITY",
            "host": "build.example.com",
            "host_key_sha256": host_key_fingerprint(public_key),
            "host_public_key": public_key,
            "owner_principal_id": "owner_a",
            "port": 22,
            "user": "raiker",
        },
    )


@pytest.mark.parametrize(
    "value",
    ["a; rm -rf x", "$(touch x)", "a b", "'\"`$\\", "line\nbreak"],
)
def test_remote_argv_is_canonical_data_not_shell_source(value: str) -> None:
    envelope = RemoteCommandEnvelope(
        "cmd_a", ("printf", "%s", value), ".", 30, 100_000
    )
    decoded = decode_remote_envelope(encode_remote_envelope(envelope))
    assert decoded.argv == ("printf", "%s", value)
    assert decoded.digest == envelope.digest


def test_remote_envelope_rejects_unknown_fields_and_traversing_cwd() -> None:
    envelope = RemoteCommandEnvelope("cmd_a", ("git", "status"), ".", 30, 100_000)
    frame = encode_remote_envelope(envelope)
    value = json.loads(frame[4:])
    value["shell"] = True
    changed = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="remote_command_fields_invalid"):
        decode_remote_envelope(len(changed).to_bytes(4, "big") + changed)
    with pytest.raises(ValueError, match="remote_command_cwd_invalid"):
        RemoteCommandEnvelope("cmd_a", ("git", "status"), "../escape", 30, 100_000)


def test_ssh_backend_uses_its_own_pin_and_fixed_supervisor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _ssh_profile(tmp_path, monkeypatch)
    monkeypatch.setattr("raiker.execution.commands.backends.remote.shutil.which", lambda _name: "ssh")
    written: list[bytes] = []
    process = Mock()
    process.write.side_effect = written.append

    class Handle:
        def __init__(self) -> None:
            self.process = process

        @staticmethod
        def poll() -> None:
            return None

    handle = Handle()
    runner = Mock(return_value=handle)
    backend = SshCommandBackend(profile, tmp_path, runner=runner)

    assert backend.start(_request(tmp_path), Mock()) is handle

    transport = runner.call_args.args[1]
    assert "StrictHostKeyChecking=yes" in transport
    known_hosts_arg = next(value for value in transport if value.startswith("UserKnownHostsFile="))
    assert Path(known_hosts_arg.split("=", 1)[1]).is_file()
    assert transport[-1] == "/usr/local/bin/raiker-command-supervisor"
    assert transport[-2] == "raiker@build.example.com"
    assert decode_remote_envelope(written[0]).argv == ("git", "status")
    assert profile.features.shell is False
    assert profile.features.background is False
    assert profile.features.pty is False
    assert profile.features.restart_recovery is False
    assert profile.features.credential_delivery is False


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("background", "selected_environment_background_unsupported"),
        ("interactive", "selected_environment_pty_unsupported"),
    ],
)
def test_remote_backend_refuses_unbuilt_lifecycle_features(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    reason: str,
) -> None:
    backend = SshCommandBackend(_ssh_profile(tmp_path, monkeypatch), tmp_path, runner=Mock())
    with pytest.raises(CommandBackendError, match=reason):
        backend.start(_request(tmp_path, **{field: True}), Mock())


def test_selected_unready_ssh_never_falls_back_to_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteStore(tmp_path)
    profile = _ssh_profile(tmp_path, monkeypatch)
    now = utc_now()
    store.insert_remote_execution_profile(
        RemoteExecutionProfile(
            profile.profile_id,
            "ssh",
            "Build host",
            json.dumps(dict(profile.config)),
            True,
            "owner_a",
            now,
            now,
        )
    )
    store.select_execution_environment("owner_a", profile.profile_id)
    resolution = resolve_command_environment(
        store,
        "owner_a",
        "shell",
        probe=lambda selected: ProfileProbe(
            selected, False, "ssh_command_supervisor_unavailable", utc_now()
        ),
    )
    assert resolution.available is False
    assert resolution.profile is profile or resolution.profile is not None
    assert resolution.reason_code == "ssh_command_supervisor_unavailable"


def test_remote_probe_document_is_foreground_only_and_identity_bound() -> None:
    document = probe_document()
    assert document["protocol"] == "raiker-command-v1"
    assert len(str(document["artifact_digest"])) == 64
    assert document["features"] == {
        "background": False,
        "credential_delivery": False,
        "filtered_network": False,
        "pty": False,
        "restart_recovery": False,
        "shell": False,
    }


def test_remote_supervisor_is_a_packaged_console_script() -> None:
    project = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert project["project"]["scripts"]["raiker-command-supervisor"] == (
        "raiker.execution.commands.remote_supervisor:main"
    )
