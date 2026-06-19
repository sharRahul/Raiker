from __future__ import annotations

from pathlib import Path

from raiker.contracts.models import ClientMetadata
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.hooks.contracts import HOOK_SCOPES, HookInput, HookOutcome
from raiker.hooks.decision import HandlerDecision, combine
from raiker.hooks.handlers.builtin import BuiltinHookError, run_builtin
from raiker.hooks.handlers.command import CommandHookError, CommandHookTimeout, run_command
from raiker.hooks.matchers import guard_matches, matches
from raiker.hooks.registry import HooksRegistry


class HookDispatcher:
    """Runs configured hooks at a lifecycle point and aggregates their decisions.

    Hooks can only make an action stricter (deny/ask); they can never bypass the tool broker,
    the policy engine, or the event log. When no hooks are configured the dispatcher is inactive
    and does nothing, so the runtime behaves exactly as it did without hooks.
    """

    def __init__(
        self,
        registry: HooksRegistry,
        *,
        workspace_root: str | Path,
        writer: EventLogWriter | None = None,
    ) -> None:
        self.registry = registry
        self.workspace_root = Path(workspace_root)
        self.writer = writer

    def is_active(self) -> bool:
        return not self.registry.is_empty()

    def _emit(
        self,
        event_type: str,
        payload: dict[str, object],
        *,
        session_id: str | None,
        turn_id: str | None,
        client: ClientMetadata | None,
    ) -> None:
        if self.writer is None or session_id is None:
            return
        self.writer.append(
            make_event(
                session_id=session_id,
                turn_id=turn_id,
                event_type=event_type,
                actor="hooks",
                payload=payload,
                client=client,
            )
        )

    def dispatch(
        self,
        hook_input: HookInput,
        *,
        session_id: str | None,
        turn_id: str | None,
        client: ClientMetadata | None = None,
    ) -> HookOutcome:
        rules = sorted(
            self.registry.for_event(hook_input.event_name),
            key=lambda rule: HOOK_SCOPES.index(rule.scope),
        )
        decisions: list[HandlerDecision] = []
        reasons: list[str] = []
        context_additions: list[str] = []
        executed: list[str] = []
        matched_any = False
        for rule in rules:
            if not matches(rule.matcher, hook_input.tool_name):
                continue
            if not guard_matches(rule.if_guard, hook_input.tool_name, hook_input.tool_input):
                continue
            matched_any = True
            self._emit(
                "hook_matched",
                {"event": hook_input.event_name, "matcher": rule.matcher, "scope": rule.scope},
                session_id=session_id,
                turn_id=turn_id,
                client=client,
            )
            for handler in rule.handlers:
                try:
                    if handler.type == "builtin":
                        assert handler.builtin is not None
                        output = run_builtin(handler.builtin, hook_input)
                        authority = True
                    else:
                        output = run_command(handler, hook_input, self.workspace_root)
                        authority = handler.decision_authority
                except CommandHookTimeout:
                    self._emit(
                        "hook_timeout",
                        {"handler_id": handler.id, "scope": rule.scope},
                        session_id=session_id,
                        turn_id=turn_id,
                        client=client,
                    )
                    continue
                except (CommandHookError, BuiltinHookError) as exc:
                    self._emit(
                        "hook_failed",
                        {"handler_id": handler.id, "scope": rule.scope, "error": str(exc)},
                        session_id=session_id,
                        turn_id=turn_id,
                        client=client,
                    )
                    continue
                executed.append(handler.id)
                self._emit(
                    "hook_executed",
                    {
                        "handler_id": handler.id,
                        "scope": rule.scope,
                        "decision": output.decision,
                        "has_authority": authority,
                    },
                    session_id=session_id,
                    turn_id=turn_id,
                    client=client,
                )
                decisions.append(
                    HandlerDecision(rule.scope, output.decision, authority, output.decision_reason)
                )
                if output.decision_reason:
                    reasons.append(output.decision_reason)
                if output.additional_context:
                    context_additions.append(output.additional_context)
        if not matched_any:
            return HookOutcome()
        final = combine(decisions)
        self._emit(
            "hook_decision",
            {"event": hook_input.event_name, "decision": final, "reasons": reasons},
            session_id=session_id,
            turn_id=turn_id,
            client=client,
        )
        return HookOutcome(
            decision=final,
            reasons=reasons,
            additional_context=context_additions,
            executed=executed,
        )
