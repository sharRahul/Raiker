from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from raiker.contracts.ids import new_id
from raiker.contracts.models import TOOLS, PolicyDecision, ToolAction, ToolResult
from raiker.verification.models import VerificationCheck, VerificationResult

READ_ONLY_TOOLS = {
    "read_file",
    "list_directory",
    "glob",
    "grep",
    "stat_path",
    "diff_files",
    "git_status",
    "git_diff",
    "git_log",
}
MUTATION_TOOLS = {"write_file", "edit_file", "apply_patch"}

# Keys in a tool result output that would indicate the workspace was mutated. Read-only
# results must never carry these.
_MUTATION_MARKERS = {"mutated", "written", "applied", "deleted", "executed"}


def _check(name: str, status: str, reason: str, metadata: dict[str, object] | None = None) -> VerificationCheck:
    return VerificationCheck(
        check_id=new_id("vchk_"),
        name=name,
        status=status,
        reason=reason,
        metadata=metadata or {},
    )


class Verifier:
    """Deterministic Phase 1/2 verifier.

    This is not a semantic-correctness proof. It performs safety and result-shape checks:
    tool-call schema validation, confirmation that denied/approval-required actions did not
    execute, and read/mutation result-shape validation. It never exposes hidden reasoning,
    chain-of-thought, scratchpads, or system prompts in its output.
    """

    # --- individual checks --------------------------------------------------------

    def verify_tool_call(self, tool_name: object, arguments: object) -> VerificationCheck:
        if not isinstance(tool_name, str) or tool_name not in TOOLS:
            return _check(
                "tool_call_schema",
                "failed",
                "unknown_tool",
                {"tool_name": str(tool_name)},
            )
        if not isinstance(arguments, dict):
            return _check(
                "tool_call_schema",
                "failed",
                "arguments_not_object",
                {"tool_name": tool_name},
            )
        return _check(
            "tool_call_schema",
            "passed",
            "known_tool_and_object_arguments",
            {"tool_name": tool_name},
        )

    def verify_non_execution(
        self,
        *,
        action: ToolAction,
        result: ToolResult,
        started_action_ids: Iterable[str],
    ) -> VerificationCheck:
        started = set(started_action_ids)
        executed = action.action_id in started or result.status in {"success", "failed"}
        if result.status == "denied" and not executed and result.output is None:
            return _check(
                "denied_action_non_execution",
                "passed",
                "denied_action_did_not_execute",
                {"action_id": action.action_id},
            )
        return _check(
            "denied_action_non_execution",
            "failed",
            "denied_action_may_have_executed",
            {"action_id": action.action_id, "status": result.status, "executed": executed},
        )

    def verify_approval_required(
        self,
        *,
        action: ToolAction,
        result: ToolResult,
        started_action_ids: Iterable[str],
    ) -> VerificationCheck:
        started = set(started_action_ids)
        executed = action.action_id in started or result.status in {"success", "failed"}
        has_approval = bool(result.output and result.output.get("approval_id"))
        if result.status == "approval_required" and not executed and has_approval:
            return _check(
                "approval_required_non_execution",
                "passed",
                "stopped_before_execution_with_approval_record",
                {"action_id": action.action_id},
            )
        return _check(
            "approval_required_non_execution",
            "failed",
            "approval_required_action_not_safely_paused",
            {
                "action_id": action.action_id,
                "status": result.status,
                "executed": executed,
                "has_approval": has_approval,
            },
        )

    def verify_read_result_shape(self, action: ToolAction, result: ToolResult) -> VerificationCheck:
        if result.status not in {"success", "failed"}:
            return _check(
                "read_result_shape",
                "failed",
                "unexpected_status_for_read_tool",
                {"tool_name": action.tool_name, "status": result.status},
            )
        if result.status == "success":
            output = result.output
            if not isinstance(output, dict):
                return _check(
                    "read_result_shape",
                    "failed",
                    "read_success_output_not_object",
                    {"tool_name": action.tool_name},
                )
            mutation_hit = next(
                (m for m in _MUTATION_MARKERS if bool(output.get(m))), None
            )
            if mutation_hit is not None:
                return _check(
                    "read_result_shape",
                    "failed",
                    "read_result_carries_mutation_metadata",
                    {"tool_name": action.tool_name, "marker": mutation_hit},
                )
            if output.get("requires_approval"):
                return _check(
                    "read_result_shape",
                    "failed",
                    "read_result_unexpectedly_requires_approval",
                    {"tool_name": action.tool_name},
                )
        return _check(
            "read_result_shape",
            "passed",
            "read_result_shape_ok",
            {"tool_name": action.tool_name, "status": result.status},
        )

    def verify_mutation_proposal(
        self,
        *,
        action: ToolAction,
        decision: PolicyDecision,
        result: ToolResult,
        started_action_ids: Iterable[str],
    ) -> VerificationCheck:
        started = set(started_action_ids)
        executed = action.action_id in started or result.status in {"success", "failed"}
        requires_approval = decision.decision == "needs_approval" or decision.requires_user_approval
        has_preview = bool(
            result.output and (result.output.get("proposal_preview") or result.output.get("reasons"))
        )
        if requires_approval and not executed and result.status == "approval_required":
            return _check(
                "mutation_proposal_safety",
                "passed",
                "mutation_requires_approval_and_did_not_execute",
                {"action_id": action.action_id, "has_preview": has_preview},
            )
        return _check(
            "mutation_proposal_safety",
            "failed",
            "mutation_proposal_not_safely_gated",
            {
                "action_id": action.action_id,
                "decision": decision.decision,
                "status": result.status,
                "executed": executed,
            },
        )

    # --- aggregation --------------------------------------------------------------

    def verify(
        self,
        *,
        action: ToolAction | None = None,
        decision: PolicyDecision | None = None,
        result: ToolResult | None = None,
        started_action_ids: Iterable[str] = (),
        rejected_tool_call: dict[str, Any] | None = None,
    ) -> VerificationResult:
        checks: list[VerificationCheck] = []
        started = set(started_action_ids)

        if rejected_tool_call is not None:
            checks.append(
                _check(
                    "tool_call_schema",
                    "failed",
                    rejected_tool_call.get("reason", "rejected_tool_call"),
                    {"tool_name": str(rejected_tool_call.get("tool_name"))},
                )
            )

        if action is not None and decision is not None and result is not None:
            checks.append(self.verify_tool_call(action.tool_name, action.arguments))
            if decision.decision == "deny":
                checks.append(
                    self.verify_non_execution(
                        action=action, result=result, started_action_ids=started
                    )
                )
            elif decision.decision == "needs_approval":
                if action.tool_name in MUTATION_TOOLS:
                    checks.append(
                        self.verify_mutation_proposal(
                            action=action,
                            decision=decision,
                            result=result,
                            started_action_ids=started,
                        )
                    )
                else:
                    checks.append(
                        self.verify_approval_required(
                            action=action, result=result, started_action_ids=started
                        )
                    )
            elif decision.decision == "allow":
                if action.tool_name in READ_ONLY_TOOLS:
                    checks.append(self.verify_read_result_shape(action, result))
                elif action.tool_name in MUTATION_TOOLS:
                    checks.append(
                        self.verify_mutation_proposal(
                            action=action,
                            decision=decision,
                            result=result,
                            started_action_ids=started,
                        )
                    )

        if not checks:
            checks.append(
                _check("no_verification_required", "skipped", "no_tool_action_to_verify")
            )

        failed = [c for c in checks if c.status == "failed"]
        overall_status = "failed" if failed else "passed"
        safe_to_continue = not failed
        return VerificationResult(
            result_id=new_id("vres_"),
            overall_status=overall_status,
            checks=checks,
            safe_to_continue=safe_to_continue,
            metadata={"check_count": len(checks), "failed_check_count": len(failed)},
        )
