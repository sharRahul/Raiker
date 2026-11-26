"""A configured sandbox is not proof that automatic commands are contained."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from raiker.api.routes_commands import _sandbox_view
from raiker.execution.commands.backends.native import NativeSandboxDriver, NativeSandboxProof


@pytest.mark.parametrize("available", [False, True])
def test_posture_readiness_uses_measured_enforcement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, available: bool,
) -> None:
    monkeypatch.setattr(NativeSandboxDriver, "locate", lambda self: (None, "not_installed"))
    monkeypatch.setattr(NativeSandboxDriver, "wsl_status", lambda self: {"configured": True})
    monkeypatch.setattr(NativeSandboxDriver, "wsl_runner", lambda self: None)
    monkeypatch.setattr(
        NativeSandboxDriver, "probe",
        lambda self: NativeSandboxProof(available, None, "test", "now"),
    )
    request = Request({
        "type": "http",
        "app": SimpleNamespace(state=SimpleNamespace(workspace_root=tmp_path)),
    })
    assert _sandbox_view(request, "wsl")["enforced"] is available
