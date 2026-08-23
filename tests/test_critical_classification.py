"""Workstream F / Slice F6 (ZT-7) — production critical-risk classification.

Two layers of coverage:

* unit tests over the canonical table (`raiker/runtime/authority/critical.py`)
  proving each of the five criteria (a)-(e) is recognised, and that near-misses
  are *not* elevated (so the floor is not over-broad);
* router-integration tests proving every criterion routes to the critical floor
  — an AI-proposed action is parked for a human decision (F7) and a human is
  asked to confirm — regardless of the action's self-declared risk level or any
  permissive decision mode. The full parked → resolve lifecycle lives in
  ``tests/test_critical_lifecycle.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.contracts.ids import new_id
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.critical import (
    CRITICAL_CROSS_PRINCIPAL_RESTORE,
    CRITICAL_EXTERNAL_SEND_UNLISTED,
    CRITICAL_GRANT_MUTATION,
    CRITICAL_TIER2_RELAXATION,
    CRITICAL_VAULT_OR_EGRESS,
    classify_critical,
)
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


@pytest.fixture
def authority(store: SQLiteStore) -> RuntimeAuthority:
    return RuntimeAuthority(store, EventLogWriter(store))


def _ai() -> Principal:
    return Principal(
        principal_id="test_ai",
        principal_type=PrincipalType.AI_AGENT,
        display_name="AI",
        role_ids=("rl_assistant",),
        is_active=True,
    )


def _human() -> Principal:
    return Principal(
        principal_id="test_human",
        principal_type=PrincipalType.HUMAN,
        display_name="Human",
        role_ids=("rl_owner",),
        is_active=True,
    )


def _action(action_type: str, *, tool: str = "", args: dict | None = None) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id="test_ai",
        action_type=action_type,
        tool_or_service_name=tool or action_type,
        arguments=args or {},
        # Deliberately declare low risk: classification must elevate regardless.
        risk_level=RiskLevelValue.LOW,
    )


# ── unit: each criterion is recognised (ZT-7) ───────────────────────────────


def test_criterion_a_tier2_gate_enable_is_critical() -> None:
    match = classify_critical(
        "enable_runtime_gate", "", {"capability": "shell_execution", "target_state": "enabled"}
    )
    assert match is not None and match.code == CRITICAL_TIER2_RELAXATION


def test_criterion_a_tier2_threat_ack_is_critical() -> None:
    match = classify_critical("threat_model_ack", "", {"capability": "process_execution"})
    assert match is not None and match.code == CRITICAL_TIER2_RELAXATION


def test_criterion_a_tier2_confirmation_token_is_critical() -> None:
    match = classify_critical("confirmation_token_issue", "", {"capability": "process_execution"})
    assert match is not None and match.code == CRITICAL_TIER2_RELAXATION


def test_criterion_b_external_send_unlisted_is_critical() -> None:
    match = classify_critical("email_send", "", {"to": "stranger@example.com"})
    assert match is not None and match.code == CRITICAL_EXTERNAL_SEND_UNLISTED


def test_criterion_c_cross_principal_restore_is_critical() -> None:
    match = classify_critical(
        "checkpoint_restore", "", {"checkpoint_id": "cp_1", "touches_other_principal": True}
    )
    assert match is not None and match.code == CRITICAL_CROSS_PRINCIPAL_RESTORE


def test_criterion_d_grant_mutation_is_critical() -> None:
    match = classify_critical("standing_grant_create", "", {})
    assert match is not None and match.code == CRITICAL_GRANT_MUTATION


def test_criterion_e_vault_or_egress_is_critical() -> None:
    by_action = classify_critical("credential_rotate", "", {})
    assert by_action is not None and by_action.code == CRITICAL_VAULT_OR_EGRESS
    by_tool = classify_critical("noop", "egress_allowlist_add", {})
    assert by_tool is not None and by_tool.code == CRITICAL_VAULT_OR_EGRESS


# ── unit: near-misses are NOT elevated (floor is not over-broad) ─────────────


def test_ordinary_file_write_is_not_critical() -> None:
    assert classify_critical("write_file", "", {"path": "a.txt", "text": "hi"}) is None


def test_tier2_gate_disable_is_not_critical() -> None:
    # Tightening a Tier-2 gate (transition to disabled) is never critical.
    assert (
        classify_critical(
            "enable_runtime_gate", "", {"capability": "shell_execution", "target_state": "disabled"}
        )
        is None
    )


def test_external_send_to_allowlisted_recipient_is_not_critical() -> None:
    assert (
        classify_critical(
            "email_send", "", {"to": "boss@my-company.com"},
            recipient_allowlist=["*@my-company.com"],
        )
        is None
    )


def test_ordinary_checkpoint_restore_is_not_critical() -> None:
    # A same-principal restore is medium risk (B4), not critical.
    assert classify_critical("checkpoint_restore", "", {"checkpoint_id": "cp_1"}) is None


# ── router integration: every criterion routes to the critical floor ─────────

# Criterion (a) is exercised via the threat-ack / confirmation-token variants:
# the gate-transition action type (`enable_runtime_gate`) is intercepted by the
# router's earlier AI-cannot-enable-gates check, so its critical routing is
# proven at the unit level above instead.
_CRITICAL_ACTIONS = [
    ("threat_model_ack", {"capability": "web_fetch"}),
    ("confirmation_token_issue", {"capability": "shell_execution"}),
    ("email_send", {"to": "stranger@example.com"}),
    ("checkpoint_restore", {"checkpoint_id": "cp_1", "touches_other_principal": True}),
    ("standing_grant_create", {}),
    ("credential_rotate", {}),
]


@pytest.mark.parametrize(("action_type", "args"), _CRITICAL_ACTIONS)
def test_ai_proposed_critical_action_is_parked_not_executed(
    authority: RuntimeAuthority, action_type: str, args: dict
) -> None:
    # F7: an AI-proposed critical action is no longer silently flat-denied — it is
    # parked as a critical approval (resting state deny) and the owner is notified.
    # Nothing executes; only a live human may later resolve it.
    result = authority.route_action(_action(action_type, args=args), _ai())
    assert result.decision == "needs_human_confirmation"
    assert result.message == "critical_action_parked_for_human"
    assert result.approval_id is not None


@pytest.mark.parametrize(("action_type", "args"), _CRITICAL_ACTIONS)
def test_human_critical_action_needs_confirmation(
    authority: RuntimeAuthority, action_type: str, args: dict
) -> None:
    human = _human()
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id=human.principal_id,
        action_type=action_type,
        tool_or_service_name=action_type,
        arguments=args,
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, human)
    # A human proposing a critical action directly still cannot execute it in-band:
    # it is parked for an explicit, step-up-verified confirmation.
    assert result.decision == "needs_human_confirmation"
    assert result.approval_id is not None


def test_critical_classification_emits_audit_event(
    authority: RuntimeAuthority, store: SQLiteStore
) -> None:
    authority.route_action(_action("credential_rotate"), _ai())
    from raiker.events.query import EventViewer

    events = EventViewer(store).list_events(event_type="critical_action_classified", limit=50)
    assert len(events) == 1
