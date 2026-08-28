from __future__ import annotations

import asyncio
import json
from pathlib import Path

from raiker.channels.registry import ConnectorRegistry
from raiker.checkpoints.service import CheckpointService
from raiker.contracts.models import (
    DEFAULT_MAX_TOOL_CALLS,
    LEGACY_PARKED_FOR_APPROVAL_NOTICE,
    PARKED_FOR_APPROVAL_NOTICE,
    AgentResponse,
    ClientMetadata,
    ContractValidationError,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
    normalize_input_mode,
    normalize_prompt_surface,
)
from raiker.contracts.streaming import FINAL, StreamEvent
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.hooks.contracts import HookInput, HookOutcome
from raiker.hooks.dispatcher import HookDispatcher
from raiker.hooks.handlers.prompt import prompt_runner
from raiker.hooks.owner_switch import hooks_disabled
from raiker.hooks.registry import HooksRegistry
from raiker.models.connections import get_model_connection
from raiker.models.contracts import ModelMessage, ToolCallProposal
from raiker.models.policy_state import provider_runtime_policy_from_gates
from raiker.models.readiness import (
    ModelNotReady,
    ModelReadinessService,
    ProviderCatalogueProbe,
)
from raiker.models.registry import ModelProfileRegistry, RegistryError, profile_with_model
from raiker.models.router import ModelRouter
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.identity.lifecycle import (
    TrustedTurnIdentity,
    TurnMachineIdentityLifecycle,
)
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.runtime.turn_suspension import (
    TurnSuspensionError,
    deserialize_messages,
    deserialize_pending_calls,
    resumed_call_row_status,
)
from raiker.sessions.manager import SessionManager
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tools.broker import ToolBroker

# Upper bound on the assistant reply persisted with a turn.
TURN_SUMMARY_MAX_CHARS = 8000

