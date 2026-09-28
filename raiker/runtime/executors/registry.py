from __future__ import annotations

from typing import TYPE_CHECKING, Any

from raiker.runtime.executors.base import ExecutionResult, Executor

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class RoutedExecutor:
    """An executor as the registry hands it out: runnable only while routed.

    CR-01 — the registry used to store an executor and return that same object,
    so anything holding a registry — a future route handler, a scheduled job, a
    helper — could fetch a real side-effecting executor and call it with no
    gate, no decision mode, no approval and no audit. The review asked for
    runtime-issued authority on every call, and the runtime already issues one:
    ``RuntimeAuthority.route_action`` opens a :func:`routed_dispatch` for exactly
    one capability and one action around ``executor.execute`` (CR-03).

    This wrapper checks for that token before the executor runs. A call with no
    live dispatch, a dispatch of another action, or a dispatch of another
    capability returns a failed result naming why, and the executor itself is
    never entered, so there is no side effect to undo.

    What it does not do is stop code that constructs an executor class itself;
    ``tests/test_executor_authority_boundary.py`` holds that line, by failing on
    any construction outside the registry builder that is not listed with its
    reason.
    """

    __slots__ = ("_inner", "capability")

    def __init__(self, capability: str, inner: Executor) -> None:
        self.capability = capability
        self._inner = inner

    @property
    def inner(self) -> Executor:
        """The executor this guards, for code that inspects rather than runs it."""
        return self._inner

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        # Imported here: the authority package imports this registry.
        from raiker.runtime.authority.routed import current_routed_authority

        token = current_routed_authority(action.action_id)
        if token is None or token.capability != self.capability:
            return ExecutionResult(
                ok=False,
                capability=self.capability,
                action_id=action.action_id,
                reason_code="executor_not_routed",
                summary=(
                    f"{self.capability} refused: it runs only when the runtime "
                    "authority dispatches it, and nothing did."
                ),
            )
        return self._inner.execute(action, principal)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class ExecutorRegistry:
    def __init__(self) -> None:
        self._executors: dict[str, RoutedExecutor] = {}

    def register(self, capability: str, executor: Executor) -> None:
        self._executors[capability] = (
            executor
            if isinstance(executor, RoutedExecutor) and executor.capability == capability
            else RoutedExecutor(capability, executor)
        )

    def get(self, capability: str) -> RoutedExecutor | None:
        return self._executors.get(capability)

    def has(self, capability: str) -> bool:
        return capability in self._executors

    def capabilities(self) -> frozenset[str]:
        return frozenset(self._executors)
