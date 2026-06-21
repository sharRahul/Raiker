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


def not_implemented(capability: str, action_id: str) -> ExecutionResult:
    """Fail-closed result for a capability whose executor is not yet implemented.

    Returning this (instead of a fabricated ``ok=True``) preserves the
    no-silent-runtime invariant: a flipped-on gate whose real runtime does not
    exist reports an honest failure rather than a fake success.
    """
    return ExecutionResult(
        ok=False,
        capability=capability,
        action_id=action_id,
        reason_code=f"not_implemented:{capability}",
        summary=f"{capability} runtime is not implemented; failing closed.",
    )