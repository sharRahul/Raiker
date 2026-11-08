"""An approval executes exactly what was proposed, even when it looks sensitive.

Found by BD-5 (2026-11-08): a Build write to ``bd5-stats-1778230000/stats.py``
was stored with the path redacted as a phone-like ID, so approving it failed
as ``approval_payload_tampered``, and executing it would have written to the
masked path. The stored action keeps its exact arguments; the event does not.
"""

from __future__ import annotations

import json
from pathlib import Path

from raiker.approvals import ApprovalInbox
from raiker.contracts.models import ToolAction
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


def test_an_approval_for_an_id_like_path_resolves_and_keeps_the_real_path(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    action = ToolAction(
        action_id="act_1",
        tool_name="write_file",
        arguments={"path": "bd5-stats-1778230000/stats.py", "text": "x = 1\n"},
        risk_level="medium",
        requires_approval=True,
        proposed_by="principal_owner",
    )
    sanitized = ToolBroker._event_safe_arguments(action)
    assert "[REDACTED" in json.dumps(sanitized), "the event-safe form still masks it"
    store.insert_tool_action(action, "sess_1", "turn_1", "approval_required")
    store.insert_approval("appr_1", action)
    approval = store.load_approval("appr_1")
    assert approval is not None
    stored = json.loads(str(approval["arguments_json"]))
    assert stored["path"] == "bd5-stats-1778230000/stats.py"
    resolution = ApprovalInbox(store).resolve("appr_1", approve=True)
    assert resolution.status == "approved"
