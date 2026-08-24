from __future__ import annotations

import json
from pathlib import Path

from raiker.context.gatherer import CAPABILITY_GATE_TOOLS, ContextGatherer
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PolicyDecision, ToolAction, ToolResult
from raiker.verification.verifier import Verifier

# The capabilities whose gates the context bundle is required to report. BUG-57
# replaced a fixed list of `*_enabled: false` lines with a live per-principal
# reading, so what this test hardens has changed with it: not that a flag is
# permanently false, but that a fresh workspace — where the owner has enabled
# nothing — is reported as gated, in the tool vocabulary the model proposes in.
REQUIRED_GATED_CAPABILITIES = (
    "file_write_execution",
    "patch_apply_execution",
    "shell_execution",
    "remote_execution_cap",
    "cloud_execution_cap",
    "web_fetch",
    "connector_github_runtime",
    "connector_gmail_runtime",
    "connector_gcal_runtime",
    "connector_slack_runtime",
    "advisor_model_runtime",
    "mcp_connector_runtime",
)


def test_required_capability_gates_are_reported_as_the_tools_will_read_them(
    tmp_path: Path,
) -> None:
    """Every gated capability is reported, and reported truthfully.

    Previously this asserted all of them read ``disabled`` on a fresh workspace.
    That was true of the bundle and untrue of the product: `web_fetch` resolves
    an empty gate table to the shipped default, so the model was told the
    capability was off while the tool would have allowed the call (GEP-01).
    """
    from raiker.runtime.authority.admission import capability_admission
    from raiker.storage.sqlite import SQLiteStore

    assert set(REQUIRED_GATED_CAPABILITIES).issubset(set(CAPABILITY_GATE_TOOLS))

    bundle = ContextGatherer().gather(
        workspace_root=tmp_path,
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        prompt_text="check disabled flags",
    )
    capability = [
        item for item in bundle.included_items if item.source.source_type == "capability_status"
    ][0]

    store = SQLiteStore(tmp_path)
    for name in REQUIRED_GATED_CAPABILITIES:
        expected = capability_admission(store, None, name).gate_enabled
        assert capability.metadata[name]["enabled"] is expected, name  # type: ignore[index]
        assert f"{name}: {'enabled' if expected else 'disabled'}" in capability.content
        for tool in CAPABILITY_GATE_TOOLS[name]:
            assert tool in capability.content

    # The claim worth keeping literal: nothing that executes is on before the
    # owner says so.
    assert capability.metadata["shell_execution"]["enabled"] is False  # type: ignore[index]


def test_context_gathered_event_payload_is_metadata_only_and_redacted(tmp_path: Path) -> None:
    prompt = "token=supersecretvalue123 email dev@example.com"
    bundle = ContextGatherer().gather(
        workspace_root=tmp_path,
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        prompt_text=prompt,
    )

    prompt_item = [item for item in bundle.included_items if item.source.source_type == "current_prompt"][0]
    assert prompt_item.source.redacted is True
    assert "supersecretvalue123" not in prompt_item.content
    assert "dev@example.com" not in prompt_item.content

    event_payload = bundle.event_payload()
    dumped = json.dumps(event_payload, sort_keys=True)
    assert "supersecretvalue123" not in dumped
    assert "dev@example.com" not in dumped
    assert "token=" not in dumped
    assert "current_prompt" in dumped
    assert "source_types" in event_payload
    assert "items" not in event_payload


def test_verification_completed_event_payload_is_metadata_only() -> None:
    action = ToolAction(
        action_id=new_id("act_"),
        tool_name="read_file",
        arguments={"path": "secret.txt"},
        risk_level="medium",
        requires_approval=False,
    )
    decision = PolicyDecision(
        decision_id=new_id("pol_"),
        action_id=action.action_id,
        decision="allow",
        reasons=["read_only_tool"],
        requires_user_approval=False,
        risk_level="medium",
        timestamp=utc_now(),
    )
    result = ToolResult(
        action_id=action.action_id,
        tool_name=action.tool_name,
        status="success",
        output={"status": "success", "text": "password=hunter2"},
        error=None,
        started_at=utc_now(),
        completed_at=utc_now(),
    )

    verification = Verifier().verify(
        action=action,
        decision=decision,
        result=result,
        started_action_ids={action.action_id},
    )
    payload = verification.event_payload()
    dumped = json.dumps(payload, sort_keys=True)

    assert verification.overall_status == "passed"
    assert "hunter2" not in dumped
    assert "password" not in dumped
    assert "secret.txt" not in dumped
    assert "chain_of_thought" not in dumped
    assert payload["check_names"] == ["tool_call_schema", "read_result_shape"]
