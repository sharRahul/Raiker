from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from raiker.contracts.models import ClientMetadata
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.hooks.contracts import HOOK_SCOPES, HookHandler, HookInput, HookOutcome, HookOutput
from raiker.hooks.decision import HandlerDecision, combine
from raiker.hooks.handlers.builtin import BuiltinHookError, run_builtin
from raiker.hooks.handlers.command import CommandHookError, CommandHookTimeout, run_command
from raiker.hooks.handlers.prompt import PromptHookError
from raiker.hooks.matchers import guard_matches, matches
from raiker.hooks.registry import HooksRegistry
from raiker.models.exceptions import ModelProviderError


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
        prompt_runner: Callable[[HookHandler, HookInput], Awaitable[HookOutput]] | None = None,
    ) -> None:
        self.registry = registry
        self.workspace_root = Path(workspace_root)
        self.writer = writer
        self.prompt_runner = prompt_runner
        self._disabled = False

    def set_disabled(self, disabled: bool) -> None:
        """Apply the owner's off switch (BUG-222), refreshed once per turn.

        Read per turn rather than per call: it is a setting the owner changes
        from a page, so it has to take effect without a restart, and a store read
        on every tool call to answer a question that cannot change mid-turn is
        the wrong trade.
        """
        self._disabled = disabled

    def is_active(self) -> bool:
        return not self._disabled and not self.registry.is_empty()

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
        payload = {**payload, "summary": self._summary(event_type, payload)}
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

    @staticmethod
    def _summary(event_type: str, payload: dict[str, object]) -> str:
        """One line naming what this row is about, for the surfaces that list it.

        The Hooks tab showed each row as its verb and a relative time — "matched,
        two minutes ago" — which was readable while the build emitted a handful of
        events and became unreadable at twenty: an owner watching for one rule
        could not tell whether it was theirs that ran. The event and the handler
        are the two facts that answer it, and both are already in the payload the
        row is built from, so this is a label rather than new data. Nothing here
        reads a hook's own input or output, so a summary can never carry the
        content those payloads deliberately exclude.

        The verb is deliberately absent: the row already carries it as a tag, and
        repeating it read as "matched — matched: PostToolBatch". A row with
        neither fact gets no summary rather than an echo of its own tag.
        """
        event = str(payload.get("event") or "")
        handler = str(payload.get("handler_id") or "")
        return " · ".join(part for part in (event, handler) if part)

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
                    elif handler.type == "prompt":
                        if self.prompt_runner is None:
                            raise CommandHookError("prompt_handler_model_unavailable")
                        output = asyncio.run(
                            asyncio.wait_for(
                                self.prompt_runner(handler, hook_input),
                                timeout=handler.timeout_ms / 1000,
                            )
                        )
                        # Model output is never part of Raiker's authority chain.
                        authority = False
                    else:
                        output = run_command(handler, hook_input, self.workspace_root)
                        authority = handler.decision_authority
                except (CommandHookTimeout, TimeoutError):
                    self._emit(
                        "hook_timeout",
                        {"event": hook_input.event_name, "handler_id": handler.id, "scope": rule.scope},
                        session_id=session_id,
                        turn_id=turn_id,
                        client=client,
                    )
                    continue
                except (CommandHookError, BuiltinHookError, PromptHookError, ModelProviderError) as exc:
                    self._emit(
                        "hook_failed",
                        {"event": hook_input.event_name, "handler_id": handler.id, "scope": rule.scope, "error": str(exc)},
                        session_id=session_id,
                        turn_id=turn_id,
                        client=client,
                    )
                    continue
                executed.append(handler.id)
                self._emit(
                    "hook_executed",
                    {
                        "event": hook_input.event_name,
                        "handler_id": handler.id,
                        "scope": rule.scope,
                        "decision": output.decision,
                        "has_authority": authority,
                        **{
                            key: value
                            for key, value in output.metadata.items()
                            if key
                            in {
                                "provider",
                                "model",
                                "input_tokens",
                                "output_tokens",
                                "cache_read_tokens",
                                "cache_write_tokens",
                            }
                        },
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

    async def adispatch(
        self,
        hook_input: HookInput,
        *,
        session_id: str | None,
        turn_id: str | None,
        client: ClientMetadata | None = None,
    ) -> HookOutcome:
        """Dispatch without blocking an active turn's event loop.

        The synchronous path remains the authority used by the broker and
        background services. Async turn call sites move that exact path to a
        worker; a prompt handler owns a small private event loop there, while a
        command handler keeps its existing bounded subprocess behavior.
        """
        return await asyncio.to_thread(
            self.dispatch,
            hook_input,
            session_id=session_id,
            turn_id=turn_id,
            client=client,
        )
