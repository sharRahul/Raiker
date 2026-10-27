"""Risk classification must not select an unisolated execution destination."""

from pathlib import Path

import pytest

from raiker.execution.code_placement import place_code, set_sandbox_prober
from raiker.storage.sqlite import SQLiteStore


@pytest.mark.parametrize("background,interactive", [(False, False), (True, False), (False, True)])
def test_host_risk_still_requires_authorization_without_host_placement(
    tmp_path: Path, background: bool, interactive: bool
) -> None:
    set_sandbox_prober(lambda _: False)
    try:
        placement = place_code(
            SQLiteStore(tmp_path), "owner", ["python", "task.py"], tmp_path,
            background=background, interactive=interactive,
        )
        assert placement.classification == "host_network"
        assert placement.needs_host_network_capability
        assert placement.kind == "unavailable"
    finally:
        set_sandbox_prober(None)


def test_local_profile_approval_does_not_select_host(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.select_execution_environment("owner", "local_native")
    set_sandbox_prober(lambda _: True)
    try:
        placement = place_code(store, "owner", ["python", "task.py"], tmp_path)
        assert placement.classification == "host_network"
        assert placement.needs_host_network_capability
        assert placement.kind == "sandbox"
    finally:
        set_sandbox_prober(None)
