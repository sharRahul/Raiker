from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult, not_implemented

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class _DomainExecutorBase:
    """Tier-6 sensitive-domain executor.

    These domains (email, calendar, finance, medical, CCTV, home security,
    hardware, …) require real external integrations plus a per-domain threat
    model before they can perform any action. Until that work lands, they
    **fail closed** rather than fabricating success — flipping the gate on must
    never make the system claim a medical/finance/security action "completed"
    when nothing happened.
    """

    capability = ""

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return not_implemented(self.capability, action.action_id)


class EmailRuntimeExecutor(_DomainExecutorBase):
    capability = "email_runtime"


class CalendarRuntimeExecutor(_DomainExecutorBase):
    capability = "calendar_runtime"


class FinanceRuntimeExecutor(_DomainExecutorBase):
    capability = "finance_runtime"


class InvestmentRuntimeExecutor(_DomainExecutorBase):
    capability = "investment_runtime"


class MedicalRuntimeExecutor(_DomainExecutorBase):
    capability = "medical_runtime"


class PregnancyBabyRuntimeExecutor(_DomainExecutorBase):
    capability = "pregnancy_baby_runtime"


class CctvRuntimeExecutor(_DomainExecutorBase):
    capability = "cctv_runtime"


class HomeSecurityRuntimeExecutor(_DomainExecutorBase):
    capability = "home_security_runtime"


class HardwareOperatorRuntimeExecutor(_DomainExecutorBase):
    capability = "hardware_operator_runtime"
