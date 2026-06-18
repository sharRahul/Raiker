from __future__ import annotations

from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, UIActionEnvelope

CLIENTS = [
    ("tui", "terminal"),
    ("desktop", "desktop"),
    ("web_ui", "web"),
    ("dashboard", "dashboard"),
    ("ide", "ide"),
    ("voice", "voice"),
    ("mobile_companion", "mobile"),
    ("browser_extension", "browser"),
    ("slack", "chat/channel client"),
]


def test_future_clients_share_ui_action_envelope_and_are_not_privileged() -> None:
    for client_type, name in CLIENTS:
        client = ClientMetadata(type=client_type, name=f"raiker-{name}", version="0.0.0")
        envelope = UIActionEnvelope(new_id("act_"), new_id("sess_"), new_id("turn_"), client, "inspect_workspace", {"privileged": False})
        assert envelope.client.interface_status == "equal_primary_when_enabled"
        assert envelope.payload["privileged"] is False
        assert envelope.action_type != "direct_tool_call"


def test_approval_gated_actions_are_interface_independent() -> None:
    approvals = []
    for client_type, name in CLIENTS:
        client = ClientMetadata(type=client_type, name=f"raiker-{name}", version="0.0.0")
        envelope = UIActionEnvelope(new_id("act_"), "sess", "turn", client, "tool_action_requested", {"tool_name": "shell", "requires_approval": True})
        approvals.append(envelope.payload["requires_approval"])
    assert approvals == [True] * len(CLIENTS)
