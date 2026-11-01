"""Capability status must not claim that sandbox failure permits host execution."""

from pathlib import Path

from raiker.control.service import RuntimeControlService
from raiker.execution.code_placement import set_sandbox_prober


def test_unavailable_sandbox_is_reported_as_blocked(tmp_path: Path) -> None:
    set_sandbox_prober(lambda _: False)
    try:
        message = RuntimeControlService(tmp_path)._network_boundary("shell_execution")
        assert "unavailable" in message.lower()
        assert "refused" in message.lower()
        assert "run with its network" not in message
    finally:
        set_sandbox_prober(None)
