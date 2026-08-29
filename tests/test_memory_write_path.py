"""BUG-71 — durable memory has to be reachable from Chat and Build.

Permissions listed **Memory store** with all four decision modes and the
description "Persist durable memories through the governed broker." The broker
really did route ``memory_write`` / ``memory_forget`` to fully governed
executors — but neither tool was in the model's catalogue and
``governed_memory_status`` returned ``read_only_review`` as a literal, so a turn
could not propose a write however the owner set the row, and the agent told the
owner memory was read-only.

This suite pins what closes that, in the order an owner meets it:

- both tools are advertised to the model, validate their arguments, and take the
  high-risk approval path rather than being answered ``unknown_or_denied_tool``;
- the proposal shows the *text*, because that is what the decision is about, and
  credential-like text is refused before anyone is asked to approve it;
- approving really writes (and really forgets) rather than recording a decision;
- ``governed_memory_status`` reports the gate and decision mode the next write
  would actually meet, in every combination of the two.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.approvals.execution import EXECUTABLE_ON_APPROVAL, executable_capability
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.memory.candidates import governed_memory_status
from raiker.memory.store import MemoryGovernance, get_memory, write_memory
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import (
    ToolCallRejected,
    default_tool_specs,
    validate_tool_call,
)
from raiker.phase_gates import default_capability_gates
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.authority.activation import get_activation_requirement
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    build_default_executor_registry,
)
from raiker.storage.sqlite import SQLiteStore
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker

_WRITE_CAP = "memory_write_execution"
_FORGET_CAP = "memory_forget_execution"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


class TestToolSurface:
    def test_both_tools_are_advertised_to_the_model(self) -> None:
        names = {spec.name for spec in default_tool_specs()}
        assert {"memory_write", "memory_forget"} <= names

    def test_the_write_advertises_its_optional_scope(self) -> None:
        # Without it a model has no way to learn a memory can be global rather
        # than project-scoped, and would never offer the distinction.
        spec = next(s for s in default_tool_specs() if s.name == "memory_write")
        assert "scope" in spec.parameters["properties"]
        assert spec.parameters["required"] == ["text"]

    def test_validation_requires_the_arguments_the_tool_needs(self) -> None:
        empty: dict[str, object] = {}
        for tool, args in (("memory_write", empty), ("memory_forget", empty)):
            with pytest.raises(ToolCallRejected):
                validate_tool_call(
                    ToolCallProposal(call_id="call_1", tool_name=tool, arguments=args)
                )

    def test_a_valid_call_is_medium_risk_and_still_approval_bound(self) -> None:
        """Medium, and approval-bound anyway.

        A stored memory is the owner's own record on this machine, nobody else
        can see it, and `memory_forget` reverses it — `medium` by the definitions
        in `raiker.policy.risk`. It parks for the owner all the same, because
        parking is `approval_required_actions` and not the band. The sibling
        `memory_forget` is the one that is not covered by a checkpoint.
        """
        action = validate_tool_call(
            ToolCallProposal(
                call_id="call_1",
                tool_name="memory_write",
                arguments={"text": "The owner prefers metric units."},
            )
        )
        assert action.risk_level == "medium"
        assert action.requires_approval is True


class TestPolicy:
    def test_the_memory_tools_take_the_approval_path(self, tmp_path: Path) -> None:
        engine = PolicyEngine(StaticPolicyConfig(tmp_path))
        for tool in ("memory_write", "memory_forget"):
            decision = engine.review(ToolAction(new_id("act_"), tool, {}, "high", True))
            assert decision.decision == "needs_approval", tool
            assert "unknown_or_denied_tool" not in decision.reasons, tool


class TestGovernanceWiring:
    def test_both_capabilities_are_real_registered_and_enableable(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        registry = build_default_executor_registry(tmp_path, store)
        for cap in (_WRITE_CAP, _FORGET_CAP):
            assert cap in REAL_EXECUTOR_CAPABILITIES, cap
            assert registry.has(cap), cap
            assert get_activation_requirement(cap) is not None, cap
            assert cap in default_capability_gates(), cap

    def test_each_tool_answers_to_its_own_owner_switch(self) -> None:
        assert CAPABILITY_GATE_MAP["memory_write"] == _WRITE_CAP
        assert CAPABILITY_GATE_MAP["memory_forget"] == _FORGET_CAP

    def test_approving_executes_rather_than_records(self) -> None:
        assert _WRITE_CAP in EXECUTABLE_ON_APPROVAL
        assert _FORGET_CAP in EXECUTABLE_ON_APPROVAL
        assert executable_capability("memory_write") == _WRITE_CAP
        assert executable_capability("memory_forget") == _FORGET_CAP


class TestProposalPreview:
    """The decision is about text, so the owner has to be shown the text."""

    def _broker(self, workspace: Path) -> ToolBroker:
        store = SQLiteStore(workspace)
        return ToolBroker(
            workspace_root=workspace,
            policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
            store=store,
            principal_id="principal_owner",
        )

    def test_a_write_proposal_shows_the_exact_text(self, workspace: Path) -> None:
        broker = self._broker(workspace)
        preview = broker._approval_preview(
            ToolAction(
                new_id("act_"),
                "memory_write",
                {"text": "The owner prefers metric units.", "scope": "global"},
                "high",
                True,
            )
        )
        assert preview is not None
        assert preview["status"] == "success"
        assert preview["text"] == "The owner prefers metric units."
        assert preview["scope"] == "global"

    def test_credential_like_text_is_refused_before_anyone_is_asked(
        self, workspace: Path
    ) -> None:
        preview = self._broker(workspace)._approval_preview(
            ToolAction(
                new_id("act_"),
                "memory_write",
                {"text": "api key sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHH"},
                "high",
                True,
            )
        )
        assert preview is not None
        assert preview["status"] == "failed"
        assert preview["error"]["type"] == "secret_or_credential_like_memory_blocked"

    def test_forgetting_a_record_that_does_not_exist_is_not_a_decision(
        self, workspace: Path
    ) -> None:
        preview = self._broker(workspace)._approval_preview(
            ToolAction(new_id("act_"), "memory_forget", {"memory_id": "mem_nope"}, "high", True)
        )
        assert preview is not None
        assert preview["error"]["type"] == "memory_not_found"

    def test_a_forget_proposal_shows_the_record_it_would_remove(
        self, workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        entry = write_memory(
            "The owner prefers metric units.",
            workspace_root=workspace,
            scope="project",
            source_event_id="evt_seed",
            store=store,
            governance=MemoryGovernance(
                source_event_id="evt_seed",
                source_session_id="sess_seed",
                source_turn_id=None,
                source_type="test",
                confidence=0.75,
                trust_score=0.75,
                retention="until_forget",
                approval_state="policy_allowed",
                created_by="principal_owner",
            ),
            owner_principal_id=store.account_scope("principal_owner"),
        )
        preview = self._broker(workspace)._approval_preview(
            ToolAction(
                new_id("act_"), "memory_forget", {"memory_id": entry.memory_id}, "high", True
            )
        )
        assert preview is not None
        assert preview["status"] == "success"
        assert preview["text"] == "The owner prefers metric units."

    def test_the_sentence_shown_before_the_decision_says_it_executes(
        self, workspace: Path
    ) -> None:
        broker = self._broker(workspace)
        sentence = broker._expected_effect(
            ToolAction(new_id("act_"), "memory_write", {"text": "x", "scope": "global"}, "high", True),
            False,
        )
        assert "stores this exact text as a durable global memory, once" in sentence
        assert "does not execute" not in sentence


class TestGovernedMemoryStatus:
    """What the model is told about memory must be a reading, not a literal."""

    @staticmethod
    def _set(store: SQLiteStore, capability: str, *, state: str, mode: str) -> None:
        store.upsert_capability_gate_state(
            {
                "capability": capability,
                "state": state,
                "reason": "test",
                "created_at": "2026-08-10T00:00:00Z",
                "updated_at": "2026-08-10T00:00:00Z",
            }
        )
        store.upsert_capability_decision_mode(
            {
                "capability": capability,
                "decision_mode": mode,
                "set_by": "principal_owner",
                "set_at": "2026-08-10T00:00:00Z",
                "reason": "test",
                "event_id": "",
                "created_at": "2026-08-10T00:00:00Z",
                "updated_at": "2026-08-10T00:00:00Z",
            }
        )

    def test_no_store_still_answers_conservatively(self) -> None:
        status = governed_memory_status([])
        assert status["durable_writes_enabled"] is False
        assert status["mode"] == "read_only_review"

    def test_a_disabled_gate_reports_read_only(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        self._set(store, _WRITE_CAP, state="disabled", mode="ask")
        status = governed_memory_status([], store=store)
        assert status["durable_writes_enabled"] is False
        assert status["mode"] == "read_only_review"

    def test_an_enabled_gate_at_ask_reports_a_governed_write(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        self._set(store, _WRITE_CAP, state="enabled_runtime", mode="ask")
        status = governed_memory_status([], store=store)
        # This is the exact combination BUG-71 was reported against: the owner
        # turned the capability on and the agent still said "read_only".
        assert status["durable_writes_enabled"] is True
        assert status["mode"] == "governed_write_review"
        assert status["write_decision_mode"] == "ask"

    def test_an_enabled_gate_at_allow_reports_a_standing_write(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        self._set(store, _WRITE_CAP, state="enabled_runtime", mode="always_allow")
        status = governed_memory_status([], store=store)
        assert status["durable_writes_enabled"] is True
        assert status["mode"] == "governed_write"

    def test_deny_is_reported_as_denied_not_as_read_only(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        self._set(store, _WRITE_CAP, state="enabled_runtime", mode="deny")
        status = governed_memory_status([], store=store)
        assert status["durable_writes_enabled"] is False
        # "read_only_review" would tell the owner the capability does not exist;
        # it exists, and they denied it.
        assert status["mode"] == "denied_by_decision_mode"


class TestApprovedWriteReallyHappens:
    def test_the_executor_writes_and_the_record_is_readable(self, workspace: Path) -> None:
        from raiker.runtime.authority.models import Principal, PrincipalType
        from raiker.runtime.authority.router import GovernedAction

        store = SQLiteStore(workspace)
        registry = build_default_executor_registry(workspace, store)
        executor = registry.get(_WRITE_CAP)
        assert executor is not None
        result = executor.execute(
            GovernedAction(
                action_id=new_id("act_"),
                principal_id="principal_owner",
                action_type="memory_write",
                tool_or_service_name="memory_write",
                arguments={"text": "The owner prefers metric units.", "scope": "global"},
                risk_level="high",
            ),
            Principal(
                principal_id="principal_owner",
                principal_type=PrincipalType.HUMAN,
                display_name="Owner",
            ),
        )
        assert result.ok is True
        memory_id = str(result.artifacts["memory_id"])
        entry = get_memory(
            memory_id,
            workspace_root=workspace,
            owner_principal_id=store.account_scope("principal_owner"),
        )
        assert entry is not None
        assert entry.text == "The owner prefers metric units."
