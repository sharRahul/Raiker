"""BUG-70 — a composer mode is the turn's posture, not an edit to standing rights.

Build's **Plan / Edit / Auto** chips used to issue four
``POST /api/capability-modes/<cap>/<mode>`` calls. That change was global,
permanent, and skipped the step-up — a recorded reason, and a threat-model
acknowledgement where the capability demands one — that the Permissions page
requires for the *identical* transition. An owner pressing **Auto** in a
composer was silently rewriting four high-risk permissions for every later Chat,
Task and Build session.

The posture is now carried by the turn. This suite pins the two properties that
make that safe:

- it can only ever **tighten** — ``ask`` and ``deny`` are the only values the
  envelope accepts, so a turn can never grant itself authority; and
- it really is enforced — a ``deny`` posture refuses the call at the broker with
  its own reason code, and an ``ask`` posture cannot be swallowed by the
  unattended approval modes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    ContractValidationError,
    PromptOptions,
    ToolAction,
    validated_turn_capability_modes,
)
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker

_WRITE = "file_write_execution"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


def _broker(workspace: Path) -> ToolBroker:
    return ToolBroker(
        workspace_root=workspace,
        policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
        store=SQLiteStore(workspace),
        principal_id="principal_owner",
    )


def _write_action(workspace: Path) -> ToolAction:
    return ToolAction(
        new_id("act_"),
        "write_file",
        {"path": "notes.md", "text": "hello\n"},
        "high",
        True,
    )


class TestTheEnvelopeOnlyAcceptsTightening:
    def test_ask_and_deny_are_accepted(self) -> None:
        assert validated_turn_capability_modes({_WRITE: "ask"}) == {_WRITE: "ask"}
        assert validated_turn_capability_modes({_WRITE: "deny"}) == {_WRITE: "deny"}

    @pytest.mark.parametrize("mode", ["allow", "auto", "always_allow", "", "ASK"])
    def test_a_loosening_or_unknown_mode_fails_the_envelope(self, mode: str) -> None:
        # Failing here rather than being dropped downstream is deliberate: a
        # caller that tries to widen a turn has to be told, not quietly ignored.
        with pytest.raises(ContractValidationError):
            PromptOptions(capability_modes={_WRITE: mode})

    def test_an_unknown_capability_fails_the_envelope(self) -> None:
        with pytest.raises(ContractValidationError):
            PromptOptions(capability_modes={"not_a_capability": "deny"})

    def test_the_default_turn_names_no_posture(self) -> None:
        # Every existing caller — Chat, the CLI, a REST client — keeps running
        # under the owner's standing modes exactly as before.
        assert PromptOptions().capability_modes == {}


class TestTheBrokerEnforcesIt:
    def test_a_deny_posture_refuses_the_call_with_its_own_reason(
        self, workspace: Path
    ) -> None:
        result, decision = _broker(workspace).execute(
            _write_action(workspace),
            session_id="sess_1",
            turn_id="turn_1",
            turn_capability_modes={_WRITE: "deny"},
        )
        assert decision.decision == "deny"
        # Named apart from `denied_by_decision_mode` so an audit reader can tell
        # "the owner denied this capability" from "this turn writes nothing".
        assert "denied_by_turn_posture" in decision.reasons
        assert result.status == "denied"
        assert not (workspace / "notes.md").exists()

    def test_a_deny_posture_leaves_other_capabilities_alone(self, workspace: Path) -> None:
        # Plan mode denies the write capabilities and nothing else, so research
        # still works — that is what keeps the mode usable.
        result, decision = _broker(workspace).execute(
            ToolAction(new_id("act_"), "list_directory", {"path": "."}, "low", False),
            session_id="sess_1",
            turn_id="turn_1",
            turn_capability_modes={_WRITE: "deny"},
        )
        assert decision.decision != "deny"
        assert result.status == "success"

    def test_an_ask_posture_survives_the_unattended_approval_modes(
        self, workspace: Path
    ) -> None:
        # `approval_mode="auto"` pre-authorises ordinary approvals. A turn that
        # explicitly asked to see its own decisions must not have them executed
        # underneath it.
        result, decision = _broker(workspace).execute(
            _write_action(workspace),
            session_id="sess_1",
            turn_id="turn_1",
            approval_mode="auto",
            turn_capability_modes={_WRITE: "ask"},
        )
        assert decision.decision == "needs_approval"
        assert result.status == "approval_required"
        assert not (workspace / "notes.md").exists()

    def test_naming_no_posture_changes_nothing(self, workspace: Path) -> None:
        _result, decision = _broker(workspace).execute(
            _write_action(workspace),
            session_id="sess_1",
            turn_id="turn_1",
        )
        assert decision.decision == "needs_approval"
        assert "denied_by_turn_posture" not in decision.reasons

    def test_a_loosening_value_reaching_the_broker_directly_is_ignored(
        self, workspace: Path
    ) -> None:
        # Second, independent refusal: even a caller that bypasses the envelope
        # cannot widen a turn through this parameter.
        _result, decision = _broker(workspace).execute(
            _write_action(workspace),
            session_id="sess_1",
            turn_id="turn_1",
            turn_capability_modes={_WRITE: "allow"},
        )
        assert decision.decision == "needs_approval"


class TestThePostureSurvivesAnApproval:
    def test_a_parked_turn_carries_its_posture_into_the_resume(self) -> None:
        # A turn parked in Plan mode has to resume in Plan mode; picking up the
        # standing modes hours later would silently change what it may do.
        from raiker.contracts.models import PromptEnvelope

        options = PromptOptions(capability_modes={_WRITE: "deny"})
        restored = PromptEnvelope.from_dict(
            {
                "schema_version": "1.0",
                "request_id": "req_1",
                "session_id": "sess_1",
                "turn_id": "turn_1",
                "client": {"type": "web_ui", "name": "raiker-web", "version": "0.0.0"},
                "user": {"id": "principal_owner"},
                "prompt": {"text": "do the thing"},
                "options": {
                    "planning_mode": options.planning_mode,
                    "approval_mode": options.approval_mode,
                    "model_profile": options.model_profile,
                    "model": options.model,
                    "reasoning_effort": options.reasoning_effort,
                    "max_tool_calls": options.max_tool_calls,
                    "capability_modes": dict(options.capability_modes),
                },
            }
        )
        assert restored.options.capability_modes == {_WRITE: "deny"}
