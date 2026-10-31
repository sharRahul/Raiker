"""Agent commands must never select an unisolated command backend."""

from pathlib import Path

import pytest

from raiker.execution.commands.backends.native import NativeSandboxDriver, NativeSandboxProof
from raiker.execution.commands.service import CommandService, CommandServiceError
from raiker.execution.profiles import ExecutionProfile


@pytest.mark.parametrize("argv", [["python", "task.py"], ["unknown-tool"], ["git", "status"]])
@pytest.mark.parametrize("background,interactive", [(False, False), (True, False), (False, True)])
def test_local_commands_are_always_placed_in_native_sandbox(
    tmp_path: Path, argv: list[str], background: bool, interactive: bool
) -> None:
    service = CommandService(tmp_path)
    profile = service._place_code(
        ExecutionProfile("local_native", "local"), "owner", argv,
        background=background, interactive=interactive, host_network_code=True,
    )
    assert profile.kind == "native"


@pytest.mark.parametrize("kind", ["container", "ssh", "daytona"])
def test_other_profiles_cannot_bypass_native_sandbox(tmp_path: Path, kind: str) -> None:
    service = CommandService(tmp_path)
    with pytest.raises(CommandServiceError, match="native_sandbox_required"):
        service._place_code(
            ExecutionProfile("other", kind), "owner", ["unknown-tool"],  # type: ignore[arg-type]
            background=False, interactive=False, host_network_code=True,
        )


def test_unavailable_native_boundary_never_launches_host_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "host-executed"
    script = tmp_path / "task.py"
    script.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    monkeypatch.setattr(
        NativeSandboxDriver, "probe",
        lambda self: NativeSandboxProof(False, "native_sandbox_unavailable", "none", ""),
    )
    service = CommandService(tmp_path)
    with pytest.raises(CommandServiceError, match="native_sandbox_unavailable"):
        service.start(
            owner_principal_id="owner", acting_principal_id="owner",
            session_id="session", turn_id="turn", action_id="action",
            authority_kind="approval", authority_id="approval", command="python task.py",
            argv=["python", "task.py"], host_network_code=True,
        )
    assert not marker.exists()