class AgentGateway:
    def __init__(self, workspace_root: str | Path, principal_id: str = "local_user") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.store = SQLiteStore(self.workspace_root)
        self.writer = EventLogWriter(self.store)
        self.owner_principal_id = principal_id
        self.machine_identities = TurnMachineIdentityLifecycle(
            self.workspace_root, self.store, self.writer
        )
        self.sessions = SessionManager(self.store, self.workspace_root)
        # Local-account owner for session attribution: sessions this principal
        # creates are stamped with its user_id so accounts stay isolated. Legacy
        # principals without a user mapping leave sessions unattributed (shared).
        principal_row = self.store.get_principal(principal_id)
        self._owner_user_id = (
            str(principal_row["delegated_by_user_id"])
            if principal_row and principal_row.get("delegated_by_user_id")
            else None
        )
        self.checkpoints = CheckpointService(self.store)
        policy_engine = PolicyEngine(StaticPolicyConfig(self.workspace_root))
        self.hook_dispatcher = HookDispatcher(
            HooksRegistry.load(self.workspace_root),
            workspace_root=self.workspace_root,
            writer=self.writer,
        )
        self.tool_broker = ToolBroker(
            workspace_root=self.workspace_root,
            policy_engine=policy_engine,
            store=self.store,
            writer=self.writer,
            hook_dispatcher=self.hook_dispatcher,
            principal_id=principal_id,
        )
        self.model_registry = ModelProfileRegistry.load()
        self.connector_registry = ConnectorRegistry.load()
        self.store.upsert_model_profiles(self.model_registry.list_profiles())
        self.store.upsert_connector_profiles(self.connector_registry.list_profiles())
        # Provider policy is derived from the persisted capability gates:
        # hosted/private-network model access stays fail-closed unless the
        # owner enabled the corresponding gate through the governed control
        # plane. The owner egress allowlist is re-checked per provider build.
        self.model_router = ModelRouter(
            self.model_registry,
            self.writer,
            runtime_policy=provider_runtime_policy_from_gates(self.store, principal_id),
            connection_resolver=lambda profile_id: get_model_connection(
                self.store, principal_id, profile_id
            ),
        )
        # Native default backend: the one explicitly marked profile in the shipped registry;
        # production never falls back to deterministic test providers.
        # Honor the operator's selected model profile (e.g. via `/model use`); fall back to the native default.
        self.default_provider = self._resolve_default_provider()
        self.hook_dispatcher.prompt_runner = prompt_runner(
            self.model_router, self.default_provider
        )
        self.runtime = RuntimeOrchestrator(
            workspace_root=self.workspace_root,
            writer=self.writer,
            tool_broker=self.tool_broker,
            model_router=self.model_router,
            default_provider=self.default_provider,
            profile_resolver=self._resolve_profile_for_turn,
            fallback_resolver=self._resolve_fallback_chain,
        )

    def _resolve_default_provider(self) -> tuple[str, str]:
        """Pick the runtime model from the persisted selection, else the native default.

        A selection made with ``/model use`` is stored as a ``ModelSessionState``. When it
        resolves to a concrete model, the orchestrator uses it; otherwise (no selection, or an
        unresolved placeholder model) it falls back to the registry's native default. This is the
        only place selection is bound to a turn, so the CLI and any future client share it.
        """
        native_default = self.model_router.default_provider()
        state = (
            self.store.load_principal_model_state(self.tool_broker.principal_id)
            if self.store.get_account(self.tool_broker.principal_id) is not None
            else self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        )
        if state is None:
            return native_default
        try:
            profile = self.model_registry.resolve_profile_id(state.profile_id)
        except RegistryError:
            return native_default
        effective_model = state.model or profile.model
        if not effective_model or "<" in effective_model:
            return native_default
        if effective_model != profile.model:
            self.model_registry.register(profile_with_model(profile, effective_model))
        return (profile.provider, effective_model)

    def _resolve_profile_for_turn(
        self, profile_id: str, model: str | None = None
    ) -> tuple[str, str] | None:
        """Resolve an explicit per-turn profile choice to ``(provider, model)``.

        An explicit per-turn ``model`` wins, then the operator's persisted
        selection for that profile, then the profile's own model. Test-harness
        profiles and unresolved ``<model>`` placeholders return None so the turn
        falls back to the operator's persisted selection — the web/REST surface
        only ever runs working backends. Provider policy (gates, egress
        allowlist, API keys) is still enforced downstream by the model router.
        """
        try:
            profile = self.model_registry.resolve_profile_id(profile_id)
        except RegistryError:
            return None
        if bool(profile.raw.get("test_only", False)):
            return None
        effective_model = profile.model
        state = (
            self.store.load_principal_model_state(self.tool_broker.principal_id)
            if self.store.get_account(self.tool_broker.principal_id) is not None
            else self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        )
        if state is not None and state.profile_id == profile.profile_id and state.model:
            effective_model = state.model
        if not effective_model or "<" in effective_model:
            # The session state names one profile only, so every *other* profile
            # the owner pinned a model for — every fallback entry, in practice —
            # keeps its choice in the configured-model table. Without this read
            # the whole fallback sequence silently drops hosted providers, all of
            # which ship a `<model>` placeholder.
            effective_model = self._configured_model(profile.profile_id) or effective_model
        if model:
            effective_model = model
        if not effective_model or "<" in effective_model:
            return None
        # Register the concrete choice so the router can resolve (provider, model)
        # even when the profile ships a different or placeholder model. Policy is
        # unchanged — the registered copy inherits the profile's gates/egress/key.
        if effective_model != profile.model and not self.model_registry.find(
            profile.provider, effective_model
        ):
            self.model_registry.register(profile_with_model(profile, effective_model))
        return (profile.provider, effective_model)

    def _configured_model(self, profile_id: str) -> str | None:
        """The owner's most recent pinned model for one profile, if any."""
        try:
            pairs = self.store.list_configured_models(self.tool_broker.principal_id)
        except Exception:  # noqa: BLE001 — an unreadable pin resolves nothing
            return None
        for candidate_profile, candidate_model in reversed(list(pairs or [])):
            if candidate_profile == profile_id and candidate_model:
                return str(candidate_model)
        return None

    def _resolve_fallback_chain(self) -> list[tuple[str, str]]:
        """Resolve the user-owned ordered fallback sequence to ``(provider, model)`` pairs.

        Read fresh each turn from the persisted sequence. Each profile id is
        resolved through the same rules as an explicit per-turn choice
        (``_resolve_profile_for_turn``), so test-harness profiles and unresolved
        ``<model>`` placeholders are dropped and duplicates collapse. Provider
        policy (gates, egress allowlist, API keys) is still enforced downstream by
        the model router when each candidate is actually tried.
        """
        chain: list[tuple[str, str]] = []
        # Owner-scoped first, terminal only when the owner saved none. Keying off
        # an account row instead would ignore the sequence a CLI-bootstrapped
        # owner saved against their own principal, and the readiness gate reads
        # the chain the same way — the two must not disagree.
        fallback_ids = self.store.load_principal_model_fallback_sequence(
            self.tool_broker.principal_id
        ) or self.store.load_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID)
        for profile_id in fallback_ids:
            resolved = self._resolve_profile_for_turn(profile_id)
            if resolved is not None and resolved not in chain:
                chain.append(resolved)
        return chain

    async def _dispatch_lifecycle_hook(
        self,
        event_name: str,
        envelope: PromptEnvelope,
        context: dict[str, object] | None = None,
    ) -> HookOutcome:
        resolved = (
            self._resolve_profile_for_turn(
                envelope.options.model_profile, envelope.options.model or None
            )
            if envelope.options.model_profile
            else None
        ) or self.default_provider
        return await self.hook_dispatcher.adispatch(
            HookInput(
                event_name=event_name,
                tool_name=None,
                tool_input={},
                context={
                    "prompt_length": len(envelope.prompt.text),
                    "_model_provider": resolved[0],
                    "_model": resolved[1],
                    **(context or {}),
                },
                session_id=envelope.session_id,
                turn_id=envelope.turn_id,
                cwd=str(self.workspace_root),
            ),
            session_id=envelope.session_id,
            turn_id=envelope.turn_id,
            client=envelope.client,
        )

    async def _adispatch_turn_end_hook(
        self, envelope: PromptEnvelope, response: AgentResponse
    ) -> None:
        """`Stop` when the turn produced an answer, `StopFailure` when it did not.

        Claude Code's `Stop` fires when the agent stops responding, and the split
        exists because the two are not the same question. A turn parked on an
        approval has not finished — it is waiting — and a turn the owner stopped
        did what it was told. Reporting either as a clean `Stop` would let a rule
        written to react to *completion* fire on a run that never completed, which
        is the same class of dishonesty as an event that never fires at all.

        Observation only: both land after the checkpoint and the turn row are
        written, so nothing a handler returns can change an outcome that already
        happened. That is deliberate — a hook may make an action stricter before
        it runs, never rewrite it afterwards.

        The reply text is **not** passed. A `command` handler is a subprocess, and
        `config/hooks.json` travels with a repository, so a project a workspace
        cloned could hand a script whatever this context carries. A rule reacting
        to a turn ending needs to know *whether* and *why*, which is what `status`
        is; a handler that genuinely needs what was said can read the audit trail
        under its own authority rather than being fed it. `UserPromptSubmit`
        already passes the prompt's length rather than the prompt for the same
        reason, and this keeps the two ends of a turn consistent.
        """
        if not self.hook_dispatcher.is_active():
            return
        completed = response.status == "completed"
        await self._dispatch_lifecycle_hook(
            "Stop" if completed else "StopFailure",
            envelope,
            {"status": response.status, "reply_length": len(response.message)},
        )

    def _dispatch_turn_end_hook(
        self, envelope: PromptEnvelope, response: AgentResponse
    ) -> None:
        """Synchronous compatibility boundary used by lifecycle tests/callers."""
        asyncio.run(self._adispatch_turn_end_hook(envelope, response))

    @staticmethod
    def _coerce_envelope(
        envelope: PromptEnvelope | dict[str, object],
    ) -> tuple[PromptEnvelope | None, AgentResponse | None]:
        try:
            prompt_envelope = (
                envelope
                if isinstance(envelope, PromptEnvelope)
                else PromptEnvelope.from_dict(envelope)  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, ContractValidationError, ValueError) as exc:
            return None, AgentResponse(
                request_id="req_invalid",
                session_id="sess_invalid",
                turn_id="turn_invalid",
                status="failed",
                message=f"Invalid prompt envelope: {exc}",
            )
        return prompt_envelope, None

    async def _aprepare_turn(self, prompt_envelope: PromptEnvelope) -> TrustedTurnIdentity:
        input_mode = normalize_input_mode(
            prompt_envelope.prompt.metadata.get("input_mode", "typed")
        )
        surface = normalize_prompt_surface(
            prompt_envelope.prompt.metadata.get("surface", "chat")
        )
        # BUG-222 — the owner's hooks off switch, re-read per turn so toggling it
        # takes effect without restarting the host.
        self.hook_dispatcher.set_disabled(
            hooks_disabled(self.workspace_root, self.owner_principal_id)
        )
        existing_session = self.sessions.load_session(prompt_envelope.session_id)
        self.sessions.get_or_create(prompt_envelope.session_id, user_id=self._owner_user_id)
        self.sessions.track_turn(
            prompt_envelope.session_id,
            prompt_envelope.turn_id,
            prompt_envelope.prompt.text,
        )
        self.writer.append(
            make_event(
                session_id=prompt_envelope.session_id,
                turn_id=prompt_envelope.turn_id,
                event_type="prompt_received",
                actor="agent_gateway",
                payload={
                    "client_type": prompt_envelope.client.type,
                    "prompt_length": len(prompt_envelope.prompt.text),
                    "input_mode": input_mode,
                    # Recorded so the audit trail states which operating protocol
                    # the turn ran under rather than leaving it to be inferred.
                    "surface": surface,
                },
                client=prompt_envelope.client,
            )
        )
        if self.hook_dispatcher.is_active():
            additions: list[str] = []
            if existing_session is None:
                started = await self._dispatch_lifecycle_hook("SessionStart", prompt_envelope)
                additions.extend(started.additional_context)
            submitted = await self._dispatch_lifecycle_hook("UserPromptSubmit", prompt_envelope)
            additions.extend(submitted.additional_context)
            if additions:
                prompt_envelope.prompt.metadata["_hook_context"] = additions
        return self.machine_identities.start(
            owner_principal_id=self.owner_principal_id,
            session_id=prompt_envelope.session_id,
            turn_id=prompt_envelope.turn_id,
            role_ids=("assistant",),
        )

    def _prepare_turn(self, prompt_envelope: PromptEnvelope) -> TrustedTurnIdentity:
        """Synchronous compatibility boundary used by direct runtime callers."""
        return asyncio.run(self._aprepare_turn(prompt_envelope))

    async def _model_readiness_refusal(
        self, prompt_envelope: PromptEnvelope
    ) -> AgentResponse | None:
        """Refuse a turn only when the model is genuinely unavailable (BUG-238).

        ``require_ready_async`` re-takes an observation that has merely aged out
        rather than treating the TTL as evidence that the model was never set
        up. A turn still never runs on an observation older than the owner's
        window — the stale one is replaced by a fresh check first — but an owner
        who set a model up once is not asked to set it up again after a restart.
        """
        try:
            await ModelReadinessService(
                self.store,
                probe=ProviderCatalogueProbe(self.store),
            ).require_ready_async(
                self.owner_principal_id,
                prompt_envelope.options.model_profile,
                prompt_envelope.options.model,
            )
        except ModelNotReady as exc:
            return AgentResponse(
                request_id=prompt_envelope.request_id,
                session_id=prompt_envelope.session_id,
                turn_id=prompt_envelope.turn_id,
                status="failed",
                message=exc.readiness.summary,
                client=prompt_envelope.client,
            )
        except (KeyError, ValueError):
            return AgentResponse(
                request_id=prompt_envelope.request_id,
                session_id=prompt_envelope.session_id,
                turn_id=prompt_envelope.turn_id,
                status="failed",
                message="The selected model profile is not available.",
                client=prompt_envelope.client,
            )
        return None

    def _rotate_identity_for_resume(
        self, envelope: PromptEnvelope
    ) -> TrustedTurnIdentity:
        row = self.store.get_turn_machine_identity_for_turn(
            owner_principal_id=self.owner_principal_id,
            session_id=envelope.session_id,
            turn_id=envelope.turn_id,
        )
        if row is None:
            raise TurnSuspensionError("machine_identity_missing")
        return self.machine_identities.rotate(
            owner_principal_id=self.owner_principal_id,
            session_id=envelope.session_id,
            turn_id=envelope.turn_id,
            principal_id=str(row["principal_id"]),
            role_ids=("assistant",),
        )

    @staticmethod
    def _persisted_summary(response: AgentResponse) -> str:
        """The reply this turn stores in its transcript row (BUG-73).

        A turn parked on an approval has no answer yet — it has a *state*. The
        pre-approval notice ("Approval required for local action. No command was
        executed.") used to be stored as though it were the answer, and the
        resume was the only thing that ever replaced it. One live round ended
        with that sentence sitting, durably, beneath the chip for the file the
        approval had just written: the write happened, was checkpointed, and
        changed the filesystem, and reopening the conversation showed the denial
        again.

        Nothing about a race can produce that now, because the false claim is
        never written. An interrupted resume leaves the turn with no stored
        answer and its parked approval still showing — which is what actually
        happened — and the resume writes the real one over an empty row. The old
        wording is refused alongside the new one so a workspace written before
        this change cannot re-persist it on a resume either.
        """
        if response.message in {
            PARKED_FOR_APPROVAL_NOTICE,
            LEGACY_PARKED_FOR_APPROVAL_NOTICE,
        }:
            return ""
        return response.message[:TURN_SUMMARY_MAX_CHARS]

    async def _afinalize_turn(
        self, prompt_envelope: PromptEnvelope, response: AgentResponse
    ) -> AgentResponse:
        checkpoint, checkpoint_path = self.checkpoints.write_turn_checkpoint(
            session_id=prompt_envelope.session_id,
            turn_id=prompt_envelope.turn_id,
            runtime_state="CLOSED",
            summary=response.message[:500],
            last_event_id=response.last_event_id or self.writer.last_event_id or "evt_missing",
        )
        self.writer.append(
            make_event(
                session_id=prompt_envelope.session_id,
                turn_id=prompt_envelope.turn_id,
                event_type="checkpoint_created",
                actor="checkpoint_service",
                payload={
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "summary": checkpoint.summary,
                    "last_event_id": checkpoint.last_event_id,
                },
                client=prompt_envelope.client,
            )
        )
        self.writer.append(
            make_event(
                session_id=prompt_envelope.session_id,
                turn_id=prompt_envelope.turn_id,
                event_type="turn_closed",
                actor="agent_gateway",
                payload={"status": response.status, "summary": response.message[:200]},
                client=prompt_envelope.client,
            )
        )
        # The stored reply is the conversation record: the Chat view renders it as
        # the assistant's message and the orchestrator replays it as history on
        # the next turn. 500 characters truncated both, so a resumed conversation
        # lost most of every answer. The bound stays generous but finite — a turn
        # row is a transcript entry, not an unbounded blob.
        self.sessions.close_turn(
            prompt_envelope.turn_id,
            response.status,
            self._persisted_summary(response),
        )
        if response.status == "completed":
            try:
                from raiker.memory.entity_extraction import propose_completed_turn_memories

                summary = propose_completed_turn_memories(
                    self.store,
                    owner_principal_id=self.owner_principal_id,
                    session_id=prompt_envelope.session_id,
                    turn_id=prompt_envelope.turn_id,
                    source_event_id=self.writer.last_event_id or "evt_missing",
                    user_text=prompt_envelope.prompt.text,
                    assistant_text=self._persisted_summary(response),
                )
                self.writer.append(
                    make_event(
                        session_id=prompt_envelope.session_id,
                        turn_id=prompt_envelope.turn_id,
                        event_type="memory_relationship_extraction_completed",
                        actor="memory_entity_extractor",
                        payload={
                            "scanned": summary.scanned,
                            "proposed": summary.proposed,
                            "skipped": summary.skipped,
                            "already_present": summary.already_present,
                        },
                        client=prompt_envelope.client,
                    )
                )
            except Exception as exc:  # extraction never invalidates a completed turn
                self.writer.append(
                    make_event(
                        session_id=prompt_envelope.session_id,
                        turn_id=prompt_envelope.turn_id,
                        event_type="memory_relationship_extraction_failed",
                        actor="memory_entity_extractor",
                        payload={"reason_code": type(exc).__name__},
                        client=prompt_envelope.client,
                    )
                )
        await self._adispatch_turn_end_hook(prompt_envelope, response)
        events_path = str(self.writer.path_for_session(prompt_envelope.session_id))
        return AgentResponse(
            request_id=response.request_id,
            session_id=response.session_id,
            turn_id=response.turn_id,
            status=response.status,
            message=response.message,
            events_path=events_path,
            checkpoint_path=str(checkpoint_path),
            client=response.client,
            approval=response.approval,
            last_event_id=self.writer.last_event_id,
        )

    def _finalize_turn(
        self, prompt_envelope: PromptEnvelope, response: AgentResponse
    ) -> AgentResponse:
        """Synchronous compatibility boundary used by direct runtime callers."""
        return asyncio.run(self._afinalize_turn(prompt_envelope, response))

    async def submit_prompt_async(self, envelope: PromptEnvelope | dict[str, object]) -> AgentResponse:
        prompt_envelope, error = self._coerce_envelope(envelope)
        if prompt_envelope is None:
            assert error is not None
            return error
        if refusal := await self._model_readiness_refusal(prompt_envelope):
            return refusal
        identity = await self._aprepare_turn(prompt_envelope)
        response: AgentResponse | None = None
        try:
            response = await self.runtime.ahandle(prompt_envelope, identity=identity)
            return await self._afinalize_turn(prompt_envelope, response)
        finally:
            if response is None or response.status != "needs_approval":
                self.machine_identities.finish(identity)

    async def astream_prompt(self, envelope: PromptEnvelope | dict[str, object]):  # type: ignore[no-untyped-def]
        """Yield :class:`StreamEvent`s for one turn (text deltas, lifecycle, final).

        Same authority as :meth:`submit_prompt_async`: the durable event log, checkpoint,
        and turn close are identical; this only surfaces the turn incrementally. Tool
        execution still flows through the broker, policy, and approvals.
        """

        prompt_envelope, error = self._coerce_envelope(envelope)
        if prompt_envelope is None:
            assert error is not None
            yield StreamEvent(kind=FINAL, response=error)
            return
        if refusal := await self._model_readiness_refusal(prompt_envelope):
            yield StreamEvent(
                kind=FINAL,
                event_type="model_not_ready",
                payload={"reason_code": "model_not_ready"},
                response=refusal,
            )
            return
        identity = await self._aprepare_turn(prompt_envelope)
        tasks = TaskManager(self.store, self.writer)
        task = tasks.create_task(
            session_id=prompt_envelope.session_id,
            title="Chat turn",
            objective="Governed chat turn",
            parent_turn_id=prompt_envelope.turn_id,
        )
        final: AgentResponse | None = None
        try:
            async for event in self.runtime.astream_handle(prompt_envelope, identity=identity):
                current = tasks.get_task(task.task_id)
                if current is not None and current.status == "cancelled":
                    final = AgentResponse(
                        request_id=prompt_envelope.request_id,
                        session_id=prompt_envelope.session_id,
                        turn_id=prompt_envelope.turn_id,
                        # B17/C13 — a turn the owner stopped is `stopped`, not
                        # `failed`. The runtime did what it was told; saying it
                        # failed put the blame in the wrong place and made Chat
                        # render the owner's own decision as an error.
                        status="stopped",
                        message="Stopped by user at a safe boundary.",
                        client=prompt_envelope.client,
                    )
                    break
                if event.kind == FINAL and event.response is not None:
                    final = event.response
                    continue
                yield event
            assert final is not None
            enriched = await self._afinalize_turn(prompt_envelope, final)
            yield StreamEvent(kind=FINAL, response=enriched)
        finally:
            if final is None or final.status != "needs_approval":
                self.machine_identities.finish(identity)
            current = tasks.get_task(task.task_id)
            if current is not None and current.status != "cancelled":
                if final is None or final.status == "failed":
                    tasks.fail_task(task.task_id, final.message if final is not None else "stream ended")
                else:
                    tasks.complete_task(task.task_id, final.message)

    # ── B2: resume a turn that was parked for an approval ────────────────────

    def _restore_suspended_turn(
        self, approval_id: str
    ) -> tuple[
        PromptEnvelope, list[ModelMessage], int, list[ToolCallProposal], int, dict[str, str]
    ]:
        """Rebuild the parked turn's envelope, conversation, budget, and queue.

        Raises :class:`TurnSuspensionError` when the row is missing, already
        claimed, unresolved, or unreadable — every one of which must fail closed
        rather than resume a turn from half a state.
        """
        row = self.store.load_suspended_turn(
            approval_id, principal_id=self.tool_broker.principal_id
        )
        if row is None:
            raise TurnSuspensionError("suspended_turn_not_found")
        if str(row.get("status")) != "suspended":
            raise TurnSuspensionError("suspended_turn_already_resumed")
        outcome_raw = row.get("outcome_json")
        if not outcome_raw:
            raise TurnSuspensionError("approval_not_resolved")
        try:
            outcome = json.loads(str(outcome_raw))
            options_raw = json.loads(str(row.get("options_json") or "{}"))
            client_raw = json.loads(str(row.get("client_json") or "{}"))
        except (ValueError, TypeError) as exc:
            raise TurnSuspensionError("suspended_turn_unreadable") from exc

        messages = deserialize_messages(str(row["messages_json"]))
        # The resolved tool result closes the call the model is still waiting on.
        # Approved-and-executed replays the real result; rejected and
        # approved-but-not-executed say so, so the model reacts to what happened.
        messages.append(
            ModelMessage(
                role="tool",
                content=json.dumps(outcome, sort_keys=True),
                tool_call_id=str(row["call_id"]),
                name=str(row["tool_name"]),
            )
        )
        envelope = PromptEnvelope(
            request_id=str(row["request_id"]),
            session_id=str(row["session_id"]),
            # The *same* turn id: this is one turn continuing, not a new one, so
            # the transcript shows a single exchange and `close_turn` updates the
            # row the parked turn already owns.
            turn_id=str(row["turn_id"]),
            client=ClientMetadata(
                type=str(client_raw.get("type", "web_ui")),
                name=str(client_raw.get("name", "raiker-web")),
                version=str(client_raw.get("version", "0.0.0")),
            ),
            user=UserMetadata(id=self.tool_broker.principal_id),
            prompt=PromptPayload(
                text=str(row["prompt_text"]),
                metadata={"resumed_from_approval": approval_id},
            ),
            options=PromptOptions(
                planning_mode=str(options_raw.get("planning_mode", "auto")),
                approval_mode=str(options_raw.get("approval_mode", "interactive")),
                model_profile=str(options_raw.get("model_profile", "")),
                model=str(options_raw.get("model", "")),
                reasoning_effort=(
                    str(options_raw["reasoning_effort"])
                    if isinstance(options_raw.get("reasoning_effort"), str)
                    else None
                ),
                max_tool_calls=int(options_raw.get("max_tool_calls", DEFAULT_MAX_TOOL_CALLS)),
                capability_modes=(
                    dict(options_raw["capability_modes"])
                    if isinstance(options_raw.get("capability_modes"), dict)
                    else {}
                ),
            ),
        )
        # ADD-02 — the rest of the batch this decision unblocked, in the order the
        # model proposed it, plus how many decisions the batch holds so the next
        # park can still say which one it is.
        return (
            envelope,
            messages,
            int(row.get("tool_calls_made", 0)),
            deserialize_pending_calls(row.get("pending_calls_json")),
            int(row.get("queue_total") or 1),
            # BUG-206 — the call this decision closed. Its row said "waiting for
            # your decision" while the turn was parked, and nothing downstream
            # would settle it: the approved call is not re-brokered here, its
            # result was produced when the approval resolved and is replayed as
            # the message above.
            {
                "action_id": str(row["action_id"]),
                "tool_name": str(row["tool_name"]),
                "status": resumed_call_row_status(outcome),
            },
        )

    async def aresume_after_approval(self, approval_id: str) -> AgentResponse:
        (
            envelope, messages, tool_calls_made, pending_calls, queue_total, resolved_call
        ) = self._restore_suspended_turn(approval_id)
        if not self.store.claim_suspended_turn(approval_id):
            raise TurnSuspensionError("suspended_turn_already_resumed")
        identity = self._rotate_identity_for_resume(envelope)
        final: AgentResponse | None = None
        try:
            async for event in self.runtime.aresume_events(
                envelope,
                messages,
                stream=False,
                tool_calls_made=tool_calls_made,
                approval_id=approval_id,
                pending_calls=pending_calls,
                queue_total=queue_total,
                identity=identity,
                resolved_call=resolved_call,
            ):
                if event.kind == FINAL and event.response is not None:
                    final = event.response
            assert final is not None
            finalized = await self._afinalize_turn(envelope, final)
            return finalized
        finally:
            if final is None or final.status != "needs_approval":
                self.machine_identities.finish(identity)
            self.store.finalize_suspended_turn(
                approval_id, status="resumed" if final is not None else "resume_failed"
            )

    async def astream_resume_after_approval(self, approval_id: str):  # type: ignore[no-untyped-def]
        """Stream the continuation of a parked turn.

        Same authority and the same finalisation as an ordinary turn — this only
        surfaces it incrementally, so the continuation lands in the transcript
        the way the interrupted turn would have.
        """
        (
            envelope, messages, tool_calls_made, pending_calls, queue_total, resolved_call
        ) = self._restore_suspended_turn(approval_id)
        if not self.store.claim_suspended_turn(approval_id):
            raise TurnSuspensionError("suspended_turn_already_resumed")
        identity = self._rotate_identity_for_resume(envelope)
        final: AgentResponse | None = None
        try:
            async for event in self.runtime.aresume_events(
                envelope,
                messages,
                stream=True,
                tool_calls_made=tool_calls_made,
                approval_id=approval_id,
                pending_calls=pending_calls,
                queue_total=queue_total,
                identity=identity,
                resolved_call=resolved_call,
            ):
                if event.kind == FINAL and event.response is not None:
                    final = event.response
                    continue
                yield event
            assert final is not None
            finalized = await self._afinalize_turn(envelope, final)
            yield StreamEvent(kind=FINAL, response=finalized)
        finally:
            if final is None or final.status != "needs_approval":
                self.machine_identities.finish(identity)
            self.store.finalize_suspended_turn(
                approval_id, status="resumed" if final is not None else "resume_failed"
            )

    def submit_prompt(self, envelope: PromptEnvelope | dict[str, object]) -> AgentResponse:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.submit_prompt_async(envelope))
        raise RuntimeError("submit_prompt cannot be called from a running event loop; use submit_prompt_async")
