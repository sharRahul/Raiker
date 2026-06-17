from __future__ import annotations

from dataclasses import dataclass

from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolResult


@dataclass(frozen=True)
class VerificationResult:
    verification_id: str
    status: str
    checks: list[dict[str, str]]
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "verification_id": self.verification_id,
            "status": self.status,
            "checks": self.checks,
            "notes": self.notes,
        }


class VerificationStub:
    def verify_tool_result(self, result: ToolResult | None) -> VerificationResult:
        if result is None:
            return VerificationResult(
                verification_id=new_id("ver_"),
                status="passed",
                checks=[{"name": "no_tool_required", "status": "passed"}],
                notes=[],
            )
        if result.status == "success":
            return VerificationResult(
                verification_id=new_id("ver_"),
                status="passed",
                checks=[{"name": "tool_result_success", "status": "passed"}],
                notes=[],
            )
        return VerificationResult(
            verification_id=new_id("ver_"),
            status="partial" if result.status == "approval_required" else "failed",
            checks=[{"name": f"tool_result_{result.status}", "status": result.status}],
            notes=["Phase 1 verification stub records status only."],
        )
