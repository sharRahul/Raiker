from __future__ import annotations

from pathlib import Path

from raiker.contracts.ids import new_id
from raiker.contracts.models import AgentResponse, PromptEnvelope, ToolAction, ToolResult
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.models.router import ModelRouter
from raiker.runtime.classifier import Classification, SimpleClassifier
from raiker.runtime.planner import SimplePlanner
from raiker.runtime.state_machine import RuntimeStateMachine
from raiker.runtime.verifier import VerificationStub
from raiker.tools.broker import ToolBroker


class RuntimeOrchestrator:
    def __init__(
        self,
        *,
        workspace_root: str | Path,
        writer: EventLogWriter,
        tool_broker: ToolBroker,
        model_router: ModelRouter,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.writer = writer
        self.tool_broker = tool_broker
        self.model_router = model_router
        self.classifier = SimpleClassifier()
        self.planner = SimplePlanner()
        self.verifier = VerificationStub()

    def _state(self, machine: RuntimeStateMachine, envelope: PromptEnvelope, new_state: str) -> None:
        old_state = machine.state
        machine.transition(new_state)
        self.writer.append(
            make_event(
                session_id=envelope.session_id,
                turn_id=envelope.turn_id,
                event_type="turn_state_changed",
                actor="runtime",
                payload={"from": old_state, "to": new_state},
                client=envelope.client,
            )
        )

    def _event(self, envelope: PromptEnvelope, event_type: str, payload: dict[str, object]) -> None:
        self.writer.append(
            make_event(
                session_id=envelope.session_id,
                turn_id=envelope.turn_id,
                event_type=event_type,
                actor="runtime",
                payload=payload,
                client=envelope.client,
            )
        )

    def _action_from_prompt(self, prompt: str, classification: Classification) -> ToolAction | None:
        text = prompt.strip()
        lower = text.lower()
        if classification.intent == "local_action_request":
            command = text[1:].strip() if text.startswith("!") else text
            return ToolAction(
                action_id=new_id("act_"),
                tool_name="shell",
                arguments={"command": command},
                risk_level="high",
                requires_approval=True,
            )
        if classification.intent != "filesystem_query":
            return None
        if lower.startswith("read file"):
            path = text[len("read file") :].strip() or "."
            return ToolAction(
                action_id=new_id("act_"),
                tool_name="read_file",
                arguments={"path": path},
                risk_level="medium",
                requires_approval=False,
            )
        if lower.startswith("read "):
            path = text[len("read") :].strip() or "."
            return ToolAction(
                action_id=new_id("act_"),
                tool_name="read_file",
                arguments={"path": path},
                risk_level="medium",
                requires_approval=False,
            )
        if "grep" in lower or "search" in lower:
            query = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""
            return ToolAction(
                action_id=new_id("act_"),
                tool_name="grep",
                arguments={"query": query, "path": ".", "max_results": 50},
                risk_level="medium",
                requires_approval=False,
            )
        return ToolAction(
            action_id=new_id("act_"),
            tool_name="list_directory",
            arguments={"path": "."},
            risk_level="medium",
            requires_approval=False,
        )

    def handle(self, envelope: PromptEnvelope) -> AgentResponse:
        machine = RuntimeStateMachine()
        self._state(machine, envelope, "NORMALISED")
        self._event(envelope, "prompt_normalised", {"text_length": len(envelope.prompt.text)})
        self._state(machine, envelope, "CLASSIFIED")
        classification = self.classifier.classify(envelope.prompt.text)
        self._event(
            envelope,
            "intent_classified",
            {
                "intent": classification.intent,
                "confidence": classification.confidence,
                "requires_tools": classification.requires_tools,
                "requires_plan": classification.requires_plan,
                "notes": classification.notes,
            },
        )
        self._event(
            envelope,
            "risk_classified",
            {
                "risk_level": classification.risk_level,
                "requires_approval": classification.risk_level == "high",
                "reasons": [classification.intent],
            },
        )
        self._state(machine, envelope, "CONTEXT_READY")
        self._event(envelope, "context_gathered", {"sources": ["current_prompt"], "context_items": 1})
        plan_result = self.planner.create_or_skip(classification)
        self._state(machine, envelope, "PLAN_READY" if plan_result.required else "PLAN_SKIPPED")
        self._event(envelope, plan_result.event_type, plan_result.payload)

        action = self._action_from_prompt(envelope.prompt.text, classification)
        tool_result: ToolResult | None = None
        if action is None:
            self._state(machine, envelope, "RESPONDING")
            message = self.model_router.generate("mock", "mock-deterministic", envelope.prompt.text, {"intent": classification.intent})
            status = "completed"
            approval = None
        else:
            self._state(machine, envelope, "POLICY_REVIEWED")
            tool_result, decision = self.tool_broker.execute(
                action,
                session_id=envelope.session_id,
                turn_id=envelope.turn_id,
                client=envelope.client,
            )
            if decision.decision == "needs_approval":
                self._state(machine, envelope, "WAITING_FOR_APPROVAL")
                self._state(machine, envelope, "RESPONDING")
                status = "needs_approval"
                approval = {
                    "action_id": action.action_id,
                    "tool_name": action.tool_name,
                    "arguments": action.arguments,
                    "risk_level": "high",
                    "reasons": decision.reasons,
                    "message": "Approval required. Phase 1 did not execute this action.",
                }
                message = "Approval required for local action. No command was executed."
            elif decision.decision == "deny":
                self._state(machine, envelope, "DENIED")
                self._state(machine, envelope, "RESPONDING")
                status = "denied"
                approval = None
                message = f"Action denied by policy: {', '.join(decision.reasons)}"
            else:
                self._state(machine, envelope, "EXECUTING")
                self._state(machine, envelope, "OBSERVING")
                self._state(machine, envelope, "VERIFYING")
                verification = self.verifier.verify_tool_result(tool_result)
                self._event(envelope, "verification_completed", verification.to_dict())
                self._state(machine, envelope, "RESPONDING")
                status = "completed" if tool_result.status == "success" else "failed"
                approval = None
                if tool_result.status == "success" and tool_result.output is not None:
                    if action.tool_name == "list_directory":
                        entries = tool_result.output.get("entries", [])
                        message = "Project entries: " + ", ".join(str(item) for item in entries)
                    elif action.tool_name == "read_file":
                        text = str(tool_result.output.get("text", ""))
                        message = text[:1000] if text else "File was read but empty."
                    elif action.tool_name in {"glob", "grep"}:
                        message = str(tool_result.output)
                    else:
                        message = "Tool completed."
                else:
                    message = f"Tool failed safely: {tool_result.error}"
        self._event(
            envelope,
            "response_created",
            {"status": status, "summary": message[:200], "runtime_state": machine.state},
        )
        return AgentResponse(
            request_id=envelope.request_id,
            session_id=envelope.session_id,
            turn_id=envelope.turn_id,
            status=status,
            message=message,
            client=envelope.client,
            approval=approval,
            last_event_id=self.writer.last_event_id,
        )
