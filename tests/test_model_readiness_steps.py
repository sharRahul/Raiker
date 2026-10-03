# SPDX-License-Identifier: Apache-2.0
"""UX-MODEL-02 — a decision said as four steps and one next action.

"Provider connected", "models discovered", "model selected" and "runtime
available" were four facts an owner had to find and order themselves. The
decision now says them in that order: every step before the one that stops the
work is done, that one is blocked and carries the action, and every step after
it is waiting rather than failed. These cases pin the table one verdict at a
time, and one end-to-end case shows the route carries it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.decision import ModelChoice, readiness_steps
from raiker.models.readiness import ModelReadiness, ModelReadinessKey, ModelReadinessState
from raiker.models.wire import ReadinessStep

OWNER = "principal_owner"
CHOSEN = ModelChoice("anthropic-hosted", "claude-sonnet-5-5", "global_default")
NOTHING = ModelChoice("", "", "native_default")


def _verdict(state: ModelReadinessState, reason_code: str) -> ModelReadiness:
    return ModelReadiness(
        key=ModelReadinessKey(OWNER, CHOSEN.profile_id, CHOSEN.model, ""),
        state=state,
        checked_at=None,
        expires_at=None,
        summary="",
        reason_code=reason_code,
        remediation="",
        evidence={},
    )


def _states(steps: tuple[ReadinessStep, ...]) -> list[str]:
    return [step["state"] for step in steps]


def test_a_ready_pair_is_four_done_steps_and_no_action() -> None:
    steps, action = readiness_steps(
        selected=CHOSEN,
        head=_verdict(ModelReadinessState.READY, "ready"),
        has_connection=True,
        catalogue_lists_model=True,
    )
    assert [step["id"] for step in steps] == ["connect", "discover", "choose", "run"]
    assert _states(steps) == ["done", "done", "done", "done"]
    assert action is None


def test_no_provider_at_all_stops_at_the_first_step() -> None:
    steps, action = readiness_steps(
        selected=NOTHING, head=None, has_connection=False, catalogue_lists_model=None
    )
    assert _states(steps) == ["blocked", "waiting", "waiting", "waiting"]
    assert action == {"label": "Connect a provider", "target": "add"}


def test_connected_but_nothing_chosen_asks_for_a_choice() -> None:
    steps, action = readiness_steps(
        selected=NOTHING, head=None, has_connection=True, catalogue_lists_model=None
    )
    assert _states(steps) == ["done", "done", "blocked", "waiting"]
    assert action == {"label": "Choose a model", "target": "models"}


@pytest.mark.parametrize(
    ("state", "reason", "blocked", "target"),
    [
        (ModelReadinessState.AUTHENTICATION_FAILED, "provider_authentication_failed", "connect", "add"),
        (ModelReadinessState.AUTHENTICATION_FAILED, "provider_workspace_required", "connect", "add"),
        (ModelReadinessState.MODEL_MISSING, "provider_model_missing", "discover", "models"),
        (ModelReadinessState.UNSUPPORTED, "model_catalogue_unsupported", "discover", "add"),
        (ModelReadinessState.RUNTIME_STOPPED, "local_runtime_unreachable", "run", "runtime"),
        (ModelReadinessState.QUOTA_EXHAUSTED, "provider_quota_exhausted", "run", "check"),
        (ModelReadinessState.POLICY_BLOCKED, "provider_policy_blocked", "run", "permissions"),
        (ModelReadinessState.UNREACHABLE, "provider_unreachable", "run", "check"),
        # One state, two steps: an execution check the provider will not run is
        # a "run" problem, not a catalogue one.
        (ModelReadinessState.UNSUPPORTED, "provider_execution_probe_unsupported", "run", "check"),
    ],
)
def test_each_verdict_stops_at_its_own_step(
    state: ModelReadinessState, reason: str, blocked: str, target: str
) -> None:
    steps, action = readiness_steps(
        selected=CHOSEN,
        head=_verdict(state, reason),
        has_connection=True,
        catalogue_lists_model=True,
    )
    states: dict[str, str] = {step["id"]: step["state"] for step in steps}
    assert states[blocked] == "blocked"
    order = ["connect", "discover", "choose", "run"]
    for step_id in order[: order.index(blocked)]:
        assert states[step_id] == "done"
    for step_id in order[order.index(blocked) + 1 :]:
        assert states[step_id] == "waiting"
    assert action is not None and action["target"] == target


def test_a_pair_never_checked_is_unchecked_not_broken() -> None:
    steps, action = readiness_steps(
        selected=CHOSEN,
        head=_verdict(ModelReadinessState.NOT_CONFIGURED, "model_not_checked"),
        has_connection=True,
        catalogue_lists_model=None,
    )
    # Connected is on record; the catalogue never named it and nothing ran.
    assert _states(steps) == ["done", "unchecked", "done", "unchecked"]
    assert action == {"label": "Check it now", "target": "check"}
    assert "blocked" not in _states(steps)


def test_an_expired_observation_is_unchecked_at_run() -> None:
    steps, action = readiness_steps(
        selected=CHOSEN,
        head=_verdict(ModelReadinessState.STALE, "readiness_expired"),
        has_connection=True,
        catalogue_lists_model=True,
    )
    assert _states(steps) == ["done", "done", "done", "unchecked"]
    assert action is not None and action["target"] == "check"


def test_an_unreadable_chain_claims_no_step() -> None:
    steps, action = readiness_steps(
        selected=CHOSEN, head=None, has_connection=True, catalogue_lists_model=True
    )
    assert set(_states(steps)) == {"unchecked"}
    assert action == {"label": "Check it now", "target": "check"}


def test_the_decisions_route_carries_steps_for_every_surface(tmp_path: Path) -> None:
    root = tmp_path / "steps"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    token, _ = ApiSessionStore(root).create_session(OWNER)
    client = TestClient(create_app(root))
    answer = client.get("/api/model-decisions", headers={"Authorization": f"Bearer {token}"})
    assert answer.status_code == 200
    for surface, decision in answer.json()["surfaces"].items():
        assert [step["id"] for step in decision["steps"]] == [
            "connect", "discover", "choose", "run",
        ], surface
        # A fresh install has chosen nothing, and says which step that is.
        assert "blocked" in [step["state"] for step in decision["steps"]]
        assert decision["next_action"] is not None
