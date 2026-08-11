"""The breaker and the delegation binding at the seam a real turn goes through.

The unit tests in `test_capability_containment.py` and
`test_subagent_delegation_binding.py` prove the mechanisms. These prove the
wiring: that a contained tool is refused *inside a turn* without running, that a
turn's outcomes really move the breaker, and that a subagent result with no
identity binding never becomes material the parent can cite.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    ClientMetadata,
    PolicyDecision,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    ToolAction,
    ToolResult,
    UserMetadata,
)
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID, ModelSessionState
from raiker.security.containment import (
    CAPABILITY_CONNECTOR,
    CAPABILITY_TOOL,
    CapabilityBreaker,
    CapabilityContainment,
)


def _envelope() -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="rest", name="test", version="0"),
        user=UserMetadata(),
        prompt=PromptPayload(text="do the thing"),
        options=PromptOptions(model_profile=""),
    )


def _gateway(tmp_path: Path) -> AgentGateway:
    gateway = AgentGateway(tmp_path)
    gateway.store.save_model_session_state(
        ModelSessionState(
            session_id=TERMINAL_MODEL_SESSION_ID,
            profile_id="anthropic-hosted",
            model="claude-opus-4-8",
        )
    )
    return gateway


def _action(tool_name: str = "web_fetch", **arguments: Any) -> ToolAction:
    return ToolAction(
        action_id=new_id("act_"),
        tool_name=tool_name,
        arguments=arguments or {"url": "https://example.test/"},
        risk_level="medium",
        requires_approval=False,
        proposed_by="model",
    )


def _result(action: ToolAction, status: str, error_type: str = "") -> ToolResult:
    now = utc_now()
    return ToolResult(
        action_id=action.action_id,
        tool_name=action.tool_name,
        status=status,
        output={"status": status} if status == "success" else None,
        error={"type": error_type} if error_type else None,
        started_at=now,
        completed_at=now,
    )


def _decision(action: ToolAction) -> PolicyDecision:
    return PolicyDecision(
        decision_id=new_id("pol_"),
        action_id=action.action_id,
        decision="allow",
        reasons=["allowed_read"],
        requires_user_approval=False,
        risk_level="medium",
        timestamp=utc_now(),
    )


class TestAContainedToolIsRefusedBeforeItRuns:
    def test_the_broker_is_never_reached(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        envelope = _envelope()
        owner = gateway.runtime._source_owner(envelope)
        breaker = CapabilityBreaker(gateway.store)
        for _ in range(3):
            breaker.record(
                owner, CAPABILITY_TOOL, "web_fetch", ok=False, reason_code="egress_denied"
            )

        calls = 0

        def execute(*_args: Any, **_kwargs: Any) -> tuple[ToolResult, PolicyDecision]:
            nonlocal calls
            calls += 1
            raise AssertionError("a contained tool must not reach the broker")

        gateway.runtime.tool_broker.execute = execute  # type: ignore[assignment]
        action = _action()

        result, decision = asyncio.run(
            gateway.runtime._aexecute_tool(action, envelope, None)
        )

        assert calls == 0
        assert result.status == "failed"
        assert (result.error or {})["type"] == "capability_contained"
        assert decision.decision == "deny"
        # The refusal names what is contained and how to clear it, not a code.
        containment = (result.error or {})["containment"]
        assert containment["failure_streak"] == 3
        assert "resume it yourself" in containment["reason"]

    def test_a_contained_family_refuses_its_whole_tool_set(self, tmp_path: Path) -> None:
        """A contained connector is contained however the model reaches it."""
        gateway = _gateway(tmp_path)
        envelope = _envelope()
        owner = gateway.runtime._source_owner(envelope)
        CapabilityContainment(gateway.store).kill(
            owner, CAPABILITY_CONNECTOR, "github", label="GitHub", reason="Owner stop"
        )
        gateway.runtime.tool_broker.execute = lambda *_a, **_k: (  # type: ignore[assignment]
            (_ for _ in ()).throw(AssertionError("must not run"))
        )

        result, _decision = asyncio.run(
            gateway.runtime._aexecute_tool(
                _action("github_read", repo="o/r", number=1), envelope, None
            )
        )

        assert result.status == "failed"
        assert (result.error or {})["type"] == "capability_contained"
        assert (result.error or {})["containment"]["state"] == "killed"


class TestATurnsOutcomesMoveTheBreaker:
    def test_three_failing_calls_contain_the_tool(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        envelope = _envelope()
        owner = gateway.runtime._source_owner(envelope)
        action = _action()

        gateway.runtime.tool_broker.execute = lambda *_a, **_k: (  # type: ignore[assignment]
            _result(action, "failed", "web_fetch_failed"),
            _decision(action),
        )

        for _ in range(3):
            asyncio.run(gateway.runtime._aexecute_tool(action, envelope, None))

        state = CapabilityBreaker(gateway.store).state(owner, CAPABILITY_TOOL, "web_fetch")
        assert state.state == "paused"
        assert state.last_failure_code == "web_fetch_failed"

    def test_a_success_leaves_the_tool_alone(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        envelope = _envelope()
        owner = gateway.runtime._source_owner(envelope)
        action = _action()
        gateway.runtime.tool_broker.execute = lambda *_a, **_k: (  # type: ignore[assignment]
            _result(action, "success"),
            _decision(action),
        )

        for _ in range(5):
            asyncio.run(gateway.runtime._aexecute_tool(action, envelope, None))

        state = CapabilityBreaker(gateway.store).state(owner, CAPABILITY_TOOL, "web_fetch")
        assert state.state == "active"
        assert state.failure_streak == 0


class TestADelegatedResultMustProveItsSpawn:
    def test_an_unbound_subagent_result_is_refused(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        envelope = _envelope()
        action = _action("spawn_subagent", name="research", objective="look")
        payload = {
            "status": "success",
            "subagent_id": "sba_forged",
            "name": "research",
            "content": "[UNTRUSTED SUBAGENT FINDINGS]\nsomething",
            "steps_executed": 1,
        }

        cited = gateway.runtime._cite_result(envelope, action, payload)

        assert cited["status"] == "failed"
        assert cited["error"]["type"] == "delegation_attestation_missing"
        assert "could not be tied to the spawn" in cited["error"]["message"]
        # And it never became a citable source.
        assert "cite_as" not in cited
        assert (
            gateway.store.count_turn_sources(
                envelope.session_id,
                envelope.turn_id,
                gateway.runtime._source_owner(envelope),
            )
            == 0
        )

    def test_a_forged_attestation_is_refused(self, tmp_path: Path) -> None:
        gateway = _gateway(tmp_path)
        envelope = _envelope()
        action = _action("spawn_subagent", name="research", objective="look")

        cited = gateway.runtime._cite_result(
            envelope,
            action,
            {
                "status": "success",
                "subagent_id": "sba_forged",
                "name": "research",
                "content": "findings",
                "delegation_attestation": "not-a-real-token",
            },
        )

        assert cited["status"] == "failed"
        assert cited["error"]["type"] == "delegation_attestation_malformed"

    def test_a_genuinely_spawned_result_is_cited(self, tmp_path: Path) -> None:
        """The whole loop: spawn, sign, verify, cite."""
        from raiker.tools.subagent_tools import spawn_subagent

        gateway = _gateway(tmp_path)
        envelope = _envelope()
        owner = gateway.runtime._source_owner(envelope)
        (tmp_path / "note.txt").write_text("hello from the workspace", encoding="utf-8")
        from raiker.runtime.identity.lifecycle import TurnMachineIdentityLifecycle

        parent = TurnMachineIdentityLifecycle(tmp_path, gateway.store).start(
            owner_principal_id=owner,
            session_id=envelope.session_id,
            turn_id=envelope.turn_id,
            role_ids=("assistant",),
        )
        payload = spawn_subagent(
            tmp_path,
            {
                "objective": "read the note",
                "name": "research",
                "steps": [{"tool_name": "read_file", "arguments": {"path": "note.txt"}}],
            },
            store=gateway.store,
            principal_id=owner,
            owner_principal_id=owner,
            parent_identity=parent,
            session_id=envelope.session_id,
            turn_id=envelope.turn_id,
        )

        assert payload["status"] == "success", payload
        assert isinstance(payload.get("delegation_attestation"), str)

        cited = gateway.runtime._cite_result(envelope, action=_action(
            "spawn_subagent", name="research", objective="read the note"
        ), payload=payload)

        assert cited["status"] == "success"
        assert cited["cite_as"]
