from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_STATUSES = {"passed", "failed", "skipped"}


@dataclass(frozen=True)
class VerificationCheck:
    check_id: str
    name: str
    status: str
    reason: str
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class VerificationResult:
    result_id: str
    overall_status: str
    checks: list[VerificationCheck]
    safe_to_continue: bool
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def failed_checks(self) -> list[VerificationCheck]:
        return [c for c in self.checks if c.status == "failed"]

    def to_dict(self) -> dict[str, object]:
        return {
            "result_id": self.result_id,
            "overall_status": self.overall_status,
            "checks": [c.to_dict() for c in self.checks],
            "safe_to_continue": self.safe_to_continue,
            "metadata": dict(self.metadata),
        }

    def event_payload(self) -> dict[str, object]:
        return {
            "result_id": self.result_id,
            "overall_status": self.overall_status,
            "safe_to_continue": self.safe_to_continue,
            "check_count": len(self.checks),
            "failed_check_count": len(self.failed_checks),
            "check_names": [c.name for c in self.checks],
        }
