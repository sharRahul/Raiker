from __future__ import annotations

import json

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PolicyDecision, ToolAction, ToolResult
from raiker.verification.verifier import Verifier


def _action(tool_name: str, arguments: dict[str, object], *, requires_approval: bool = False) -> ToolAction:
    risk = "high" if requires_approval else "medium"
    return ToolAction(
        action_id=new_id("act_"),
        tool_name=tool_name,
        arguments=arguments,
        risk_level=risk,
        requires_approval=requires_approval,
    )


def _decision(action: ToolAction, decision: str) -> PolicyDecision:
    return PolicyDecision(
        decision_id=new_id("pol_"),
        action_id=action.action_id,
        decision=decision,
        reasons=[f"{decision}_reason"],
        requires_user_approval=decision == "needs_approval",
        risk_level="high" if decision != "allow" else action.risk_level,
        timestamp=utc_now(),
    )


def _result(
    action: ToolAction,
    status: str,
    *,
    output: dict[str, object] | None = None,
    error: dict[str, object] | None = None,
) -> ToolResult:
    return ToolResult(
        action_id=action.action_id,
        tool_name=action.tool_name,
        status=status,
        output=output,
        error=error,
        started_at=utc_now(),
        completed_at=utc_now(),
    )


def test_invalid_tool_call_fails_verification() -> None:
    verifier = Verifier()
    check = verifier.verify_tool_call("read_file", "not-a-dict")
    assert check.status == "failed"
    assert check.reason == "arguments_not_object"


def test_unknown_tool_call_fails_verification() -> None:
    verifier = Verifier()
    check = verifier.verify_tool_call("definitely_not_a_tool", {})
    assert check.status == "failed"
    assert check.reason == "unknown_tool"
    # Aggregate path with a rejected call must be unsafe to continue.
    result = verifier.verify(rejected_tool_call={"tool_name": "definitely_not_a_tool", "reason": "unknown_tool"})
    assert result.overall_status == "failed"
    assert result.safe_to_continue is False


def test_known_tool_call_passes() -> None:
    assert Verifier().verify_tool_call("read_file", {"path": "x"}).status == "passed"


def test_denied_action_verifies_non_execution() -> None:
    verifier = Verifier()
    action = _action("read_file", {"path": "../escape.txt"})
    decision = _decision(action, "deny")
    result = _result(action, "denied")
    res = verifier.verify(action=action, decision=decision, result=result, started_action_ids=set())
    assert res.overall_status == "passed"
    assert res.safe_to_continue is True
    names = [c.name for c in res.checks]
    assert "denied_action_non_execution" in names


def test_denied_action_that_actually_executed_fails() -> None:
    verifier = Verifier()
    action = _action("read_file", {"path": "x"})
    decision = _decision(action, "deny")
    result = _result(action, "denied")
    res = verifier.verify(
        action=action,
        decision=decision,
        result=result,
        started_action_ids={action.action_id},
    )
    assert res.overall_status == "failed"
    assert res.safe_to_continue is False


def test_needs_approval_verifies_non_execution_and_metadata() -> None:
    verifier = Verifier()
    action = _action("write_file", {"path": "x", "text": "y"}, requires_approval=True)
    decision = _decision(action, "needs_approval")
    result = _result(
        action,
        "approval_required",
        output={"approval_id": new_id("appr_"), "reasons": decision.reasons},
    )
    res = verifier.verify(action=action, decision=decision, result=result)
    assert res.overall_status == "passed"
    assert res.safe_to_continue is True


def test_needs_approval_without_approval_record_fails() -> None:
    verifier = Verifier()
    action = _action("shell", {"command": "ls"}, requires_approval=True)
    decision = _decision(action, "needs_approval")
    result = _result(action, "approval_required", output={})
    res = verifier.verify(action=action, decision=decision, result=result)
    assert res.overall_status == "failed"


def test_safe_read_result_shape_passes() -> None:
    verifier = Verifier()
    action = _action("list_directory", {"path": "."})
    decision = _decision(action, "allow")
    result = _result(action, "success", output={"status": "success", "entries": ["a", "b"]})
    res = verifier.verify(action=action, decision=decision, result=result, started_action_ids={action.action_id})
    assert res.overall_status == "passed"


def test_malformed_read_result_fails() -> None:
    verifier = Verifier()
    action = _action("read_file", {"path": "x"})
    # success status but no output object is malformed.
    check = verifier.verify_read_result_shape(action, _result(action, "success", output=None))
    assert check.status == "failed"
    # a read result carrying mutation metadata is also rejected.
    mutated = _result(action, "success", output={"status": "success", "mutated": True})
    assert verifier.verify_read_result_shape(action, mutated).status == "failed"


def test_write_proposal_requires_approval() -> None:
    verifier = Verifier()
    for tool in ("write_file", "edit_file", "apply_patch"):
        action = _action(tool, {"path": "x", "text": "y"}, requires_approval=True)
        decision = _decision(action, "needs_approval")
        result = _result(action, "approval_required", output={"approval_id": new_id("appr_")})
        check = verifier.verify_mutation_proposal(
            action=action, decision=decision, result=result, started_action_ids=set()
        )
        assert check.status == "passed"


def test_mutation_that_executed_without_approval_fails() -> None:
    verifier = Verifier()
    action = _action("write_file", {"path": "x", "text": "y"}, requires_approval=True)
    decision = _decision(action, "allow")
    result = _result(action, "success", output={"status": "success"})
    check = verifier.verify_mutation_proposal(
        action=action,
        decision=decision,
        result=result,
        started_action_ids={action.action_id},
    )
    assert check.status == "failed"


def test_verifier_output_does_not_expose_private_reasoning() -> None:
    verifier = Verifier()
    action = _action("read_file", {"path": "x"})
    decision = _decision(action, "allow")
    result = _result(action, "success", output={"status": "success", "text": "file body"})
    res = verifier.verify(action=action, decision=decision, result=result, started_action_ids={action.action_id})
    dumped = json.dumps(res.to_dict())
    for forbidden in ("chain_of_thought", "scratchpad", "You are Raiker", "system_prompt", "reasoning_trace"):
        assert forbidden not in dumped


def test_empty_verify_is_skipped_and_safe() -> None:
    res = Verifier().verify()
    assert res.overall_status == "passed"
    assert res.safe_to_continue is True
    assert res.checks[0].status == "skipped"
