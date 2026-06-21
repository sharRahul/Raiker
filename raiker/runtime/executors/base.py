from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class Executor(Protocol):
    capability: str

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult: ...


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    capability: str
    action_id: str
    reason_code: str | None = None
    summary: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)