from __future__ import annotations

from pathlib import Path

from raiker.channels.registry import ConnectorRegistry
from raiker.checkpoints.service import CheckpointService
from raiker.contracts.models import AgentResponse, ContractValidationError, PromptEnvelope
from raiker.contracts.streaming import FINAL, StreamEvent
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.hooks.contracts import HookInput
from raiker.hooks.dispatcher import HookDispatcher
from raiker.hooks.registry import HooksRegistry
from raiker.models.policy_state import provider_runtime_policy_from_gates
from raiker.models.registry import ModelProfileRegistry, RegistryError, profile_with_model
from raiker.models.router import ModelRouter
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.sessions.manager import SessionManager
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


class AgentGateway:
    def __init__(self, workspace_root: str | Path, principal_id: str = "local_user") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.store = SQLiteStore(self.workspace_root)
        self.writer = EventLogWriter(self.store)
        self.sessions = SessionManager(self.store, self.workspace_root)
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
            runtime_policy=provider_runtime_policy_from_gates(self.store),
        )
        # Native default backend: configured llama.cpp profile only; production never falls back to deterministic test providers.
        # Honor the operator's selected model profile (e.g. via `/model use`); fall back to the native default.
        self.default_provider = self._resolve_default_provider()
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
        unresolved placeholder model) it falls back to the native llama.cpp default. This is the
        only place selection is bound to a turn, so the CLI and any future client share it.
        """
        native_default = self.model_router.default_provider()
        state = self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
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
        state = self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        if state is not None and state.profile_id == profile.profile_id and state.model:
            effective_model = state.model
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
        for profile_id in self.store.load_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID):
            resolved = self._resolve_profile_for_turn(profile_id)
            if resolved is not None and resolved not in chain:
                chain.append(resolved)
        return chain

    def _dispatch_lifecycle_hook(self, event_name: str, envelope: PromptEnvelope) -> None:
        self.hook_dispatcher.dispatch(
            HookInput(
                event_name=event_name,
                tool_name=None,
                tool_input={},
                context={"prompt_length": len(envelope.prompt.text)},
                session_id=envelope.session_id,
                turn_id=envelope.turn_id,
                cwd=str(self.workspace_root),
            ),
            session_id=envelope.session_id,
            turn_id=envelope.turn_id,
            client=envelope.client,
        )

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

    def _prepare_turn(self, prompt_envelope: PromptEnvelope) -> None:
        existing_session = self.sessions.load_session(prompt_envelope.session_id)
        self.sessions.get_or_create(prompt_envelope.session_id)
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
                },
                client=prompt_envelope.client,
            )
        )
        if self.hook_dispatcher.is_active():
            if existing_session is None:
                self._dispatch_lifecycle_hook("SessionStart", prompt_envelope)
            self._dispatch_lifecycle_hook("UserPromptSubmit", prompt_envelope)

    def _finalize_turn(
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
        self.sessions.close_turn(prompt_envelope.turn_id, response.status, response.message[:500])
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

    async def submit_prompt_async(self, envelope: PromptEnvelope | dict[str, object]) -> AgentResponse:
        prompt_envelope, error = self._coerce_envelope(envelope)
        if prompt_envelope is None:
            assert error is not None
            return error
        self._prepare_turn(prompt_envelope)
        response = await self.runtime.ahandle(prompt_envelope)
        return self._finalize_turn(prompt_envelope, response)

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
        self._prepare_turn(prompt_envelope)
        final: AgentResponse | None = None
        async for event in self.runtime.astream_handle(prompt_envelope):
            if event.kind == FINAL and event.response is not None:
                final = event.response
                continue
            yield event
        assert final is not None
        enriched = self._finalize_turn(prompt_envelope, final)
        yield StreamEvent(kind=FINAL, response=enriched)

    def submit_prompt(self, envelope: PromptEnvelope | dict[str, object]) -> AgentResponse:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.submit_prompt_async(envelope))
        raise RuntimeError("submit_prompt cannot be called from a running event loop; use submit_prompt_async")
