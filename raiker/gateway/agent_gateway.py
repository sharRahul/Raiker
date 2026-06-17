from __future__ import annotations

from pathlib import Path

from raiker.channels.registry import ConnectorRegistry
from raiker.checkpoints.service import CheckpointService
from raiker.contracts.models import AgentResponse, ContractValidationError, PromptEnvelope
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.models.registry import ModelProfileRegistry
from raiker.models.router import ModelRouter
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.sessions.manager import SessionManager
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


class AgentGateway:
    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.store = SQLiteStore(self.workspace_root)
        self.writer = EventLogWriter(self.store)
        self.sessions = SessionManager(self.store, self.workspace_root)
        self.checkpoints = CheckpointService(self.store)
        policy_engine = PolicyEngine(StaticPolicyConfig(self.workspace_root))
        self.tool_broker = ToolBroker(
            workspace_root=self.workspace_root,
            policy_engine=policy_engine,
            store=self.store,
            writer=self.writer,
        )
        self.model_registry = ModelProfileRegistry.load()
        self.connector_registry = ConnectorRegistry.load()
        self.store.upsert_model_profiles(self.model_registry.list_profiles())
        self.store.upsert_connector_profiles(self.connector_registry.list_profiles())
        self.model_router = ModelRouter(self.model_registry, self.writer)
        self.runtime = RuntimeOrchestrator(
            workspace_root=self.workspace_root,
            writer=self.writer,
            tool_broker=self.tool_broker,
            model_router=self.model_router,
        )

    def submit_prompt(self, envelope: PromptEnvelope | dict[str, object]) -> AgentResponse:
        try:
            prompt_envelope = (
                envelope if isinstance(envelope, PromptEnvelope) else PromptEnvelope.from_dict(envelope)  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, ContractValidationError, ValueError) as exc:
            return AgentResponse(
                request_id="req_invalid",
                session_id="sess_invalid",
                turn_id="turn_invalid",
                status="failed",
                message=f"Invalid prompt envelope: {exc}",
            )
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
                payload={"client_type": prompt_envelope.client.type, "prompt_length": len(prompt_envelope.prompt.text)},
                client=prompt_envelope.client,
            )
        )
        response = self.runtime.handle(prompt_envelope)
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
