"""An approval that cannot carry its action out says so plainly (regular use, 2026-11-16)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from raiker.tools.broker import ToolBroker
from tests.factories import tool_action


def test_a_memory_write_with_memory_store_off_names_the_permission(tmp_path: Path) -> None:
    broker = ToolBroker.__new__(ToolBroker)
    broker.store = object()  # type: ignore[assignment]
    broker.principal_id = "principal_owner"
    action = tool_action(
        "memory_write", {"scope": "global", "text": "Dentist on Thursdays"},
        risk_level="medium", requires_approval=True,
    )
    with mock.patch(
        "raiker.approvals.execution.ApprovalExecutionBridge.metadata_only_gate",
        return_value="memory_write_execution",
    ), mock.patch("raiker.approvals.execution.ApprovalExecutionBridge.__init__", return_value=None):
        sentence = broker._record_only_consequence(action)
    assert sentence.startswith("Approving will not do this: the Memory store permission is off")
    assert "Turn on Memory store in Permissions" in sentence
    assert "metadata-only" not in sentence
