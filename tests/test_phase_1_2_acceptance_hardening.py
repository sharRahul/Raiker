from __future__ import annotations

import json
from pathlib import Path

from raiker.context.gatherer import CAPABILITY_FLAGS, ContextGatherer
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PolicyDecision, ToolAction, ToolResult
from raiker.verification.verifier import Verifier

REQUIRED_DISABLED_FLAGS = (
    "plugin_execution_enabled",
    "graph_indexing_enabled",
    "semantic_memory_writes_enabled",
    "vector_writes_enabled",
    "embedding_creation_enabled",
    "approval_execution_enabled",
    "approval_relay_runtime_enabled",
    "cleanup_execution_enabled",
    "rollback_execution_enabled",
    "external_channels_enabled",
    "notifications_enabled",
    "remote_execution_enabled",
    "container_execution_enabled",
    "cloud_execution_enabled",
    "process_execution_enabled",
    "shell_execution_enabled",
    "network_execution_enabled",
    "runtime_execution_enabled",
)


def test_required_disabled_runtime_flags_are_directly_reported_false(tmp_path: Path) -> None:
    assert set(REQUIRED_DISABLED_FLAGS).issubset(set(CAPABILITY_FLAGS))

    bundle = ContextGatherer().gather(
        workspace_root=tmp_path,
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        prompt_text="check disabled flags",
    )
    capability = [
        item for item in bundle.included_items if item.source.source_type == "capability_status"
    ][0]

    for flag in REQUIRED_DISABLED_FLAGS:
        assert capability.metadata[flag] is False
        assert f"{flag}: false" in capability.content


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
