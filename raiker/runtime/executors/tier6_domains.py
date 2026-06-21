from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class EmailRuntimeExecutor:
    capability = "email_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Email operation completed.",
            artifacts={"domain": "email"},
        )


class CalendarRuntimeExecutor:
    capability = "calendar_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Calendar operation completed.",
            artifacts={"domain": "calendar"},
        )


class ReminderRuntimeExecutor:
    capability = "reminder_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Reminder operation completed.",
            artifacts={"domain": "reminders"},
        )


class FinanceRuntimeExecutor:
    capability = "finance_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Finance operation completed.",
            artifacts={"domain": "finance"},
        )


class InvestmentRuntimeExecutor:
    capability = "investment_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Investment operation completed.",
            artifacts={"domain": "investments"},
        )


class MedicalRuntimeExecutor:
    capability = "medical_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Medical operation completed.",
            artifacts={"domain": "medical"},
        )


class PregnancyBabyRuntimeExecutor:
    capability = "pregnancy_baby_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Pregnancy/baby operation completed.",
            artifacts={"domain": "pregnancy_baby"},
        )


class CctvRuntimeExecutor:
    capability = "cctv_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="CCTV operation completed.",
            artifacts={"domain": "cctv"},
        )


class HomeSecurityRuntimeExecutor:
    capability = "home_security_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Home security operation completed.",
            artifacts={"domain": "home_security"},
        )


class HardwareOperatorRuntimeExecutor:
    capability = "hardware_operator_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Hardware operator operation completed.",
            artifacts={"domain": "hardware"},
        )